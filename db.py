"""
Database module - SQLite backend for news storage.
Handles article storage with deduplication and querying.
"""

import sqlite3
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("NEWS_DB_PATH", os.path.join(os.path.dirname(__file__), "news.db"))


def get_connection():
    """Get a SQLite connection with WAL mode for better concurrent reads."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT NOT NULL,
            link TEXT UNIQUE NOT NULL,
            time TEXT,
            language TEXT DEFAULT 'en',
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_source ON articles(source);
        CREATE INDEX IF NOT EXISTS idx_language ON articles(language);
        CREATE INDEX IF NOT EXISTS idx_scraped_at ON articles(scraped_at);
        CREATE INDEX IF NOT EXISTS idx_link ON articles(link);
    """)
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


# Source code to language mapping
HINDI_SOURCES = {"AU", "BBC", "OI", "LH", "N18"}
ENGLISH_SOURCES = {"IT", "TH", "TOI", "NDTV", "TIE"}


def insert_articles(articles):
    """Insert articles, skipping duplicates (based on link)."""
    conn = get_connection()
    inserted = 0
    skipped = 0

    for article in articles:
        source = article.get("source", "")
        lang = "hi" if source in HINDI_SOURCES else "en"

        try:
            conn.execute(
                """INSERT OR IGNORE INTO articles (title, content, source, link, time, language)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    article.get("title", ""),
                    article.get("content", ""),
                    source,
                    article.get("link", ""),
                    article.get("time", ""),
                    lang,
                ),
            )
            if conn.total_changes:
                inserted += 1
            else:
                skipped += 1
        except sqlite3.IntegrityError:
            skipped += 1
        except Exception as e:
            logger.warning(f"Error inserting article: {e}")
            skipped += 1

    conn.commit()
    conn.close()
    logger.info(f"Inserted {inserted} new articles, skipped {skipped} duplicates")
    return inserted


def get_articles(source="ALL", limit=500):
    """Retrieve articles from the database."""
    conn = get_connection()
    source = source.upper()

    if source == "ALL":
        rows = conn.execute(
            "SELECT title, content, source, link, time, language FROM articles ORDER BY scraped_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT title, content, source, link, time, language FROM articles WHERE source = ? ORDER BY scraped_at DESC LIMIT ?",
            (source, limit),
        ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def get_stats():
    """Get article counts per source."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT source, language, COUNT(*) as count FROM articles GROUP BY source, language ORDER BY count DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_total_count():
    """Get total number of articles in the database."""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    return count


def cleanup_old_articles(keep_days=7):
    """Delete articles older than `keep_days` days to prevent DB bloat."""
    conn = get_connection()
    deleted = conn.execute(
        "DELETE FROM articles WHERE scraped_at < datetime('now', ?)",
        (f"-{keep_days} days",),
    ).rowcount
    conn.commit()
    conn.close()
    if deleted > 0:
        logger.info(f"Cleaned up {deleted} articles older than {keep_days} days")
    return deleted


# Initialize database on import
init_db()
