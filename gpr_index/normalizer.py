"""
Z-score normalization of the GPR smoothed score.

normalized_gpr[t] = (smoothed_score[t] - μ[t]) / σ[t]

μ[t], σ[t] = rolling mean and std over the past 252 TRADING days
             (252 = standard number of trading days per year in finance)

Minimum history: 126 days before Z-score is valid.
"""

import logging
import psycopg2
from datetime import date, timedelta
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

ROLLING_WINDOW_DAYS = 252   # 1 trading year
MIN_HISTORY_DAYS    = 126   # 6 months minimum for reliable Z-score
BLACKOUT_FLAG       = "BLACKOUT"


def fetch_rolling_scores(conn: psycopg2.extensions.connection,
                          target_date: date,
                          window: int = ROLLING_WINDOW_DAYS) -> list:
    """
    Fetch the last N smoothed GPR scores before target_date.
    Excludes BLACKOUT days (media blackouts distort the distribution).
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT smoothed_score
        FROM gpr_index
        WHERE index_date < %s
          AND smoothed_score IS NOT NULL
          AND (data_quality_flag IS NULL OR data_quality_flag != %s)
        ORDER BY index_date DESC
        LIMIT %s
    """, (target_date, BLACKOUT_FLAG, window))
    return [float(r[0]) for r in cur.fetchall()]


def normalize_score(smoothed_score: float,
                    historical_scores: list) -> Tuple[Optional[float], str]:
    """
    Compute Z-score normalization.

    Args:
        smoothed_score: Today's smoothed GPR score
        historical_scores: List of historical smoothed scores (up to 252 values)

    Returns:
        (normalized_gpr, quality_flag)
        quality_flag: "OK", "INSUFFICIENT_HISTORY", or "ZERO_STD"
    """
    n = len(historical_scores)

    if n < MIN_HISTORY_DAYS:
        logger.warning(
            f"Only {n} days of history (need {MIN_HISTORY_DAYS}) — "
            f"returning raw score with INSUFFICIENT_HISTORY flag"
        )
        return smoothed_score, "INSUFFICIENT_HISTORY"

    mu    = sum(historical_scores) / n
    variance = sum((x - mu) ** 2 for x in historical_scores) / n
    sigma = variance ** 0.5

    if sigma < 1e-9:
        logger.warning("Zero standard deviation in history — GPR is constant, check data")
        return 0.0, "ZERO_STD"

    z_score = (smoothed_score - mu) / sigma
    logger.info(
        f"Normalized GPR: ({smoothed_score:.4f} - {mu:.4f}) / {sigma:.4f} = {z_score:.4f}"
        f" (n={n} historical days)"
    )
    return round(z_score, 4), "OK"
