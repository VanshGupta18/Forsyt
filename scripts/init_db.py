"""
Initialize all PostgreSQL tables.
Run once:  python scripts/init_db.py
"""

import os
import psycopg2
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

PG_DSN = os.getenv("PG_DSN", "postgresql://india_ai:secret@localhost:5432/india_ai_gpr")

DDL = [
    # --- Ingestion ---
    """
    CREATE TABLE IF NOT EXISTS raw_articles (
        id          BIGSERIAL PRIMARY KEY,
        url_hash    CHAR(64)     NOT NULL UNIQUE,
        url         TEXT         NOT NULL,
        headline    TEXT,
        body_text   TEXT,
        source_name TEXT,
        publish_ts  TIMESTAMPTZ,
        gdelt_tone  FLOAT,
        cameo_code  TEXT,
        raw_json    JSONB,
        created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_raw_articles_publish ON raw_articles (publish_ts);
    """,

    # --- Structured events ---
    """
    CREATE TABLE IF NOT EXISTS structured_events (
        id             BIGSERIAL PRIMARY KEY,
        article_id     CHAR(64)   NOT NULL REFERENCES raw_articles(url_hash),
        event_type     TEXT       NOT NULL,
        severity       FLOAT      NOT NULL CHECK (severity BETWEEN 0 AND 1),
        india_exposure FLOAT      NOT NULL CHECK (india_exposure BETWEEN 0 AND 1),
        confidence     FLOAT      NOT NULL CHECK (confidence BETWEEN 0 AND 1),
        actors         TEXT[],
        affected_sectors TEXT[],
        event_date     DATE,
        raw_text       TEXT,
        prompt_version TEXT,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_events_date     ON structured_events (event_date);
    CREATE INDEX IF NOT EXISTS idx_events_type     ON structured_events (event_type);
    CREATE INDEX IF NOT EXISTS idx_events_severity ON structured_events (severity);
    """,

    # --- GPR index ---
    """
    CREATE TABLE IF NOT EXISTS gpr_index (
        index_date         DATE       NOT NULL,
        raw_gpr            FLOAT,
        smoothed_gpr       FLOAT,
        normalized_gpr     FLOAT,
        event_count        INTEGER    DEFAULT 0,
        data_quality_flag  TEXT       DEFAULT 'OK',
        created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (index_date)
    );
    CREATE INDEX IF NOT EXISTS idx_gpr_date ON gpr_index (index_date DESC);
    """,

    # --- ML predictions ---
    """
    CREATE TABLE IF NOT EXISTS ml_predictions (
        id                  BIGSERIAL PRIMARY KEY,
        prediction_date     DATE      NOT NULL,
        model_version       TEXT      NOT NULL,
        signal              TEXT      NOT NULL,
        high_vol_probability FLOAT    NOT NULL,
        top_features        JSONB,
        feature_values      JSONB,
        created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (prediction_date, model_version)
    );
    CREATE INDEX IF NOT EXISTS idx_pred_date ON ml_predictions (prediction_date DESC);
    """,

    # --- Dead letter queue ---
    """
    CREATE TABLE IF NOT EXISTS dead_letter_queue (
        id          BIGSERIAL PRIMARY KEY,
        article_url TEXT,
        url_hash    CHAR(64),
        error_stage TEXT,
        error_msg   TEXT,
        raw_body    TEXT,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,

    # --- Ticker sector map ---
    """
    CREATE TABLE IF NOT EXISTS ticker_sector_map (
        ticker      TEXT PRIMARY KEY,
        sector      TEXT NOT NULL,
        exchange    TEXT DEFAULT 'NSE',
        updated_at  TIMESTAMPTZ DEFAULT NOW()
    );
    """,

    # --- Sector GPR betas ---
    """
    CREATE TABLE IF NOT EXISTS sector_gpr_betas (
        id             BIGSERIAL PRIMARY KEY,
        sector         TEXT    NOT NULL,
        gpr_beta       FLOAT   NOT NULL,
        r_squared      FLOAT,
        n_obs          INTEGER,
        computed_date  DATE    NOT NULL DEFAULT CURRENT_DATE,
        UNIQUE (sector, computed_date)
    );
    """,
]


def init_db():
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = True
    with conn.cursor() as cur:
        for i, stmt in enumerate(DDL, 1):
            try:
                cur.execute(stmt)
                logger.info(f"DDL block {i}/{len(DDL)} applied OK")
            except Exception as e:
                logger.error(f"DDL block {i} failed: {e}")
                raise
    conn.close()
    logger.info("All tables created successfully.")


if __name__ == "__main__":
    init_db()
