"""Backfill missing index days: export parquets, recompute GPR/corridors, sync Postgres."""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gpr_index.scripts.paths import INDIA_GPR_INDEX_START  # noqa: E402

from news_dataset import db  # noqa: E402
from news_dataset.export.to_db import sync_all  # noqa: E402
from news_dataset.pipeline.daily_index import (  # noqa: E402
    _days,
    refresh_dual_signal,
    run_daily_index,
    run_gpr_range,
)


def catch_up_range(
    from_date: date,
    to_date: date,
    *,
    force_export: bool = True,
    allow_incomplete_denominator: bool = True,
    skip_dual_signal: bool = False,
) -> dict:
    from_date = max(from_date, INDIA_GPR_INDEX_START)
    to_date = max(to_date, from_date)

    exported: list[str] = []
    skipped: list[str] = []
    for day in _days(from_date, to_date):
        try:
            details = run_daily_index(
                day,
                skip_nlp=True,
                skip_gpr=True,
                force_export=force_export,
                allow_incomplete_denominator=allow_incomplete_denominator,
            )
            if details.get("parquet"):
                exported.append(day.isoformat())
            else:
                skipped.append(day.isoformat())
        except Exception as exc:
            skipped.append(f"{day.isoformat()}: {exc}")

    run_gpr_range(INDIA_GPR_INDEX_START, to_date)
    counts = sync_all()

    dual = None
    if not skip_dual_signal:
        dual = refresh_dual_signal()

    summary = {
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
        "exported_days": exported,
        "skipped_days": skipped,
        "sync": counts,
        "dual_signal_as_of": dual,
    }
    db.log_pipeline_run("catch_up_range", "ok", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-date", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--to-date",
        type=date.fromisoformat,
        default=date.today() - timedelta(days=0),
        help="inclusive end date (default: today UTC)",
    )
    parser.add_argument("--no-force-export", action="store_true")
    parser.add_argument("--strict-denominator", action="store_true")
    parser.add_argument("--skip-dual-signal", action="store_true")
    args = parser.parse_args()

    try:
        summary = catch_up_range(
            args.from_date,
            args.to_date,
            force_export=not args.no_force_export,
            allow_incomplete_denominator=not args.strict_denominator,
            skip_dual_signal=args.skip_dual_signal,
        )
        print(f"[catch_up_range] ok: {summary}")
        return 0
    except Exception as exc:
        db.log_pipeline_run(
            "catch_up_range",
            "error",
            {"from": args.from_date.isoformat(), "to": args.to_date.isoformat(), "error": str(exc)},
        )
        print(f"[catch_up_range] FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
