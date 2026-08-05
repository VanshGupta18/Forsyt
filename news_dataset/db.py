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

        # ---- Geopolitical ingestion pipeline: extra columns on the shared articles table ----
        cur.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS tier INTEGER;")
        cur.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS confidence TEXT;")
        cur.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS matched_keywords TEXT;")
        cur.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS duplicate_of INTEGER REFERENCES articles(id);")
        cur.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS published_at TIMESTAMP;")
        cur.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS nlp_themes TEXT;")
        cur.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS nlp_tone_neg REAL;")
        cur.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS nlp_tone_polarity REAL;")
        cur.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS nlp_gcam TEXT;")
        cur.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS nlp_locations TEXT;")
        cur.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS nlp_model_version TEXT;")
        cur.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS nlp_extracted_at TIMESTAMP;")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_tier ON articles(tier);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_duplicate_of ON articles(duplicate_of);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS geo_feed_health (
                source_code TEXT PRIMARY KEY,
                last_success TIMESTAMP,
                last_attempt TIMESTAMP,
                last_error TEXT,
                consecutive_failures INTEGER NOT NULL DEFAULT 0
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS geo_cycle_stats (
                id SERIAL PRIMARY KEY,
                run_at TIMESTAMP NOT NULL,
                tier INTEGER NOT NULL,
                source_code TEXT NOT NULL,
                fetched_count INTEGER NOT NULL,
                ingested_count INTEGER NOT NULL,
                discarded_count INTEGER NOT NULL
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_geo_cycle_stats_run_at ON geo_cycle_stats(run_at);")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS geo_seen_links (
                link TEXT PRIMARY KEY,
                source_code TEXT NOT NULL,
                tier INTEGER NOT NULL,
                published_at TIMESTAMPTZ,
                first_seen_at TIMESTAMPTZ NOT NULL
            );
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_geo_seen_links_observed_at "
            "ON geo_seen_links ((COALESCE(published_at, first_seen_at)));"
        )

        conn.commit()
        cur.close()
        conn.close()
        logger.info("PostgreSQL database initialized")

    # Source code to language mapping
    HINDI_SOURCES = {"AU", "BBC", "OI", "LH", "N18"}
    ENGLISH_SOURCES = {"IT", "TH", "TOI", "NDTV", "TIE"}


    def get_total_count():
        """Get total number of articles in the database (PostgreSQL)."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM articles")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count

    # ---- Geopolitical ingestion pipeline (PostgreSQL) — writes into `articles` ----

    def insert_geo_article(article):
        """Insert one geo-pipeline article into the shared `articles` table.
        Returns the new row id, or None if the link already existed (duplicate
        link, not a fuzzy-title duplicate)."""
        import json as _json

        source_code = article["source_code"]
        lang = "hi" if source_code in HINDI_SOURCES else "en"

        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """INSERT INTO articles
                       (title, content, source, link, time, language,
                        tier, confidence, matched_keywords, duplicate_of, published_at, scraped_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (link) DO NOTHING
                   RETURNING id""",
                (
                    article["title"], article.get("description", ""), source_code,
                    article["link"], article.get("published_at_raw", ""), lang,
                    article["tier"], article["confidence"],
                    _json.dumps(article.get("matched_keywords", [])),
                    article.get("duplicate_of"), article.get("published_at"),
                    article["ingested_at"],
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return row[0] if row else None
        finally:
            cur.close()
            conn.close()

    def get_recent_geo_articles(since):
        """Fetch canonical (non-duplicate) geo articles published since `since`,
        for fuzzy-dedup comparison against newly fetched candidates."""
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT id, title, published_at FROM articles
               WHERE tier IS NOT NULL AND published_at >= %s AND duplicate_of IS NULL
               ORDER BY published_at ASC""",
            (since,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in rows]

    def get_geo_articles(tier=None, dedup_only=True, limit=500):
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        clauses, params = ["tier IS NOT NULL"], []
        if tier is not None:
            clauses.append("tier = %s")
            params.append(tier)
        if dedup_only:
            clauses.append("duplicate_of IS NULL")
        where = f"WHERE {' AND '.join(clauses)}"
        params.append(limit)
        cur.execute(
            f"""SELECT * FROM articles {where}
                ORDER BY published_at DESC NULLS LAST LIMIT %s""",
            params,
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in rows]

    def record_geo_seen_links(rows, seen_at):
        """Idempotently record every valid URL observed in RSS feeds."""
        if not rows:
            return
        values = [
            (
                row["link"], row["source_code"], row["tier"],
                row.get("published_at"), seen_at,
            )
            for row in rows
        ]
        conn = get_connection()
        cur = conn.cursor()
        try:
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO geo_seen_links
                       (link, source_code, tier, published_at, first_seen_at)
                   VALUES %s
                   ON CONFLICT (link) DO NOTHING""",
                values,
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def count_geo_seen_articles(start, end):
        """Count distinct observed URLs in the half-open datetime range."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT COUNT(*) FROM geo_seen_links
               WHERE COALESCE(published_at, first_seen_at) >= %s
                 AND COALESCE(published_at, first_seen_at) < %s""",
            (start, end),
        )
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count

    def count_geo_ingested_articles(start, end):
        """Count URL-unique tiered articles in the half-open datetime range."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT COUNT(DISTINCT link) FROM articles
               WHERE tier IS NOT NULL
                 AND COALESCE(published_at, scraped_at) >= %s
                 AND COALESCE(published_at, scraped_at) < %s""",
            (start, end),
        )
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count

    def get_gpr_articles(start, end):
        """Return the URL-level, NLP-complete GPR population in a date range."""
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT * FROM articles
               WHERE tier IS NOT NULL
                 AND nlp_extracted_at IS NOT NULL
                 AND nlp_themes IS NOT NULL
                 AND nlp_tone_neg IS NOT NULL
                 AND nlp_tone_polarity IS NOT NULL
                 AND nlp_gcam IS NOT NULL
                 AND nlp_locations IS NOT NULL
                 AND nlp_model_version IS NOT NULL
                 AND COALESCE(published_at, scraped_at) >= %s
                 AND COALESCE(published_at, scraped_at) < %s
               ORDER BY COALESCE(published_at, scraped_at) ASC, id ASC""",
            (start, end),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in rows]

    def get_articles_pending_nlp(
        limit, model_version, start=None, end=None, reprocess=False
    ):
        """Fetch URL-unique geo articles needing NLP extraction."""
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        clauses = ["tier IS NOT NULL"]
        params = []
        if not reprocess:
            clauses.append(
                "(nlp_extracted_at IS NULL OR nlp_themes IS NULL "
                "OR nlp_tone_neg IS NULL OR nlp_tone_polarity IS NULL "
                "OR nlp_gcam IS NULL OR nlp_locations IS NULL "
                "OR nlp_model_version IS NULL "
                "OR nlp_model_version <> %s)"
            )
            params.append(model_version)
        if start is not None:
            clauses.append("COALESCE(published_at, scraped_at) >= %s")
            params.append(start)
        if end is not None:
            clauses.append("COALESCE(published_at, scraped_at) < %s")
            params.append(end)
        params.append(limit)
        cur.execute(
            f"""SELECT id, title, content, published_at FROM articles
                WHERE {' AND '.join(clauses)}
                ORDER BY COALESCE(published_at, scraped_at) ASC, id ASC
                LIMIT %s""",
            params,
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in rows]

    def update_article_nlp(article_id, fields):
        """Update one article's validated NLP fields."""
        allowed = {
            "nlp_themes", "nlp_tone_neg", "nlp_tone_polarity", "nlp_gcam",
            "nlp_locations", "nlp_model_version", "nlp_extracted_at",
        }
        invalid = set(fields) - allowed
        if invalid:
            raise ValueError(f"Unsupported NLP fields: {sorted(invalid)}")
        if not fields:
            return
        conn = get_connection()
        cur = conn.cursor()
        try:
            assignments = ", ".join(f"{name} = %s" for name in fields)
            cur.execute(
                f"UPDATE articles SET {assignments} WHERE id = %s",
                [*fields.values(), article_id],
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def upsert_geo_feed_health(source_code, success, error=None, now=None):
        conn = get_connection()
        cur = conn.cursor()
        if success:
            cur.execute(
                """INSERT INTO geo_feed_health (source_code, last_success, last_attempt, last_error, consecutive_failures)
                   VALUES (%s, %s, %s, NULL, 0)
                   ON CONFLICT (source_code) DO UPDATE SET
                       last_success = EXCLUDED.last_success,
                       last_attempt = EXCLUDED.last_attempt,
                       last_error = NULL,
                       consecutive_failures = 0""",
                (source_code, now, now),
            )
        else:
            cur.execute(
                """INSERT INTO geo_feed_health (source_code, last_success, last_attempt, last_error, consecutive_failures)
                   VALUES (%s, NULL, %s, %s, 1)
                   ON CONFLICT (source_code) DO UPDATE SET
                       last_attempt = EXCLUDED.last_attempt,
                       last_error = EXCLUDED.last_error,
                       consecutive_failures = geo_feed_health.consecutive_failures + 1""",
                (source_code, now, error),
            )
        conn.commit()
        cur.close()
        conn.close()

    def get_geo_feed_health():
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM geo_feed_health")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {row["source_code"]: dict(row) for row in rows}

    def log_geo_cycle_stats(run_at, tier, source_code, fetched, ingested, discarded):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO geo_cycle_stats (run_at, tier, source_code, fetched_count, ingested_count, discarded_count)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (run_at, tier, source_code, fetched, ingested, discarded),
        )
        conn.commit()
        cur.close()
        conn.close()

    def get_geo_cycle_stats(limit=100):
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM geo_cycle_stats ORDER BY run_at DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in rows]


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

            CREATE TABLE IF NOT EXISTS geo_feed_health (
                source_code TEXT PRIMARY KEY,
                last_success TIMESTAMP,
                last_attempt TIMESTAMP,
                last_error TEXT,
                consecutive_failures INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS geo_cycle_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at TIMESTAMP NOT NULL,
                tier INTEGER NOT NULL,
                source_code TEXT NOT NULL,
                fetched_count INTEGER NOT NULL,
                ingested_count INTEGER NOT NULL,
                discarded_count INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_geo_cycle_stats_run_at ON geo_cycle_stats(run_at);

            CREATE TABLE IF NOT EXISTS geo_seen_links (
                link TEXT PRIMARY KEY,
                source_code TEXT NOT NULL,
                tier INTEGER NOT NULL,
                published_at TIMESTAMP,
                first_seen_at TIMESTAMP NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_geo_seen_links_observed_at
                ON geo_seen_links(COALESCE(published_at, first_seen_at));
        """)

        # ---- Geopolitical ingestion pipeline: extra columns on the shared articles table ----
        # SQLite's ALTER TABLE has no "ADD COLUMN IF NOT EXISTS", so check first.
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(articles)")}
        for col_name, col_def in [
            ("tier", "INTEGER"),
            ("confidence", "TEXT"),
            ("matched_keywords", "TEXT"),
            ("duplicate_of", "INTEGER REFERENCES articles(id)"),
            ("published_at", "TIMESTAMP"),
            ("nlp_themes", "TEXT"),
            ("nlp_tone_neg", "REAL"),
            ("nlp_tone_polarity", "REAL"),
            ("nlp_gcam", "TEXT"),
            ("nlp_locations", "TEXT"),
            ("nlp_model_version", "TEXT"),
            ("nlp_extracted_at", "TIMESTAMP"),
        ]:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE articles ADD COLUMN {col_name} {col_def}")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_tier ON articles(tier);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_duplicate_of ON articles(duplicate_of);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);")

        conn.commit()
        conn.close()
        logger.info(f"SQLite database initialized at {DB_PATH}")

    # Source code to language mapping
    HINDI_SOURCES = {"AU", "BBC", "OI", "LH", "N18"}
    ENGLISH_SOURCES = {"IT", "TH", "TOI", "NDTV", "TIE"}


    def get_total_count():
        """Get total number of articles in the database (SQLite)."""
        conn = get_connection()
        count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        conn.close()
        return count

    # ---- Geopolitical ingestion pipeline (SQLite) — writes into `articles` ----

    def insert_geo_article(article):
        """Insert one geo-pipeline article into the shared `articles` table.
        Returns the new row id, or None if the link already existed (duplicate
        link, not a fuzzy-title duplicate)."""
        import json as _json

        source_code = article["source_code"]
        lang = "hi" if source_code in HINDI_SOURCES else "en"

        conn = get_connection()
        try:
            cur = conn.execute(
                """INSERT OR IGNORE INTO articles
                       (title, content, source, link, time, language,
                        tier, confidence, matched_keywords, duplicate_of, published_at, scraped_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    article["title"], article.get("description", ""), source_code,
                    article["link"], article.get("published_at_raw", ""), lang,
                    article["tier"], article["confidence"],
                    _json.dumps(article.get("matched_keywords", [])),
                    article.get("duplicate_of"), article.get("published_at"),
                    article["ingested_at"],
                ),
            )
            conn.commit()
            return cur.lastrowid if cur.rowcount > 0 else None
        finally:
            conn.close()

    def get_recent_geo_articles(since):
        """Fetch canonical (non-duplicate) geo articles published since `since`,
        for fuzzy-dedup comparison against newly fetched candidates."""
        conn = get_connection()
        rows = conn.execute(
            """SELECT id, title, published_at FROM articles
               WHERE tier IS NOT NULL AND published_at >= ? AND duplicate_of IS NULL
               ORDER BY published_at ASC""",
            (since,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_geo_articles(tier=None, dedup_only=True, limit=500):
        conn = get_connection()
        clauses, params = ["tier IS NOT NULL"], []
        if tier is not None:
            clauses.append("tier = ?")
            params.append(tier)
        if dedup_only:
            clauses.append("duplicate_of IS NULL")
        where = f"WHERE {' AND '.join(clauses)}"
        params.append(limit)
        rows = conn.execute(
            f"""SELECT * FROM articles {where}
                ORDER BY published_at DESC LIMIT ?""",
            params,
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def record_geo_seen_links(rows, seen_at):
        """Idempotently record every valid URL observed in RSS feeds."""
        if not rows:
            return
        values = [
            (
                row["link"], row["source_code"], row["tier"],
                row.get("published_at"), seen_at,
            )
            for row in rows
        ]
        conn = get_connection()
        try:
            conn.executemany(
                """INSERT OR IGNORE INTO geo_seen_links
                       (link, source_code, tier, published_at, first_seen_at)
                   VALUES (?, ?, ?, ?, ?)""",
                values,
            )
            conn.commit()
        finally:
            conn.close()

    def count_geo_seen_articles(start, end):
        """Count distinct observed URLs in the half-open datetime range."""
        conn = get_connection()
        count = conn.execute(
            """SELECT COUNT(*) FROM geo_seen_links
               WHERE COALESCE(published_at, first_seen_at) >= ?
                 AND COALESCE(published_at, first_seen_at) < ?""",
            (start, end),
        ).fetchone()[0]
        conn.close()
        return count

    def count_geo_ingested_articles(start, end):
        """Count URL-unique tiered articles in the half-open datetime range."""
        conn = get_connection()
        count = conn.execute(
            """SELECT COUNT(DISTINCT link) FROM articles
               WHERE tier IS NOT NULL
                 AND COALESCE(published_at, scraped_at) >= ?
                 AND COALESCE(published_at, scraped_at) < ?""",
            (start, end),
        ).fetchone()[0]
        conn.close()
        return count

    def get_gpr_articles(start, end):
        """Return the URL-level, NLP-complete GPR population in a date range."""
        conn = get_connection()
        rows = conn.execute(
            """SELECT * FROM articles
               WHERE tier IS NOT NULL
                 AND nlp_extracted_at IS NOT NULL
                 AND nlp_themes IS NOT NULL
                 AND nlp_tone_neg IS NOT NULL
                 AND nlp_tone_polarity IS NOT NULL
                 AND nlp_gcam IS NOT NULL
                 AND nlp_locations IS NOT NULL
                 AND nlp_model_version IS NOT NULL
                 AND COALESCE(published_at, scraped_at) >= ?
                 AND COALESCE(published_at, scraped_at) < ?
               ORDER BY COALESCE(published_at, scraped_at) ASC, id ASC""",
            (start, end),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_articles_pending_nlp(
        limit, model_version, start=None, end=None, reprocess=False
    ):
        """Fetch URL-unique geo articles needing NLP extraction."""
        conn = get_connection()
        clauses = ["tier IS NOT NULL"]
        params = []
        if not reprocess:
            clauses.append(
                "(nlp_extracted_at IS NULL OR nlp_themes IS NULL "
                "OR nlp_tone_neg IS NULL OR nlp_tone_polarity IS NULL "
                "OR nlp_gcam IS NULL OR nlp_locations IS NULL "
                "OR nlp_model_version IS NULL "
                "OR nlp_model_version <> ?)"
            )
            params.append(model_version)
        if start is not None:
            clauses.append("COALESCE(published_at, scraped_at) >= ?")
            params.append(start)
        if end is not None:
            clauses.append("COALESCE(published_at, scraped_at) < ?")
            params.append(end)
        params.append(limit)
        rows = conn.execute(
            f"""SELECT id, title, content, published_at FROM articles
                WHERE {' AND '.join(clauses)}
                ORDER BY COALESCE(published_at, scraped_at) ASC, id ASC
                LIMIT ?""",
            params,
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_article_nlp(article_id, fields):
        """Update one article's validated NLP fields."""
        allowed = {
            "nlp_themes", "nlp_tone_neg", "nlp_tone_polarity", "nlp_gcam",
            "nlp_locations", "nlp_model_version", "nlp_extracted_at",
        }
        invalid = set(fields) - allowed
        if invalid:
            raise ValueError(f"Unsupported NLP fields: {sorted(invalid)}")
        if not fields:
            return
        conn = get_connection()
        try:
            assignments = ", ".join(f"{name} = ?" for name in fields)
            conn.execute(
                f"UPDATE articles SET {assignments} WHERE id = ?",
                [*fields.values(), article_id],
            )
            conn.commit()
        finally:
            conn.close()

    def upsert_geo_feed_health(source_code, success, error=None, now=None):
        conn = get_connection()
        existing = conn.execute(
            "SELECT consecutive_failures FROM geo_feed_health WHERE source_code = ?",
            (source_code,),
        ).fetchone()

        if success:
            conn.execute(
                """INSERT INTO geo_feed_health (source_code, last_success, last_attempt, last_error, consecutive_failures)
                   VALUES (?, ?, ?, NULL, 0)
                   ON CONFLICT(source_code) DO UPDATE SET
                       last_success = excluded.last_success,
                       last_attempt = excluded.last_attempt,
                       last_error = NULL,
                       consecutive_failures = 0""",
                (source_code, now, now),
            )
        else:
            prev_failures = existing["consecutive_failures"] if existing else 0
            conn.execute(
                """INSERT INTO geo_feed_health (source_code, last_success, last_attempt, last_error, consecutive_failures)
                   VALUES (?, NULL, ?, ?, ?)
                   ON CONFLICT(source_code) DO UPDATE SET
                       last_attempt = excluded.last_attempt,
                       last_error = excluded.last_error,
                       consecutive_failures = excluded.consecutive_failures""",
                (source_code, now, error, prev_failures + 1),
            )
        conn.commit()
        conn.close()

    def get_geo_feed_health():
        conn = get_connection()
        rows = conn.execute("SELECT * FROM geo_feed_health").fetchall()
        conn.close()
        return {row["source_code"]: dict(row) for row in rows}

    def log_geo_cycle_stats(run_at, tier, source_code, fetched, ingested, discarded):
        conn = get_connection()
        conn.execute(
            """INSERT INTO geo_cycle_stats (run_at, tier, source_code, fetched_count, ingested_count, discarded_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (run_at, tier, source_code, fetched, ingested, discarded),
        )
        conn.commit()
        conn.close()

    def get_geo_cycle_stats(limit=100):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM geo_cycle_stats ORDER BY run_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]


# Initialize database on import
init_db()
