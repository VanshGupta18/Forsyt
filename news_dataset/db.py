"""PostgreSQL storage for scraped geopolitical news articles."""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)

try:
    from gpr_index.scripts.paths import INDIA_GPR_INDEX_START
except ImportError:  # pragma: no cover - tests without repo root on path
    INDIA_GPR_INDEX_START = date.fromisoformat(
        os.environ.get("INDIA_GPR_INDEX_START", "2026-08-09")
    )


def _index_start(start=None):
    """Clamp query start to the India news GPR index floor."""
    if start is None:
        return INDIA_GPR_INDEX_START
    if isinstance(start, date):
        day = start
    else:
        day = date.fromisoformat(str(start)[:10])
    return max(day, INDIA_GPR_INDEX_START)

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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gpr_daily (
            date DATE PRIMARY KEY,
            gpr_index REAL NOT NULL,
            gpr_7ma REAL,
            gpr_30ma REAL,
            gpr_acts_index REAL,
            gpr_threats_index REAL,
            total_articles INTEGER,
            positive_share REAL,
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS corridor_daily (
            date DATE NOT NULL,
            corridor TEXT NOT NULL,
            corridor_name TEXT,
            corridor_risk REAL,
            threat_index REAL,
            energy_risk REAL,
            goods_risk REAL,
            raw_ratio REAL,
            updated_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (date, corridor)
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_corridor_daily_date ON corridor_daily(date);")
    cur.execute("ALTER TABLE corridor_daily ADD COLUMN IF NOT EXISTS corridor_hit_count INTEGER;")
    cur.execute("ALTER TABLE corridor_daily ADD COLUMN IF NOT EXISTS gpr_sum REAL;")
    cur.execute("ALTER TABLE corridor_daily ADD COLUMN IF NOT EXISTS energy_exposure REAL;")
    cur.execute("ALTER TABLE corridor_daily ADD COLUMN IF NOT EXISTS goods_exposure REAL;")
    cur.execute("ALTER TABLE corridor_daily ADD COLUMN IF NOT EXISTS corridor_risk_7ma REAL;")
    cur.execute("ALTER TABLE corridor_daily ADD COLUMN IF NOT EXISTS corridor_risk_30ma REAL;")
    cur.execute("ALTER TABLE corridor_daily ADD COLUMN IF NOT EXISTS score_status TEXT;")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dual_signal_daily (
            as_of DATE PRIMARY KEY,
            payload JSONB NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id SERIAL PRIMARY KEY,
            run_at TIMESTAMP NOT NULL DEFAULT NOW(),
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            details JSONB
        );
    """)
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
             AND duplicate_of IS NULL
             AND COALESCE(published_at, scraped_at) >= %s
             AND COALESCE(published_at, scraped_at) < %s""",
        (start, end),
    )
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


_NLP_PENDING_SQL = (
    "(nlp_extracted_at IS NULL "
    "OR nlp_tone_neg IS NULL OR nlp_tone_polarity IS NULL "
    "OR nlp_gcam IS NULL OR nlp_gcam = '' "
    "OR nlp_model_version IS NULL "
    "OR nlp_model_version <> %s)"
)


def count_articles_pending_nlp(model_version, start=None, end=None, reprocess=False) -> int:
    conn = get_connection()
    cur = conn.cursor()
    clauses = ["tier IS NOT NULL", "duplicate_of IS NULL"]
    params: list = []
    if not reprocess:
        clauses.append(_NLP_PENDING_SQL)
        params.append(model_version)
    if start is not None:
        clauses.append("COALESCE(published_at, scraped_at) >= %s")
        params.append(start)
    if end is not None:
        clauses.append("COALESCE(published_at, scraped_at) < %s")
        params.append(end)
    cur.execute(
        f"SELECT COUNT(*) FROM articles WHERE {' AND '.join(clauses)}",
        params,
    )
    count = int(cur.fetchone()[0])
    cur.close()
    conn.close()
    return count


def list_tier_article_days() -> list[date]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT DISTINCT DATE(COALESCE(published_at AT TIME ZONE 'UTC', scraped_at AT TIME ZONE 'UTC'))
           FROM articles
           WHERE tier IS NOT NULL AND duplicate_of IS NULL
           ORDER BY 1"""
    )
    days = []
    for row in cur.fetchall():
        val = row[0]
        days.append(val if isinstance(val, date) else date.fromisoformat(str(val)))
    cur.close()
    conn.close()
    return days


def get_gpr_articles(start, end):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT * FROM articles
           WHERE tier IS NOT NULL
             AND duplicate_of IS NULL
             AND nlp_extracted_at IS NOT NULL
             AND nlp_tone_neg IS NOT NULL
             AND nlp_tone_polarity IS NOT NULL
             AND nlp_gcam IS NOT NULL AND nlp_gcam <> ''
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
    clauses = ["tier IS NOT NULL", "duplicate_of IS NULL"]
    params = []
    if not reprocess:
        clauses.append(_NLP_PENDING_SQL)
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


def upsert_gpr_daily(rows):
    if not rows:
        return 0
    conn = get_connection()
    cur = conn.cursor()
    try:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO gpr_daily
                   (date, gpr_index, gpr_7ma, gpr_30ma, gpr_acts_index,
                    gpr_threats_index, total_articles, positive_share, updated_at)
               VALUES %s
               ON CONFLICT (date) DO UPDATE SET
                   gpr_index = EXCLUDED.gpr_index,
                   gpr_7ma = EXCLUDED.gpr_7ma,
                   gpr_30ma = EXCLUDED.gpr_30ma,
                   gpr_acts_index = EXCLUDED.gpr_acts_index,
                   gpr_threats_index = EXCLUDED.gpr_threats_index,
                   total_articles = EXCLUDED.total_articles,
                   positive_share = EXCLUDED.positive_share,
                   updated_at = NOW()""",
            rows,
        )
        conn.commit()
        return len(rows)
    finally:
        cur.close()
        conn.close()


def delete_gpr_daily_before(cutoff) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM gpr_daily WHERE date < %s", (cutoff,))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return deleted


def delete_corridor_daily_before(cutoff) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM corridor_daily WHERE date < %s", (cutoff,))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return deleted


def get_gpr_current():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT * FROM gpr_daily
           WHERE date >= %s
           ORDER BY date DESC LIMIT 1""",
        (INDIA_GPR_INDEX_START,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_gpr_history(start=None, end=None, limit=500):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    clauses, params = ["date >= %s"], [_index_start(start)]
    if end:
        clauses.append("date <= %s")
        params.append(end)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    cur.execute(
        f"""SELECT date, gpr_index, gpr_7ma, gpr_30ma, gpr_acts_index,
                   gpr_threats_index, total_articles, positive_share
            FROM gpr_daily {where}
            ORDER BY date DESC LIMIT %s""",
        params,
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(row) for row in rows]


def upsert_corridor_daily(rows):
    if not rows:
        return 0
    conn = get_connection()
    cur = conn.cursor()
    try:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO corridor_daily
                   (date, corridor, corridor_name, corridor_risk, threat_index,
                    energy_risk, goods_risk, raw_ratio, corridor_hit_count, gpr_sum,
                    energy_exposure, goods_exposure, corridor_risk_7ma, corridor_risk_30ma,
                    score_status, updated_at)
               VALUES %s
               ON CONFLICT (date, corridor) DO UPDATE SET
                   corridor_name = EXCLUDED.corridor_name,
                   corridor_risk = EXCLUDED.corridor_risk,
                   threat_index = EXCLUDED.threat_index,
                   energy_risk = EXCLUDED.energy_risk,
                   goods_risk = EXCLUDED.goods_risk,
                   raw_ratio = EXCLUDED.raw_ratio,
                   corridor_hit_count = EXCLUDED.corridor_hit_count,
                   gpr_sum = EXCLUDED.gpr_sum,
                   energy_exposure = EXCLUDED.energy_exposure,
                   goods_exposure = EXCLUDED.goods_exposure,
                   corridor_risk_7ma = EXCLUDED.corridor_risk_7ma,
                   corridor_risk_30ma = EXCLUDED.corridor_risk_30ma,
                   score_status = EXCLUDED.score_status,
                   updated_at = NOW()""",
            rows,
        )
        conn.commit()
        return len(rows)
    finally:
        cur.close()
        conn.close()


def get_corridors_latest():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT MAX(date) AS latest FROM corridor_daily WHERE date >= %s",
        (INDIA_GPR_INDEX_START,),
    )
    latest = cur.fetchone()["latest"]
    if not latest:
        cur.close()
        conn.close()
        return None, []
    cur.execute(
        """SELECT corridor, corridor_name, corridor_risk, corridor_risk_7ma,
                  corridor_risk_30ma, threat_index, energy_risk, goods_risk,
                  raw_ratio, corridor_hit_count, gpr_sum, energy_exposure,
                  goods_exposure, score_status, date
           FROM corridor_daily WHERE date = %s
           ORDER BY corridor_risk DESC NULLS LAST, corridor ASC""",
        (latest,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return latest, [dict(row) for row in rows]


def get_corridor_history(corridor_id, start=None, end=None, limit=500):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    clauses, params = ["corridor = %s", "date >= %s"], [corridor_id, _index_start(start)]
    if end:
        clauses.append("date <= %s")
        params.append(end)
    params.append(limit)
    cur.execute(
        f"""SELECT date, corridor, corridor_name, corridor_risk, corridor_risk_7ma,
                   corridor_risk_30ma, threat_index, energy_risk, goods_risk, raw_ratio,
                   corridor_hit_count, gpr_sum, energy_exposure, goods_exposure, score_status
            FROM corridor_daily
            WHERE {' AND '.join(clauses)}
            ORDER BY date DESC LIMIT %s""",
        params,
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(row) for row in rows]


def get_recent_news(
    limit=100,
    tier=None,
    theme=None,
    corridor=None,
    start=None,
    end=None,
    tagged_only=False,
):
    """Live scraped articles from Postgres. NLP tags optional unless tagged_only."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    clauses = ["tier IS NOT NULL", "duplicate_of IS NULL"]
    params = []
    if tagged_only:
        clauses.append("nlp_extracted_at IS NOT NULL")
    if tier is not None:
        clauses.append("tier = %s")
        params.append(tier)
    if theme:
        clauses.append(
            "(nlp_themes ILIKE %s OR title ILIKE %s OR content ILIKE %s)"
        )
        params.extend([f"%{theme}%"] * 3)
    if corridor:
        clauses.append(
            "(nlp_locations ILIKE %s OR title ILIKE %s OR content ILIKE %s)"
        )
        params.extend([f"%{corridor}%"] * 3)
    if start:
        clauses.append("COALESCE(published_at, scraped_at) >= %s")
        params.append(start)
    if end:
        clauses.append("COALESCE(published_at, scraped_at) < %s")
        params.append(end)
    params.append(limit)
    cur.execute(
        f"""SELECT id, title, source, link, published_at, scraped_at, tier,
                   nlp_themes, nlp_locations, nlp_tone_neg, nlp_tone_polarity,
                   confidence, matched_keywords
            FROM articles
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(published_at, scraped_at) DESC NULLS LAST
            LIMIT %s""",
        params,
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(row) for row in rows]


def upsert_dual_signal(as_of, payload):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO dual_signal_daily (as_of, payload, updated_at)
               VALUES (%s, %s, NOW())
               ON CONFLICT (as_of) DO UPDATE SET
                   payload = EXCLUDED.payload,
                   updated_at = NOW()""",
            (as_of, json.dumps(payload)),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_dual_signal(as_of=None):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if as_of:
        cur.execute("SELECT as_of, payload FROM dual_signal_daily WHERE as_of = %s", (as_of,))
    else:
        cur.execute("SELECT as_of, payload FROM dual_signal_daily ORDER BY as_of DESC LIMIT 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return {"as_of": row["as_of"], **payload}


def log_pipeline_run(stage, status, details=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO pipeline_runs (stage, status, details)
           VALUES (%s, %s, %s)""",
        (stage, status, json.dumps(details or {})),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_last_pipeline_run(stage):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT run_at, status, details FROM pipeline_runs
           WHERE stage = %s ORDER BY run_at DESC LIMIT 1""",
        (stage,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return dict(row)


def _should_run_init_db() -> bool:
    """Skip init in Flask debug reloader parent to avoid concurrent ALTER TABLE deadlocks."""
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        return True
    if os.environ.get("WERKZEUG_SERVER_FD") is None:
        return True
    return False


def _init_db_with_retry() -> None:
    try:
        init_db()
    except psycopg2.errors.DeadlockDetected:
        logger.warning("init_db deadlock on startup; retrying once")
        import time

        time.sleep(0.5)
        init_db()


if _should_run_init_db():
    _init_db_with_retry()
