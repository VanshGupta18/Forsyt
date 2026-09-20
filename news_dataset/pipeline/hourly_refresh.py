"""Hourly platform refresh: NLP batch → parquets → GPR/corridors → Postgres + dual-signal.

Beginner note — the full order of operations for run_platform_refresh():
    Runs hourly via .github/workflows/platform_refresh.yml (20 minutes after
    the NLP scheduler, so freshly-tagged articles are ready). Unlike
    daily_index.py (which finalizes ONE past day), this job keeps TODAY and
    YESTERDAY's numbers current throughout the day:
    1. Tag articles missing NLP tags, today+yesterday first (the days this job
       re-exports, up to PLATFORM_REFRESH_NLP_WINDOW_MAX), then spend what is
       left of PLATFORM_REFRESH_NLP_BATCH on the older backlog.
    2. backfill_missing_parquets() + re-export today's and yesterday's
       Parquet files (via run_daily_index(..., skip_gpr=True) reused from
       pipeline/daily_index.py) so they reflect the newest articles.
    3. run_gpr_range() re-scores GPR + corridor risk, but only marks
       yesterday/today as "dirty" (dirty_days) so gpr_index/ doesn't have to
       recompute the whole history every hour — just the days that changed.
    4. sync_all() (export/to_db.py) pushes the updated CSV rows into Postgres.
    5. refresh_dual_signal() recomputes the cached geo+market combined signal.
    6. _warm_api_caches() pre-computes the "quality report" (so the first
       visitor of the hour doesn't wait on it) and tries to resolve article
       thumbnail images for up to 20 articles missing one.
    Every run's summary is logged via db.log_pipeline_run(STAGE, ...) for the
    /api/status and /api/pages/quality endpoints to report on.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, time, timedelta, timezone

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gpr_index.scripts.paths import INDIA_GPR_INDEX_START  # noqa: E402

from news_dataset import db  # noqa: E402
from news_dataset.export.to_db import sync_all  # noqa: E402
from news_dataset.nlp.run_extraction import NLP_MODEL_VERSION, run as run_nlp  # noqa: E402
from news_dataset.pipeline.daily_index import (  # noqa: E402
    backfill_missing_parquets,
    refresh_dual_signal,
    run_daily_index,
    run_gpr_range,
)

logger = logging.getLogger(__name__)

STAGE = "platform_refresh"
NLP_BATCH = int(os.environ.get("PLATFORM_REFRESH_NLP_BATCH", "200"))
# Ceiling for the today+yesterday catch-up pass. Must exceed a normal 2-day
# article volume or those days export half-tagged; tune if scrape volume grows.
NLP_WINDOW_MAX = int(os.environ.get("PLATFORM_REFRESH_NLP_WINDOW_MAX", "1000"))


def _warm_api_caches() -> dict:
    """Precompute quality report cache and resolve missing article images."""
    details: dict = {}
    try:
        from news_dataset.api.metrics_service import warm_quality_report_cache

        warm_quality_report_cache(refresh=False)
        details["quality_cache"] = "ok"
    except Exception as exc:
        details["quality_cache_error"] = str(exc)

    resolved = 0
    try:
        from news_dataset.api.link_preview import resolve_news_image

        for row in db.list_articles_missing_image(limit=20):
            try:
                image_url = resolve_news_image(row["link"])
                db.update_article_image_url(row["id"], image_url)
                if image_url:
                    resolved += 1
            except Exception:
                continue
        details["images_resolved"] = resolved
    except Exception as exc:
        details["image_warm_error"] = str(exc)

    return details


def _sync_search_index(dirty_days: list) -> dict:
    """Push the days we just re-exported into the vector index.

    Piggybacks on the same dirty-day set sync_all() uses rather than adding a
    scheduler: the articles whose NLP (and therefore embedding) just landed are
    exactly the ones in this window. A no-op returning {"enabled": False} when
    OPENSEARCH_URL is unset, which is the normal state everywhere except the
    compose stack — and never allowed to fail the refresh either way.
    """
    try:
        from news_dataset.search import opensearch_client

        if not opensearch_client.is_enabled():
            return {"enabled": False}
        if not dirty_days:
            return {"enabled": True, "indexed": 0}
        start = datetime.combine(min(dirty_days), time.min, tzinfo=timezone.utc)
        end = datetime.combine(max(dirty_days) + timedelta(days=1), time.min, tzinfo=timezone.utc)
        rows = db.get_articles_for_search_sync(start, end)
        return {"enabled": True, "indexed": opensearch_client.index_articles(rows)}
    except Exception as exc:  # noqa: BLE001 - search is optional, the refresh is not
        logger.warning("search index sync failed: %s", exc)
        return {"enabled": True, "error": str(exc)}


def run_platform_refresh(*, skip_nlp: bool = False, skip_dual_signal: bool = False) -> dict:
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    details: dict = {"day": today.isoformat()}

    if not skip_nlp:
        pending = db.count_articles_pending_nlp(NLP_MODEL_VERSION)
        details["nlp_pending_before"] = pending
        # The two days re-exported below must be fully tagged BEFORE that
        # export: a day's GPR is threat-tagged articles / total articles, so
        # exporting a day whose articles are still untagged scores it ~0.
        # get_articles_pending_nlp() is oldest-first, so any backlog bigger
        # than one batch spends the whole budget on old rows and starves today
        # indefinitely. Drain today+yesterday first, backlog gets the rest.
        window_start = datetime.combine(yesterday, time.min, tzinfo=timezone.utc)
        window_pending = db.count_articles_pending_nlp(
            NLP_MODEL_VERSION, start=window_start
        )
        details["nlp_window_pending_before"] = window_pending
        updated = failed = 0
        if window_pending > 0:
            updated, failed = run_nlp(limit=NLP_WINDOW_MAX, start=window_start)
        backlog_budget = max(0, NLP_BATCH - updated)
        if backlog_budget > 0 and pending > window_pending:
            backlog_updated, backlog_failed = run_nlp(limit=backlog_budget)
            updated += backlog_updated
            failed += backlog_failed
        details["nlp_updated"] = updated
        details["nlp_failed"] = failed

    backfilled = backfill_missing_parquets(today, allow_incomplete_denominator=True)
    if backfilled:
        details["backfilled_parquet_days"] = backfilled

    for day in (yesterday, today):
        try:
            day_details = run_daily_index(
                day,
                skip_nlp=True,
                skip_gpr=True,
                force_export=False,
                allow_incomplete_denominator=True,
            )
            details[f"export_{day.isoformat()}"] = day_details.get("parquet")
        except Exception as exc:
            details[f"export_{day.isoformat()}_error"] = str(exc)

    dirty = [d for d in (yesterday, today) if d >= INDIA_GPR_INDEX_START]
    run_gpr_range(INDIA_GPR_INDEX_START, today, dirty_days=dirty or None)
    counts = sync_all()
    details["sync"] = counts
    details["search_indexed"] = _sync_search_index(dirty)

    if not skip_dual_signal:
        details["dual_signal_as_of"] = refresh_dual_signal()

    details["api_cache_warm"] = _warm_api_caches()

    details["completed_at"] = datetime_now_iso()
    db.log_pipeline_run(STAGE, "ok", details)
    return details


def datetime_now_iso() -> str:
    return datetime_now().isoformat()


def datetime_now():
    from datetime import datetime

    return datetime.now(timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-nlp", action="store_true")
    parser.add_argument("--skip-dual-signal", action="store_true")
    args = parser.parse_args()

    try:
        details = run_platform_refresh(
            skip_nlp=args.skip_nlp,
            skip_dual_signal=args.skip_dual_signal,
        )
        print(f"[{STAGE}] ok: {details}")
        return 0
    except Exception as exc:
        db.log_pipeline_run(STAGE, "error", {"error": str(exc)})
        print(f"[{STAGE}] FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
