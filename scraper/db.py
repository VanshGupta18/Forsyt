"""SQLite backend for live news storage.

Port of origin/news_scraper db.py — schema and logic unchanged.
Path resolved via NEWS_DB_PATH env var (defaults to data/india_db/news.db).
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent
DB_PATH: str = os.environ.get(
    "NEWS_DB_PATH",
    str(_REPO_ROOT / "data" / "india_db" / "news.db"),
)

HINDI_SOURCES   = frozenset({"AU", "BBC", "OI", "LH", "N18"})
ENGLISH_SOURCES = frozenset({"IT", "TH", "TOI", "NDTV", "TIE"})


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            content    TEXT NOT NULL,
            source     TEXT NOT NULL,
            link       TEXT UNIQUE NOT NULL,
            time       TEXT,
            language   TEXT DEFAULT 'en',
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_source     ON articles(source);
        CREATE INDEX IF NOT EXISTS idx_language   ON articles(language);
        CREATE INDEX IF NOT EXISTS idx_scraped_at ON articles(scraped_at);
        CREATE INDEX IF NOT EXISTS idx_link       ON articles(link);
    """)
    conn.commit()
    conn.close()
    logger.info(f"DB initialised at {DB_PATH}")


def insert_articles(articles: list[dict]) -> int:
    conn = get_connection()
    inserted = 0
    for art in articles:
        source = art.get("source", "")
        lang   = "hi" if source in HINDI_SOURCES else "en"
        try:
            before = conn.total_changes
            conn.execute(
                "INSERT OR IGNORE INTO articles (title, content, source, link, time, language) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    art.get("title", ""),
                    art.get("content", ""),
                    source,
                    art.get("link", ""),
                    art.get("time", ""),
                    lang,
                ),
            )
            if conn.total_changes > before:
                inserted += 1
        except sqlite3.Error as exc:
            logger.debug(f"Insert skipped ({exc}) — {art.get('link', '')[:60]}")
    conn.commit()
    conn.close()
    return inserted


def get_articles(source: str = "all") -> list[dict]:
    conn = get_connection()
    if source == "all":
        rows = conn.execute(
            "SELECT * FROM articles ORDER BY scraped_at DESC LIMIT 500"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM articles WHERE source = ? ORDER BY scraped_at DESC LIMIT 200",
            (source.upper(),),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_total_count() -> int:
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    return n


def get_stats() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT source, language, COUNT(*) AS count FROM articles GROUP BY source, language"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cleanup_old_articles(keep_days: int = 7) -> int:
    conn = get_connection()
    result = conn.execute(
        "DELETE FROM articles WHERE scraped_at < datetime('now', ?)",
        (f"-{keep_days} days",),
    )
    deleted = result.rowcount
    conn.commit()
    conn.close()
    if deleted:
        logger.info(f"Cleanup: removed {deleted} articles older than {keep_days} days")
    return deleted
