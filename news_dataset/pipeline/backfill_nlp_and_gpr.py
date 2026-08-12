"""Backfill NLP tags on all tier articles, then run GPR/corridor index for every tier day."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from news_dataset import db  # noqa: E402
from news_dataset.nlp.run_extraction import NLP_MODEL_VERSION, run as run_nlp  # noqa: E402
from news_dataset.pipeline.daily_index import parquet_bounds, run_daily_index, run_gpr_range  # noqa: E402
from news_dataset.export.to_db import sync_all  # noqa: E402


def _pending() -> int:
    return db.count_articles_pending_nlp(NLP_MODEL_VERSION)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nlp-batch", type=int, default=1000, help="NLP batch size")
    parser.add_argument("--skip-nlp", action="store_true")
    parser.add_argument("--skip-gpr", action="store_true", help="NLP only")
    parser.add_argument(
        "--no-force-export",
        action="store_true",
        help="skip overwriting existing parquet files",
    )
    parser.add_argument(
        "--strict-denominator",
        action="store_true",
        help="fail on incomplete geo_seen_links denominator",
    )
    args = parser.parse_args()
    force_export = not args.no_force_export
    allow_incomplete = not args.strict_denominator

    if not args.skip_nlp:
        print(f"[backfill] NLP pending before: {_pending():,}")
        updated, failed = run_nlp(limit=args.nlp_batch, until_empty=True)
        print(f"[backfill] NLP done: {updated:,} updated, {failed:,} failed; pending={_pending():,}")
        if _pending() > 0:
            print("[backfill] WARNING: some tier articles still lack NLP tags", file=sys.stderr)
            return 1

    if args.skip_gpr:
        return 0

    days = db.list_tier_article_days()
    print(f"[backfill] exporting parquet for {len(days)} tier days …")
    failures: list[str] = []
    for i, day in enumerate(days, 1):
        try:
            details = run_daily_index(
                day,
                skip_nlp=True,
                skip_gpr=True,
                force_export=force_export,
                allow_incomplete_denominator=allow_incomplete,
            )
            print(f"[backfill] [{i}/{len(days)}] {day.isoformat()} ok — parquet={details.get('parquet')}")
        except Exception as exc:
            failures.append(f"{day.isoformat()}: {exc}")
            print(f"[backfill] [{i}/{len(days)}] {day.isoformat()} FAIL: {exc}", file=sys.stderr)

    if days and not failures:
        bounds = parquet_bounds(days[-1])
        if bounds:
            print(f"[backfill] batch GPR + corridor {bounds[0]} → {bounds[1]} …")
            try:
                run_gpr_range(bounds[0], bounds[1])
                counts = sync_all()
                print(f"[backfill] synced to DB: {counts}")
            except Exception as exc:
                failures.append(f"gpr batch: {exc}")
                print(f"[backfill] batch GPR FAIL: {exc}", file=sys.stderr)

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM gpr_daily")
    gpr_rows = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"[backfill] gpr_daily rows: {gpr_rows}")

    if failures:
        print(f"[backfill] {len(failures)} day(s) failed", file=sys.stderr)
        for line in failures[:10]:
            print(f"  - {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
