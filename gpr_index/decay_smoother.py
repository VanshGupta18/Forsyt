"""
Exponential decay + 3-day smoothing.

decay_weight_i = exp(-λ × hours_since_publication_i)
λ = 0.10  →  half-life ≈ 6.93 hours

Decay is from PUBLICATION TIME (not midnight), avoiding systematic bias
for articles published at different times of day.
"""

import math
import logging
import psycopg2
from datetime import date, datetime, timezone, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

LAMBDA         = 0.10       # Decay rate constant
SMOOTHING_DAYS = 3          # Rolling average window


def compute_decay_weight(publish_ts_str: Optional[str],
                         reference_ts: Optional[datetime] = None) -> float:
    """
    Compute exponential decay weight for an event.

    weight = exp(-λ × hours_since_publication)

    Args:
        publish_ts_str: ISO 8601 timestamp string (e.g. "2026-03-04T08:14:00Z")
        reference_ts: Reference time for decay calculation (defaults to now UTC)

    Returns:
        Decay weight in (0, 1]. Returns 1.0 if timestamp is missing or future.
    """
    if not publish_ts_str:
        return 1.0   # No timestamp — treat as current event

    if reference_ts is None:
        reference_ts = datetime.now(timezone.utc)

    try:
        # Parse ISO 8601 (handle both with and without 'Z')
        pub_str = publish_ts_str.replace("Z", "+00:00")
        pub_ts = datetime.fromisoformat(pub_str)
        if pub_ts.tzinfo is None:
            pub_ts = pub_ts.replace(tzinfo=timezone.utc)

        hours_since = (reference_ts - pub_ts).total_seconds() / 3600.0

        if hours_since < 0:
            return 1.0   # Future article — treat as current

        weight = math.exp(-LAMBDA * hours_since)
        return round(weight, 6)

    except (ValueError, TypeError) as e:
        logger.warning(f"Could not parse timestamp '{publish_ts_str}': {e}")
        return 1.0


def compute_weighted_score(events: List[Dict]) -> float:
    """
    Apply exponential decay to each event's contribution and sum.

    weighted_score = Σ (contribution_i × decay_weight_i)
    where contribution_i = severity_i × india_exposure_i × confidence_i
    """
    if not events:
        return 0.0

    now_utc = datetime.now(timezone.utc)
    total = 0.0

    for ev in events:
        contribution = (
            float(ev["severity"]) *
            float(ev["india_exposure"]) *
            float(ev["confidence"])
        )
        weight = compute_decay_weight(ev.get("publish_ts"), reference_ts=now_utc)
        total += contribution * weight

    return round(total, 6)


def compute_smoothed_score(conn: psycopg2.extensions.connection,
                            target_date: date,
                            current_weighted_score: float) -> float:
    """
    Compute 3-day rolling mean of weighted scores.
    Fetches previous 2 days from PostgreSQL and averages with today.

    Smoothing reduces day-to-day noise from sporadic news coverage.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT index_date, weighted_score
        FROM gpr_index
        WHERE index_date >= %s AND index_date < %s
          AND weighted_score IS NOT NULL
        ORDER BY index_date DESC
        LIMIT %s
    """, (
        target_date - timedelta(days=SMOOTHING_DAYS - 1),
        target_date,
        SMOOTHING_DAYS - 1
    ))

    rows = cur.fetchall()
    prior_scores = [float(r[1]) for r in rows]
    all_scores   = [current_weighted_score] + prior_scores

    smoothed = sum(all_scores) / len(all_scores)
    logger.debug(
        f"Smoothed score: mean({[round(s, 4) for s in all_scores]}) = {smoothed:.6f}"
    )
    return round(smoothed, 6)
