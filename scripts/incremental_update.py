"""Hourly incremental update: export → preprocess today → re-score GPR (news path).

Drops article-to-index latency from ~24h to ~1h.

Steps each run:
  1. export_news_db.export_day(today)          — SQLite → data/india_raw/ JSONL
  2. series_state: set anchor_date on first run with articles
  3. preprocess_indian_news.run(today, force)  — JSONL → data/india_processed/ parquet
  4. gkg_gpr_pipeline.run(start=anchor, end=today, only_dirty_days=[today])
     → outputs/news/

Caldara gap-fill is NOT performed for dates on or after anchor_date.

Usage:
  python -m scripts.incremental_update [--output-dir outputs/news] [--date YYYY-MM-DD]
  (from cron: python main.py incremental-update)
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

IST       = ZoneInfo("Asia/Kolkata")
REPO_ROOT = Path(__file__).parent.parent

NEWS_OUTPUT_DIR   = REPO_ROOT / "outputs" / "news"
PROCESSED_DIR_DEF = REPO_ROOT / "data" / "india_processed"


def _today_ist() -> str:
    return datetime.now(IST).date().isoformat()


def run(
    output_dir: Path | None = None,
    date_str: str | None = None,
    processed_dir: Path | None = None,
) -> None:
    target        = date_str or _today_ist()
    output_dir    = output_dir    or NEWS_OUTPUT_DIR
    processed_dir = processed_dir or PROCESSED_DIR_DEF

    logger.info(f"[incremental] target date={target}, output={output_dir}")

    # Step 1: export SQLite → JSONL
    logger.info("[incremental] 1/4 export_news_db …")
    from scripts.export_news_db import export_day  # noqa: PLC0415
    count = export_day(date_str=target)
    logger.info(f"[incremental]   {count} new articles appended")

    # Step 2: set anchor on first run with articles
    if count > 0:
        from scripts.series_state import set_anchor  # noqa: PLC0415
        set_anchor(target)

    # Step 3: preprocess → parquet (force=True so today is always re-tagged)
    logger.info("[incremental] 2/4 preprocess_indian_news …")
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
        logger.warning("[incremental] 0 articles processed — skipping GPR re-score")
        return

    # Step 4: re-score via gkg_gpr_pipeline (only today's data re-scored)
    logger.info("[incremental] 3/4 gkg_gpr_pipeline (only_dirty_days) …")
    from scripts.gkg_gpr_pipeline import run as gpr_run  # noqa: PLC0415
    from scripts.series_state import get_anchor, update_last_processed  # noqa: PLC0415

    anchor = get_anchor() or target
    output_dir.mkdir(parents=True, exist_ok=True)

    gpr_run(
        processed_dir=processed_dir,
        output_dir=output_dir,
        start_date=anchor,
        end_date=target,
        baseline_start=anchor,
        baseline_end=target,
        save_article_scores=False,
        fill_gaps=False,        # no Caldara fill for dates >= anchor
        only_dirty_days=[target],
    )

    update_last_processed(target)
    logger.info(f"[incremental] Done. GPR updated through {target} in {output_dir}/")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Hourly incremental GPR update (news path)")
    p.add_argument("--output-dir",    default=None,
                   help=f"GPR output dir (default: {NEWS_OUTPUT_DIR})")
    p.add_argument("--processed-dir", default=None,
                   help=f"Parquet dir (default: {PROCESSED_DIR_DEF})")
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
