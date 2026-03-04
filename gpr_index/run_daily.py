"""
Daily GPR index builder orchestrator.
Triggered at 20:30 IST daily by scheduler.py.
"""

import os
import json
import logging
import psycopg2
import redis as redis_lib
from datetime import date, datetime, timezone

from gpr_index.aggregator import fetch_events_for_date, compute_raw_score
from gpr_index.decay_smoother import compute_weighted_score, compute_smoothed_score
from gpr_index.normalizer import fetch_rolling_scores, normalize_score
from gpr_index.validator import BLACKOUT_THRESHOLD_PCT

logger = logging.getLogger(__name__)


def _get_db_conn():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"]
    )


def _get_redis():
    return redis_lib.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        decode_responses=True
    )


def _detect_blackout(event_count: int,
                     conn: psycopg2.extensions.connection) -> bool:
    """
    Return True if today's event count is < BLACKOUT_THRESHOLD_PCT of the
    30-day rolling average. Indicates a media blackout, not a truly calm day.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT AVG(event_count)
        FROM gpr_index
        WHERE index_date >= CURRENT_DATE - INTERVAL '30 days'
          AND data_quality_flag != 'BLACKOUT'
          AND event_count IS NOT NULL
    """)
    row = cur.fetchone()
    if not row or not row[0]:
        return False
    avg_30d = float(row[0])
    if avg_30d == 0:
        return False
    is_blackout = event_count < BLACKOUT_THRESHOLD_PCT * avg_30d
    if is_blackout:
        logger.warning(
            f"BLACKOUT detected: today={event_count} events, "
            f"30d_avg={avg_30d:.1f}, threshold={BLACKOUT_THRESHOLD_PCT * avg_30d:.1f}"
        )
    return is_blackout


def run_gpr_index_for_date(target_date: date = None) -> dict:
    """
    Full GPR index computation pipeline for a single date.
    Writes result to PostgreSQL and Redis.
    """
    if target_date is None:
        target_date = date.today()

    logger.info(f"=== GPR index build for {target_date} ===")

    conn = _get_db_conn()
    r    = _get_redis()

    try:
        # 1. Fetch events
        events = fetch_events_for_date(conn, target_date)
        event_count = len(events)
        logger.info(f"Fetched {event_count} events for {target_date}")

        # 2. Detect media blackout
        is_blackout = _detect_blackout(event_count, conn)

        if is_blackout:
            # Carry forward yesterday's GPR rather than producing a spurious 0
            cur = conn.cursor()
            cur.execute("""
                SELECT normalized_gpr, smoothed_score, weighted_score
                FROM gpr_index
                WHERE index_date < %s AND normalized_gpr IS NOT NULL
                ORDER BY index_date DESC LIMIT 1
            """, (target_date,))
            prev = cur.fetchone()
            result = {
                "index_date":      str(target_date),
                "normalized_gpr":  float(prev[0]) if prev else 0.0,
                "smoothed_score":  float(prev[1]) if prev else 0.0,
                "weighted_score":  float(prev[2]) if prev else 0.0,
                "raw_score":       0.0,
                "event_count":     event_count,
                "data_quality_flag": "BLACKOUT_CARRIED_FORWARD",
            }
        else:
            # 3. Compute scores
            raw_score, _          = compute_raw_score(events)
            weighted_score        = compute_weighted_score(events)
            smoothed_score        = compute_smoothed_score(conn, target_date, weighted_score)

            # 4. Normalize
            historical            = fetch_rolling_scores(conn, target_date)
            normalized_gpr, flag  = normalize_score(smoothed_score, historical)

            result = {
                "index_date":      str(target_date),
                "raw_score":       raw_score,
                "weighted_score":  weighted_score,
                "smoothed_score":  smoothed_score,
                "normalized_gpr":  normalized_gpr,
                "event_count":     event_count,
                "data_quality_flag": flag,
            }

        logger.info(
            f"GPR result: normalized={result['normalized_gpr']:.4f} "
            f"quality={result['data_quality_flag']}"
        )

        # 5. Upsert to PostgreSQL
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO gpr_index
                (index_date, raw_score, weighted_score, smoothed_score,
                 normalized_gpr, event_count, data_quality_flag, computed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (index_date) DO UPDATE SET
                raw_score         = EXCLUDED.raw_score,
                weighted_score    = EXCLUDED.weighted_score,
                smoothed_score    = EXCLUDED.smoothed_score,
                normalized_gpr    = EXCLUDED.normalized_gpr,
                event_count       = EXCLUDED.event_count,
                data_quality_flag = EXCLUDED.data_quality_flag,
                computed_at       = now()
        """, (
            target_date,
            result["raw_score"],
            result["weighted_score"],
            result["smoothed_score"],
            result["normalized_gpr"],
            result["event_count"],
            result["data_quality_flag"],
        ))
        conn.commit()

        # 6. Update Redis hot cache
        cache_payload = json.dumps({
            "index_date":    str(target_date),
            "normalized_gpr": result["normalized_gpr"],
            "smoothed_gpr":   result["smoothed_score"],
            "data_quality":   result["data_quality_flag"],
            "event_count":    result["event_count"],
            "computed_at":    datetime.now(timezone.utc).isoformat(),
        })
        r.set("india_gpr:latest", cache_payload, ex=86400)

        logger.info(f"GPR written to PostgreSQL + Redis for {target_date}")
        return result

    finally:
        conn.close()
        r.close()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(message)s")
    result = run_gpr_index_for_date()
    print(result)
