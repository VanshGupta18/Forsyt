"""Daily job: NLP → Parquet → GPR + corridor indices → Postgres."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gpr_index.scripts.paths import INDIA_GPR_INDEX_START, INDIA_PROCESSED_DIR, OUTPUT_DIR  # noqa: E402

from news_dataset import db  # noqa: E402
from news_dataset.export.to_db import sync_all  # noqa: E402
from news_dataset.export.to_gpr_parquet import ExportIntegrityError, process_day  # noqa: E402
from news_dataset.nlp.run_extraction import run as run_nlp  # noqa: E402

MIN_PARQUET_DAYS_FOR_GPR = int(os.environ.get("MIN_PARQUET_DAYS_FOR_GPR", "7"))
BACKFILL_LOOKBACK_DAYS = int(os.environ.get("PARQUET_BACKFILL_LOOKBACK_DAYS", "14"))


def _day(value: str) -> date:
    return date.fromisoformat(value)


def _days(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _run_cmd(args: list[str], *, cwd: Path | None = None) -> None:
    result = subprocess.run(args, cwd=cwd or REPO_ROOT, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}")


def _clamp_index_start(day: date) -> date:
    return max(day, INDIA_GPR_INDEX_START)


def _list_processed_files(end_day: date, *, lookback_days: int = 365):
    from gpr_index.scripts.gkg_gpr_pipeline import list_processed_files

    baseline = max(
        end_day - timedelta(days=lookback_days),
        INDIA_GPR_INDEX_START,
    )
    return list_processed_files(
        INDIA_PROCESSED_DIR,
        baseline.isoformat(),
        end_day.isoformat(),
    )


def parquet_bounds(end_day: date, *, lookback_days: int = 365) -> tuple[date, date] | None:
    """Earliest/latest dates with India parquet files up to end_day."""
    files = _list_processed_files(end_day, lookback_days=lookback_days)
    if not files:
        return None
    start = _clamp_index_start(files[0][0].date())
    if start > end_day:
        return None
    return start, files[-1][0].date()


def processed_day_count(end_day: date, *, lookback_days: int = 365) -> int:
    return len(_list_processed_files(end_day, lookback_days=lookback_days))


def required_parquet_days(end_day: date) -> int:
    """Days required before GPR scoring (ramps up to MIN_PARQUET_DAYS_FOR_GPR)."""
    days_in_index = max(0, (end_day - INDIA_GPR_INDEX_START).days + 1)
    return min(MIN_PARQUET_DAYS_FOR_GPR, days_in_index)


def backfill_missing_parquets(
    end_day: date,
    *,
    lookback_days: int = BACKFILL_LOOKBACK_DAYS,
    allow_incomplete_denominator: bool = False,
) -> list[str]:
    """Export parquet for recent days that have data but no cached file yet."""
    start_day = max(end_day - timedelta(days=lookback_days), INDIA_GPR_INDEX_START)
    created: list[str] = []
    for day in _days(start_day, end_day):
        ymd = day.strftime("%Y%m%d")
        path = INDIA_PROCESSED_DIR / f"india_processed_{ymd}.parquet"
        if path.exists():
            continue
        try:
            result = process_day(
                day,
                INDIA_PROCESSED_DIR,
                allow_incomplete_denominator=allow_incomplete_denominator,
            )
        except ExportIntegrityError as exc:
            print(f"[backfill {day.isoformat()}] skip: {exc}")
            continue
        if result is not None:
            created.append(day.isoformat())
    return created


def run_gpr_range(start_day: date, end_day: date) -> None:
    """Score and normalize GPR + corridors across every parquet day in range.

    Normalization needs multiple days in one batch — running one day at a time
    forces gpr_index to 100 every time (ratio / its own mean = 1).
    """
    start_day = _clamp_index_start(start_day)
    baseline_start = INDIA_GPR_INDEX_START.isoformat()
    start_str = start_day.isoformat()
    end_str = end_day.isoformat()
    _run_cmd(
        [
            sys.executable,
            "gpr_index/main.py",
            "gpr",
            "--processed-dir",
            str(INDIA_PROCESSED_DIR),
            "--output-dir",
            str(OUTPUT_DIR),
            "--start-date",
            start_str,
            "--end-date",
            end_str,
            "--baseline-start",
            baseline_start,
            "--baseline-end",
            end_str,
        ]
    )
    _run_cmd(
        [
            sys.executable,
            "gpr_index/main.py",
            "corridor",
            "--processed-dir",
            str(INDIA_PROCESSED_DIR),
            "--output-dir",
            str(OUTPUT_DIR),
            "--start-date",
            start_str,
            "--end-date",
            end_str,
            "--baseline-start",
            baseline_start,
            "--baseline-end",
            end_str,
        ]
    )


def run_daily_index(
    day: date,
    *,
    nlp_limit: int = 500,
    skip_nlp: bool = False,
    skip_gpr: bool = False,
    force_export: bool = False,
    allow_incomplete_denominator: bool = False,
) -> dict:
    """Run the full daily index pipeline for one UTC calendar day."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    details: dict = {"day": day.isoformat()}

    backfilled = backfill_missing_parquets(
        day,
        allow_incomplete_denominator=allow_incomplete_denominator,
    )
    if backfilled:
        details["backfilled_parquet_days"] = backfilled

    if not skip_nlp:
        updated, failed = run_nlp(limit=nlp_limit, start=start, end=end)
        details["nlp_updated"] = updated
        details["nlp_failed"] = failed
        db.log_pipeline_run("nlp", "ok" if failed == 0 else "partial", details)

    export_path = process_day(
        day,
        INDIA_PROCESSED_DIR,
        force=force_export,
        allow_incomplete_denominator=allow_incomplete_denominator,
    )
    details["parquet"] = str(export_path) if export_path else None
    if export_path is None:
        db.log_pipeline_run("export", "skipped", details)
        return details

    db.log_pipeline_run("export", "ok", details)

    if not skip_gpr:
        bounds = parquet_bounds(day)
        parquet_days = processed_day_count(day)
        details["parquet_days"] = parquet_days
        needed = required_parquet_days(day)
        details["parquet_days_required"] = needed
        if not bounds:
            db.log_pipeline_run(
                "gpr_corridor",
                "skipped",
                {"day": day.isoformat(), "reason": "no parquet"},
            )
        elif parquet_days < needed:
            reason = (
                f"only {parquet_days} parquet day(s) on disk since "
                f"{INDIA_GPR_INDEX_START.isoformat()}; need {needed} for stable GPR normalization"
            )
            print(f"[daily_index] SKIP GPR: {reason}")
            db.log_pipeline_run(
                "gpr_corridor",
                "skipped",
                {"day": day.isoformat(), "reason": reason, "parquet_days": parquet_days},
            )
        else:
            run_gpr_range(bounds[0], bounds[1])
            db.log_pipeline_run(
                "gpr_corridor",
                "ok",
                {
                    "day": day.isoformat(),
                    "range": f"{bounds[0]}..{bounds[1]}",
                    "parquet_days": parquet_days,
                },
            )
            counts = sync_all()
            details.update(counts)
            db.log_pipeline_run("to_db", "ok", details)
    else:
        counts = sync_all()
        details.update(counts)
        db.log_pipeline_run("to_db", "ok", details)

    try:
        _refresh_dual_signal()
        db.log_pipeline_run("dual_signal", "ok", {"day": day.isoformat()})
    except Exception as exc:
        db.log_pipeline_run("dual_signal", "error", {"error": str(exc)})
        details["dual_signal_error"] = str(exc)

    return details


def _refresh_dual_signal() -> str | None:
    from news_dataset.api.gpr_service import build_dual_signal_payload

    payload = build_dual_signal_payload(refresh=True)
    as_of = payload["geopolitical"]["as_of"]
    db.upsert_dual_signal(as_of, payload)
    return str(as_of)[:10] if as_of else None


def refresh_dual_signal() -> str | None:
    """Public wrapper for dual-signal cache refresh after index sync."""
    return _refresh_dual_signal()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=_day, help="UTC day (default: yesterday)")
    parser.add_argument("--nlp-limit", type=int, default=500)
    parser.add_argument("--skip-nlp", action="store_true")
    parser.add_argument("--skip-gpr", action="store_true")
    parser.add_argument("--force-export", action="store_true")
    parser.add_argument(
        "--allow-incomplete-denominator",
        action="store_true",
        help="pass through to parquet export for incomplete geo_seen_links history",
    )
    args = parser.parse_args()
    day = args.date or (date.today() - timedelta(days=1))
    try:
        details = run_daily_index(
            day,
            nlp_limit=args.nlp_limit,
            skip_nlp=args.skip_nlp,
            skip_gpr=args.skip_gpr,
            force_export=args.force_export,
            allow_incomplete_denominator=args.allow_incomplete_denominator,
        )
        print(f"[daily_index] {day.isoformat()} ok: {details}")
        return 0
    except Exception as exc:
        db.log_pipeline_run("daily_index", "error", {"day": day.isoformat(), "error": str(exc)})
        print(f"[daily_index] {day.isoformat()} FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
