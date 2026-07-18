"""
Database module — PostgreSQL backend for production, SQLite fallback for local dev.
Handles article storage with deduplication and querying.

Usage:
  - Set DATABASE_URL env var to a PostgreSQL connection string for production.
  - If DATABASE_URL is not set, falls back to local SQLite (news.db).
"""

import os
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Detect which backend to use
USE_POSTGRES = bool(DATABASE_URL)

# ---------------------------------------------------------------------------
# PostgreSQL backend (psycopg2)
# ---------------------------------------------------------------------------
if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

    # Fix Render/Supabase URLs that start with "postgres://" instead of "postgresql://"
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    def get_connection():
        """Get a PostgreSQL connection."""
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn

    def init_db():
        """Create tables if they don't exist (PostgreSQL)."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                link TEXT UNIQUE NOT NULL,
                time TEXT,
                language TEXT DEFAULT 'en',
                scraped_at TIMESTAMP DEFAULT NOW()
            );
        """)
        # Create indexes (IF NOT EXISTS is supported in PostgreSQL 9.5+)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_source ON articles(source);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_language ON articles(language);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scraped_at ON articles(scraped_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_link ON articles(link);")

        # Per-run, per-source dedup stats (how much of each RSS feed was already stored)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scrape_runs (
                id SERIAL PRIMARY KEY,
                run_at TIMESTAMP NOT NULL,
                source TEXT NOT NULL,
                fetched_count INTEGER NOT NULL,
                new_count INTEGER NOT NULL,
                duplicate_count INTEGER NOT NULL
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scrape_runs_source ON scrape_runs(source);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scrape_runs_run_at ON scrape_runs(run_at);")

        conn.commit()
        cur.close()
        conn.close()
        logger.info("PostgreSQL database initialized")

    # Source code to language mapping
    HINDI_SOURCES = {"AU", "BBC", "OI", "LH", "N18"}
    ENGLISH_SOURCES = {"IT", "TH", "TOI", "NDTV", "TIE"}

    def insert_articles(articles):
        """Insert articles, skipping duplicates (based on link). PostgreSQL version.

        Returns (inserted_total, per_source_stats) where per_source_stats maps
        source code -> {"new": n, "duplicate": n}, so callers can see how much
        of each RSS feed was already stored (i.e. how "stale" the feed was).
        """
        conn = get_connection()
        cur = conn.cursor()
        inserted = 0
        stats = {}

        for article in articles:
            source = article.get("source", "")
            lang = "hi" if source in HINDI_SOURCES else "en"
            source_stats = stats.setdefault(source, {"new": 0, "duplicate": 0})

            try:
                cur.execute(
                    """INSERT INTO articles (title, content, source, link, time, language)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON CONFLICT (link) DO NOTHING""",
                    (
                        article.get("title", ""),
                        article.get("content", ""),
                        source,
                        article.get("link", ""),
                        article.get("time", ""),
                        lang,
                    ),
                )
                if cur.rowcount > 0:
                    inserted += 1
                    source_stats["new"] += 1
                else:
                    source_stats["duplicate"] += 1
            except Exception as e:
                logger.warning(f"Error inserting article: {e}")
                conn.rollback()
                continue

        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Inserted {inserted} new articles, skipped {len(articles) - inserted} duplicates")
        return inserted, stats

    def get_articles(source="ALL", limit=500):
        """Retrieve articles from the database (PostgreSQL)."""
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        source = source.upper()

        if source == "ALL":
            cur.execute(
                "SELECT title, content, source, link, time, language FROM articles ORDER BY scraped_at DESC LIMIT %s",
                (limit,),
            )
        else:
            cur.execute(
                "SELECT title, content, source, link, time, language FROM articles WHERE source = %s ORDER BY scraped_at DESC LIMIT %s",
                (source, limit),
            )

        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in rows]

    def get_stats():
        """Get article counts per source (PostgreSQL)."""
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT source, language, COUNT(*) as count FROM articles GROUP BY source, language ORDER BY count DESC"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in rows]

    def log_scrape_run(stats, run_at):
        """Persist per-source fetched/new/duplicate counts for one scrape run (PostgreSQL)."""
        conn = get_connection()
        cur = conn.cursor()
        for source, counts in stats.items():
            fetched = counts["new"] + counts["duplicate"]
            cur.execute(
                """INSERT INTO scrape_runs (run_at, source, fetched_count, new_count, duplicate_count)
                   VALUES (%s, %s, %s, %s, %s)""",
                (run_at, source, fetched, counts["new"], counts["duplicate"]),
            )
        conn.commit()
        cur.close()
        conn.close()

    def get_scrape_runs(source=None, limit=50):
        """Retrieve recent scrape-run dedup stats (PostgreSQL)."""
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if source:
            cur.execute(
                """SELECT run_at, source, fetched_count, new_count, duplicate_count
                   FROM scrape_runs WHERE source = %s ORDER BY run_at DESC LIMIT %s""",
                (source.upper(), limit),
            )
        else:
            cur.execute(
                """SELECT run_at, source, fetched_count, new_count, duplicate_count
                   FROM scrape_runs ORDER BY run_at DESC LIMIT %s""",
                (limit,),
            )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in rows]

    def get_total_count():
        """Get total number of articles in the database (PostgreSQL)."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM articles")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count

    def cleanup_old_articles(keep_days=7):
        """Delete articles older than `keep_days` days (PostgreSQL)."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM articles WHERE scraped_at < NOW() - INTERVAL '%s days'",
            (keep_days,),
        )
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} articles older than {keep_days} days")
        return deleted


# ---------------------------------------------------------------------------
# SQLite fallback (local development)
# ---------------------------------------------------------------------------
else:
    import sqlite3

    DB_PATH = os.environ.get("NEWS_DB_PATH", os.path.join(os.path.dirname(__file__), "news.db"))

    def get_connection():
        """Get a SQLite connection with WAL mode for better concurrent reads."""
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def init_db():
        """Create tables if they don't exist (SQLite)."""
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

            CREATE TABLE IF NOT EXISTS scrape_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at TIMESTAMP NOT NULL,
                source TEXT NOT NULL,
                fetched_count INTEGER NOT NULL,
                new_count INTEGER NOT NULL,
                duplicate_count INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_scrape_runs_source ON scrape_runs(source);
            CREATE INDEX IF NOT EXISTS idx_scrape_runs_run_at ON scrape_runs(run_at);
        """)
        conn.commit()
        conn.close()
        logger.info(f"SQLite database initialized at {DB_PATH}")

    # Source code to language mapping
    HINDI_SOURCES = {"AU", "BBC", "OI", "LH", "N18"}
    ENGLISH_SOURCES = {"IT", "TH", "TOI", "NDTV", "TIE"}

    def insert_articles(articles):
        """Insert articles, skipping duplicates (based on link). SQLite version.

        Returns (inserted_total, per_source_stats) where per_source_stats maps
        source code -> {"new": n, "duplicate": n}, so callers can see how much
        of each RSS feed was already stored (i.e. how "stale" the feed was).
        """
        conn = get_connection()
        inserted = 0
        skipped = 0
        stats = {}

        for article in articles:
            source = article.get("source", "")
            lang = "hi" if source in HINDI_SOURCES else "en"
            source_stats = stats.setdefault(source, {"new": 0, "duplicate": 0})

            try:
                cur = conn.execute(
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
                # cur.rowcount reflects this INSERT OR IGNORE only (0 = ignored duplicate,
                # 1 = inserted) — unlike conn.total_changes, which is cumulative for the
                # whole connection and would misreport every row after the first insert.
                if cur.rowcount > 0:
                    inserted += 1
                    source_stats["new"] += 1
                else:
                    skipped += 1
                    source_stats["duplicate"] += 1
            except sqlite3.IntegrityError:
                skipped += 1
                source_stats["duplicate"] += 1
            except Exception as e:
                logger.warning(f"Error inserting article: {e}")
                skipped += 1

        conn.commit()
        conn.close()
        logger.info(f"Inserted {inserted} new articles, skipped {skipped} duplicates")
        return inserted, stats

    def get_articles(source="ALL", limit=500):
        """Retrieve articles from the database (SQLite)."""
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
        """Get article counts per source (SQLite)."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT source, language, COUNT(*) as count FROM articles GROUP BY source, language ORDER BY count DESC"
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def log_scrape_run(stats, run_at):
        """Persist per-source fetched/new/duplicate counts for one scrape run (SQLite)."""
        conn = get_connection()
        for source, counts in stats.items():
            fetched = counts["new"] + counts["duplicate"]
            conn.execute(
                """INSERT INTO scrape_runs (run_at, source, fetched_count, new_count, duplicate_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (run_at, source, fetched, counts["new"], counts["duplicate"]),
            )
        conn.commit()
        conn.close()

    def get_scrape_runs(source=None, limit=50):
        """Retrieve recent scrape-run dedup stats (SQLite)."""
        conn = get_connection()
        if source:
            rows = conn.execute(
                """SELECT run_at, source, fetched_count, new_count, duplicate_count
                   FROM scrape_runs WHERE source = ? ORDER BY run_at DESC LIMIT ?""",
                (source.upper(), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT run_at, source, fetched_count, new_count, duplicate_count
                   FROM scrape_runs ORDER BY run_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_total_count():
        """Get total number of articles in the database (SQLite)."""
        conn = get_connection()
        count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        conn.close()
        return count

    def cleanup_old_articles(keep_days=7):
        """Delete articles older than `keep_days` days (SQLite)."""
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
