"""Daily job: NLP → Parquet → GPR + corridor indices → Postgres."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gpr_index.scripts.paths import INDIA_PROCESSED_DIR, OUTPUT_DIR  # noqa: E402

from news_dataset import db  # noqa: E402
from news_dataset.export.to_db import sync_all  # noqa: E402
from news_dataset.export.to_gpr_parquet import process_day  # noqa: E402
from news_dataset.nlp.run_extraction import run as run_nlp  # noqa: E402


def _day(value: str) -> date:
    return date.fromisoformat(value)


def _run_cmd(args: list[str], *, cwd: Path | None = None) -> None:
    result = subprocess.run(args, cwd=cwd or REPO_ROOT, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}")


def run_daily_index(
    day: date,
    *,
    nlp_limit: int = 500,
    skip_nlp: bool = False,
    skip_gpr: bool = False,
    force_export: bool = False,
) -> dict:
    """Run the full daily index pipeline for one UTC calendar day."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    details: dict = {"day": day.isoformat()}

    if not skip_nlp:
        updated, failed = run_nlp(limit=nlp_limit, start=start, end=end)
        details["nlp_updated"] = updated
        details["nlp_failed"] = failed
        db.log_pipeline_run("nlp", "ok" if failed == 0 else "partial", details)

    export_path = process_day(day, INDIA_PROCESSED_DIR, force=force_export)
    details["parquet"] = str(export_path) if export_path else None
    if export_path is None:
        db.log_pipeline_run("export", "skipped", details)
        return details

    db.log_pipeline_run("export", "ok", details)

    if not skip_gpr:
        day_str = day.isoformat()
        baseline_start = (day - timedelta(days=365)).isoformat()
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
                day_str,
                "--end-date",
                day_str,
                "--baseline-start",
                baseline_start,
                "--baseline-end",
                day_str,
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
                day_str,
                "--end-date",
                day_str,
            ]
        )
        db.log_pipeline_run("gpr_corridor", "ok", {"day": day_str})

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


def _refresh_dual_signal() -> None:
    from news_dataset.api.gpr_service import build_dual_signal_payload

    payload = build_dual_signal_payload(refresh=True)
    as_of = payload["geopolitical"]["as_of"]
    db.upsert_dual_signal(as_of, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=_day, help="UTC day (default: yesterday)")
    parser.add_argument("--nlp-limit", type=int, default=500)
    parser.add_argument("--skip-nlp", action="store_true")
    parser.add_argument("--skip-gpr", action="store_true")
    parser.add_argument("--force-export", action="store_true")
    args = parser.parse_args()
    day = args.date or (date.today() - timedelta(days=1))
    try:
        details = run_daily_index(
            day,
            nlp_limit=args.nlp_limit,
            skip_nlp=args.skip_nlp,
            skip_gpr=args.skip_gpr,
            force_export=args.force_export,
        )
        print(f"[daily_index] {day.isoformat()} ok: {details}")
        return 0
    except Exception as exc:
        db.log_pipeline_run("daily_index", "error", {"day": day.isoformat(), "error": str(exc)})
        print(f"[daily_index] {day.isoformat()} FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
