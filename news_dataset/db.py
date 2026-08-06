"""PostgreSQL storage for scraped geopolitical news articles."""

from __future__ import annotations

import json
import logging
import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required (PostgreSQL only).")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

HINDI_SOURCES = {"AU", "BBC", "OI", "LH", "N18"}


def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def init_db():
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_source ON articles(source);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_language ON articles(language);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_scraped_at ON articles(scraped_at);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_link ON articles(link);")

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


def get_total_count():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM articles")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


def insert_geo_article(article):
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
                json.dumps(article.get("matched_keywords", [])),
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
    params.append(limit)
    cur.execute(
        f"""SELECT * FROM articles WHERE {' AND '.join(clauses)}
            ORDER BY published_at DESC NULLS LAST LIMIT %s""",
        params,
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(row) for row in rows]


def record_geo_seen_links(rows, seen_at):
    if not rows:
        return
    values = [
        (row["link"], row["source_code"], row["tier"], row.get("published_at"), seen_at)
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


def get_articles_pending_nlp(limit, model_version, start=None, end=None, reprocess=False):
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


init_db()
