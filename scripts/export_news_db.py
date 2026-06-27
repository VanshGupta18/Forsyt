"""Export articles from live SQLite news.db to daily gzipped JSONL.

LIVE PATH ONLY — called after each 15-min scraper cycle via the scheduler wrapper.
Never involved in backfill (backfill writes directly to JSONL).

For each scrape cycle:
  - Reads all articles in news.db whose scraped_at is TODAY (Asia/Kolkata)
  - Deduplicates against existing entries in today's JSONL file (by link)
  - Appends new articles to data/india_raw/YYYY-MM-DD.jsonl.gz

Usage (called programmatically from scraper_wrapper.py):
  python -m scripts.export_news_db [--date YYYY-MM-DD] [--db-path PATH]
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
DEFAULT_DB_PATH = os.environ.get(
    "NEWS_DB_PATH",
    str(Path(__file__).parent.parent / "data" / "india_db" / "news.db"),
)
DEFAULT_RAW_DIR = Path(__file__).parent.parent / "data" / "india_raw"


def _today_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def _load_existing_links(jsonl_path: Path) -> set[str]:
    """Return set of links already in the day file."""
    if not jsonl_path.exists():
        return set()
    seen: set[str] = set()
    with gzip.open(jsonl_path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if "link" in obj:
                    seen.add(obj["link"])
            except json.JSONDecodeError:
                pass
    return seen


def _fetch_day_from_db(db_path: str, date_str: str) -> list[dict]:
    """Return all articles scraped on date_str (IST) from news.db."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT title, content, source, link, time, language, scraped_at
            FROM articles
            WHERE date(scraped_at) = ?
            ORDER BY scraped_at ASC
            """,
            (date_str,),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError as exc:
        logger.warning(f"DB query failed: {exc}")
        return []
    finally:
        conn.close()


def export_day(
    date_str: str | None = None,
    db_path: str = DEFAULT_DB_PATH,
    raw_dir: Path = DEFAULT_RAW_DIR,
) -> int:
    """Append new articles for date_str from news.db into JSONL. Returns count added.

    date_str: YYYY-MM-DD (IST). None resolves to today IST.
    """
    if date_str is None:
        date_str = _today_ist()
    raw_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = raw_dir / f"{date_str}.jsonl.gz"

    rows = _fetch_day_from_db(db_path, date_str)
    if not rows:
        logger.info(f"[export] No articles for {date_str} in {db_path}")
        return 0

    existing_links = _load_existing_links(jsonl_path)
    new_rows = [r for r in rows if r["link"] not in existing_links]
    if not new_rows:
        logger.info(f"[export] {date_str}: all {len(rows)} articles already in JSONL")
        return 0

    with gzip.open(jsonl_path, "at", encoding="utf-8") as f:
        for row in new_rows:
            row["exported_at"] = datetime.now(timezone.utc).isoformat()
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    logger.info(f"[export] {date_str}: appended {len(new_rows)} articles → {jsonl_path.name}")
    return len(new_rows)


def run(date_str: str | None = None, db_path: str = DEFAULT_DB_PATH) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    target = date_str or _today_ist()
    count = export_day(target, db_path=db_path)
    print(f"[export-news] {target}: {count} new articles written to india_raw/")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export news.db -> daily JSONL (live path)")
    p.add_argument("--date",    default=None,          help="YYYY-MM-DD (default: today IST)")
    p.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Path to news.db")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run(date_str=args.date, db_path=args.db_path)


if __name__ == "__main__":
    main()
