"""Hourly incremental update: export → preprocess today → re-score today's GPR.

Drops article-to-index latency from ~24h to ~1h.

Steps each run:
  1. export_news_db.export_day(today)          — SQLite → JSONL (idempotent)
  2. preprocess_indian_news.run(today, force)  — JSONL → tagged parquet
  3. gkg_gpr_pipeline.run(... only_dirty_days) — re-score today only, merge
                                                  with existing history rows

Usage:
  python -m scripts.incremental_update [--output-dir outputs/india] [--date YYYY-MM-DD]
  (from cron: python main.py incremental-update)
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

IST      = ZoneInfo("Asia/Kolkata")
REPO_ROOT = Path(__file__).parent.parent


def _today_ist() -> str:
    return datetime.now(IST).date().isoformat()


def run(
    output_dir: Path | None = None,
    date_str: str | None = None,
    processed_dir: Path | None = None,
) -> None:
    target = date_str or _today_ist()
    output_dir    = output_dir    or (REPO_ROOT / "outputs")
    processed_dir = processed_dir or (REPO_ROOT / "data" / "india_processed")

    logger.info(f"[incremental] target date={target}")

    # Step 1: export SQLite → JSONL
    logger.info("[incremental] Step 1/3: export_news_db …")
    from scripts.export_news_db import export_day  # noqa: PLC0415
    count = export_day(date_str=target)
    logger.info(f"[incremental]   {count} new articles appended to india_raw/")

    # Step 2: preprocess → parquet (force=True so today is always re-tagged)
    logger.info("[incremental] Step 2/3: preprocess_indian_news …")
    from scripts.preprocess_indian_news import process_day  # noqa: PLC0415
    from datetime import date as _date  # noqa: PLC0415
    n_articles = process_day(
        day=_date.fromisoformat(target),
        raw_dir=REPO_ROOT / "data" / "india_raw",
        out_dir=processed_dir,
        force=True,
    )
    logger.info(f"[incremental]   {n_articles} articles in today's parquet")

    if n_articles == 0:
        logger.warning("[incremental] No articles processed — skipping GPR re-score")
        return

    # Step 3: re-score today via gkg_gpr_pipeline (only_dirty_days shortcut)
    logger.info("[incremental] Step 3/3: gkg_gpr_pipeline (only_dirty_days) …")
    from scripts.gkg_gpr_pipeline import run as gpr_run  # noqa: PLC0415
    import pandas as pd  # noqa: PLC0415

    # Determine overall start date from existing daily index
    daily_csv = output_dir / "gpr_daily_index.csv"
    if daily_csv.exists():
        existing = pd.read_csv(daily_csv, parse_dates=["date"])
        start_date = existing["date"].min().date().isoformat()
    else:
        start_date = "2025-01-01"

    gpr_run(
        processed_dir=processed_dir,
        output_dir=output_dir,
        start_date=start_date,
        end_date=target,
        baseline_start=start_date,
        baseline_end=target,
        save_article_scores=False,   # skip article scores on incremental runs
        fill_gaps=True,
        only_dirty_days=[target],    # new flag: skip re-scoring untouched days
    )
    logger.info(f"[incremental] Done. GPR index updated through {target}.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Hourly incremental GPR update (India path)")
    p.add_argument("--output-dir",    default=None, help="GPR output dir (default: outputs/india)")
    p.add_argument("--processed-dir", default=None, help="Parquet dir (default: data/india_processed)")
    p.add_argument("--date",          default=None, help="YYYY-MM-DD (default: today IST)")
    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    run(
        output_dir=Path(args.output_dir) if args.output_dir else None,
        processed_dir=Path(args.processed_dir) if args.processed_dir else None,
        date_str=args.date,
    )


if __name__ == "__main__":
    main()
