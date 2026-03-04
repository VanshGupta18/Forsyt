"""
GPR index validation:
1. Spike assertions against known historical events
2. Pearson correlation with Caldara-Iacoviello India benchmark
"""

import logging
import psycopg2
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)

# Known high-GPR events with known dates.
# GPR must exceed 2.0 (σ) within ±2 days of each event date.
KNOWN_SPIKE_EVENTS = [
    {"name": "2008 Mumbai Attacks (26/11)",     "date": date(2008, 11, 26)},
    {"name": "2016 Uri Surgical Strikes",        "date": date(2016, 9, 29)},
    {"name": "2019 Pulwama Attack",              "date": date(2019, 2, 14)},
    {"name": "2020 Galwan Valley Clash",         "date": date(2020, 6, 15)},
]
SPIKE_THRESHOLD   = 2.0
SPIKE_WINDOW_DAYS = 2

# Acceptable Pearson r threshold vs Caldara-Iacoviello
BENCHMARK_CORR_THRESHOLD = 0.60

BLACKOUT_THRESHOLD_PCT = 0.20   # < 20% of 30-day avg event count → BLACKOUT


def check_spike(conn: psycopg2.extensions.connection,
                event: Dict) -> Dict:
    """
    Verify GPR exceeded SPIKE_THRESHOLD within ±SPIKE_WINDOW_DAYS of a known event.
    """
    event_date   = event["date"]
    window_start = event_date - timedelta(days=SPIKE_WINDOW_DAYS)
    window_end   = event_date + timedelta(days=SPIKE_WINDOW_DAYS)

    cur = conn.cursor()
    cur.execute("""
        SELECT MAX(normalized_gpr) as max_gpr, MAX(index_date) as peak_date
        FROM gpr_index
        WHERE index_date BETWEEN %s AND %s
          AND normalized_gpr IS NOT NULL
    """, (window_start, window_end))

    row = cur.fetchone()
    max_gpr    = float(row[0]) if row and row[0] else None
    peak_date  = row[1] if row else None

    passed = max_gpr is not None and max_gpr >= SPIKE_THRESHOLD
    result = {
        "event_name":        event["name"],
        "expected_spike_by": str(window_end),
        "max_gpr_in_window": round(max_gpr, 4) if max_gpr else None,
        "peak_date":         str(peak_date) if peak_date else None,
        "threshold":         SPIKE_THRESHOLD,
        "passed":            passed,
    }
    status = "PASS" if passed else "FAIL"
    logger.info(f"Spike check [{status}]: {event['name']} → max_gpr={max_gpr}")
    return result


def compute_benchmark_correlation(conn: psycopg2.extensions.connection,
                                   caldara_series: Optional[Dict[date, float]] = None
                                  ) -> Optional[float]:
    """
    Compute Pearson r between our normalized_gpr and the
    Caldara-Iacoviello India GPR (IGPR) monthly series.

    Returns Pearson r, or None if insufficient overlapping data.
    """
    if caldara_series is None:
        logger.info("No Caldara series provided — skipping benchmark correlation")
        return None

    cur = conn.cursor()
    cur.execute("""
        SELECT index_date, normalized_gpr
        FROM gpr_index
        WHERE normalized_gpr IS NOT NULL
        ORDER BY index_date
    """)
    our_data = {row[0]: float(row[1]) for row in cur.fetchall()}

    # Match on month-year (Caldara is monthly)
    our_monthly = {}
    for d, v in our_data.items():
        month_key = date(d.year, d.month, 1)
        if month_key not in our_monthly:
            our_monthly[month_key] = []
        our_monthly[month_key].append(v)
    # Average daily values within each month
    our_monthly = {k: sum(v) / len(v) for k, v in our_monthly.items()}

    # Find overlap
    common_months = sorted(set(our_monthly.keys()) & set(caldara_series.keys()))
    if len(common_months) < 12:
        logger.warning(f"Only {len(common_months)} overlapping months — need 12 for correlation")
        return None

    our_vals    = [our_monthly[m]       for m in common_months]
    bench_vals  = [caldara_series[m]    for m in common_months]

    r, p_value = scipy_stats.pearsonr(our_vals, bench_vals)
    logger.info(
        f"Caldara-Iacoviello correlation: r={r:.4f} p={p_value:.4f} "
        f"(n={len(common_months)} months, threshold={BENCHMARK_CORR_THRESHOLD})"
    )
    return round(r, 4)


def run_full_validation(conn: psycopg2.extensions.connection) -> Dict:
    """Run all validation checks and return a summary report."""
    logger.info("=== Running GPR validation ===")

    spike_results = [check_spike(conn, ev) for ev in KNOWN_SPIKE_EVENTS]
    spike_pass_rate = sum(1 for r in spike_results if r["passed"]) / len(spike_results)

    corr = compute_benchmark_correlation(conn)

    report = {
        "spike_checks":    spike_results,
        "spike_pass_rate": round(spike_pass_rate, 2),
        "benchmark_corr":  corr,
        "overall_valid":   (
            spike_pass_rate >= 0.75 and
            (corr is None or corr >= BENCHMARK_CORR_THRESHOLD)
        )
    }

    status = "VALID" if report["overall_valid"] else "INVALID"
    logger.info(f"=== Validation {status}: spike_pass={spike_pass_rate:.0%} corr={corr} ===")
    return report
