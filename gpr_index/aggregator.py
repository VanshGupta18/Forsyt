"""
GPR raw score aggregation.
Computes: raw_score[t] = Σ (severity_i × india_exposure_i × confidence_i)
for all structured events on date t.
"""

import logging
import psycopg2
from datetime import date, timedelta
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


def fetch_events_for_date(conn: psycopg2.extensions.connection,
                           target_date: date) -> List[Dict]:
    """
    Load all structured events for the given date from PostgreSQL.
    Includes publish timestamp for decay calculation.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            se.id,
            se.severity,
            se.india_exposure,
            se.confidence,
            se.event_type,
            ra.publish_ts,
            ra.url
        FROM structured_events se
        JOIN raw_articles ra ON se.raw_article_id = ra.id
        WHERE se.event_date = %s
          AND se.severity > 0
          AND se.confidence > 0.3
        ORDER BY ra.publish_ts ASC
    """, (target_date,))
    return [dict(r) for r in cur.fetchall()]


def compute_raw_score(events: List[Dict]) -> Tuple[float, int]:
    """
    Compute the raw (unweighted) GPR score for a day.
    contribution = severity × india_exposure × confidence  (multiplicative)

    Multiplicative design: event only scores high if ALL three are high.
    A severe global event with low india_exposure contributes near-zero.

    Returns: (raw_score, event_count)
    """
    if not events:
        return 0.0, 0

    total = 0.0
    for ev in events:
        contribution = (
            float(ev["severity"]) *
            float(ev["india_exposure"]) *
            float(ev["confidence"])
        )
        total += contribution
        logger.debug(
            f"  Event {ev['id']} ({ev['event_type']}): "
            f"sev={ev['severity']:.2f} × "
            f"india={ev['india_exposure']:.2f} × "
            f"conf={ev['confidence']:.2f} = {contribution:.4f}"
        )

    logger.info(f"Raw score: {total:.4f} from {len(events)} events")
    return round(total, 6), len(events)
