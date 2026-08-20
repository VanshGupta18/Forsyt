"""Hourly platform refresh: NLP batch → parquets → GPR/corridors → Postgres + dual-signal."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta, timezone

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

STAGE = "platform_refresh"
NLP_BATCH = int(os.environ.get("PLATFORM_REFRESH_NLP_BATCH", "200"))


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


def run_platform_refresh(*, skip_nlp: bool = False, skip_dual_signal: bool = False) -> dict:
    today = date.today()
    yesterday = today - timedelta(days=1)
    details: dict = {"day": today.isoformat()}

    if not skip_nlp:
        pending = db.count_articles_pending_nlp(NLP_MODEL_VERSION)
        details["nlp_pending_before"] = pending
        if pending > 0:
            updated, failed = run_nlp(limit=NLP_BATCH)
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
