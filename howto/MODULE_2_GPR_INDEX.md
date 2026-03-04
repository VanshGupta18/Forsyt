# Module 2 — India AI-GPR Index Builder
## Step-by-Step Build Guide

---

## What This Module Does
Runs once daily at 20:30 IST. Reads all structured events for the day from PostgreSQL, applies a scoring formula, exponential decay weighting, rolling smoothing, and Z-score normalization to produce the India AI-GPR score. Stores the result in PostgreSQL and writes the latest value to Redis.

---

## Prerequisites
- Module 1 must be running and populating `structured_events` in PostgreSQL
- At least **126 days of historical events** are needed before GPR normalization is meaningful (the first 126 days use a simplified raw score)
- For initial backfill, you need to run GDELT historical data through Module 1 first (see Step 2 below)
- Python packages needed (add to requirements.txt):

```bash
pip install pandas numpy scipy psycopg2-binary redis python-dotenv
```

---

## Step 1 — Create the GPR Index PostgreSQL Table

```sql
-- Connect to india_gpr database and run:

CREATE TABLE gpr_index (
    id                  BIGSERIAL PRIMARY KEY,
    index_date          DATE UNIQUE NOT NULL,
    raw_score           NUMERIC(10,4),          -- sum of contributions before decay
    weighted_score      NUMERIC(10,4),          -- after exponential decay
    smoothed_score      NUMERIC(10,4),          -- after 3-day rolling avg
    normalized_gpr      NUMERIC(8,4),           -- final Z-score value
    rolling_mean_252d   NUMERIC(10,4),          -- rolling mean used for normalization
    rolling_std_252d    NUMERIC(10,4),          -- rolling std used for normalization
    event_count         INTEGER,                -- # events that contributed
    data_quality_flag   VARCHAR(30) DEFAULT 'OK',  -- 'OK' | 'BLACKOUT_SUSPECTED' | 'LOW_CONFIDENCE'
    computed_at         TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_gpr_index_date ON gpr_index (index_date);
```

**Verify:** `\d gpr_index` should show all columns.

---

## Step 2 — Backfill Historical Data (CRITICAL)

The GPR index needs ~1 year of historical data before normalization is meaningful. You have two options:

### Option A — GDELT Historical Backfill (Recommended)
GDELT has historical data going back to 1979. Run the ingestion pipeline against past dates.

```python
# scripts/historical_backfill.py

import requests
from datetime import date, timedelta
import time

def fetch_gdelt_historical(target_date: date):
    """
    Pull GDELT data for a specific historical date.
    GDELT stores 15-min update files at a predictable URL pattern.
    """
    # GDELT stores daily GKG files at:
    # http://data.gdeltproject.org/gkg/YYYYMMDD.gkg.csv.zip
    
    date_str = target_date.strftime("%Y%m%d")
    url = f"http://data.gdeltproject.org/gkg/{date_str}.gkg.csv.zip"
    
    response = requests.get(url, timeout=60)
    if response.status_code == 200:
        # Process the GKG CSV (contains all articles for that day)
        # Filter for India-relevant rows, then run through Module 1 pipeline
        return response.content
    return None

# Backfill 2015-01-01 to 2019-12-31
start_date = date(2015, 1, 1)
end_date = date(2019, 12, 31)
current = start_date

while current <= end_date:
    print(f"Backfilling {current}...")
    fetch_gdelt_historical(current)   
    time.sleep(2)   # Be respectful of GDELT servers
    current += timedelta(days=1)
```

### Option B — Use Caldara-Iacoviello GPR as Seed Data (Faster for Testing)
Download the published India GPR series from https://www.matteoiacoviello.com/gpr.htm and import it as a seed for the `gpr_index` table. This lets you test Module 3 immediately while Module 1 builds live data.

```python
# scripts/seed_from_caldara.py
import pandas as pd
import psycopg2

# Download: https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xlsx
df = pd.read_excel("data_gpr_daily_recent.xlsx")

# Filter for India sub-index and date range
# Column: GPRI (India-specific GPR)
india_gpr = df[['date', 'GPRI']].rename(columns={'GPRI': 'normalized_gpr'})
india_gpr['index_date'] = pd.to_datetime(india_gpr['date']).dt.date

# Insert as historical seed
conn = psycopg2.connect(...)
cur = conn.cursor()
for _, row in india_gpr.iterrows():
    cur.execute("""
        INSERT INTO gpr_index (index_date, normalized_gpr, data_quality_flag)
        VALUES (%s, %s, 'SEED_CALDARA')
        ON CONFLICT (index_date) DO NOTHING
    """, (row['index_date'], row['normalized_gpr']))
conn.commit()
```

---

## Step 3 — Write the Aggregator (`gpr_index/aggregator.py`)

The aggregator reads today's structured events and computes `raw_score[t]`.

```python
# gpr_index/aggregator.py

import logging
import psycopg2
from datetime import date
from typing import List, Dict

logger = logging.getLogger(__name__)


def fetch_events_for_date(conn: psycopg2.extensions.connection, 
                           target_date: date) -> List[Dict]:
    """
    Fetch all structured events for a given date from PostgreSQL.
    Returns list of dicts with severity, india_exposure, confidence, publish_ts.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            se.severity,
            se.india_exposure,
            se.confidence,
            ra.publish_ts,
            se.event_type,
            se.id
        FROM structured_events se
        JOIN raw_articles ra ON se.raw_article_id = ra.id
        WHERE se.event_date = %s
          AND se.severity IS NOT NULL
          AND se.india_exposure IS NOT NULL
          AND se.confidence IS NOT NULL
    """, (target_date,))
    
    columns = ['severity', 'india_exposure', 'confidence', 
               'publish_ts', 'event_type', 'id']
    events = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    
    logger.info(f"Fetched {len(events)} events for {target_date}")
    return events


def compute_raw_score(events: List[Dict]) -> float:
    """
    Compute the raw daily score as the sum of event contributions.
    
    Formula: raw_score[t] = Σ (severity_i × india_exposure_i × confidence_i)
    
    Why multiplicative:
    - If india_exposure = 0 → contribution = 0 (event doesn't affect India)
    - If confidence = 0 → contribution = 0 (unreliable extraction)
    - All three dimensions must be elevated for a high contribution
    
    Returns 0.0 if no events for the day.
    """
    if not events:
        return 0.0
    
    total = 0.0
    for event in events:
        contribution = (
            float(event['severity']) * 
            float(event['india_exposure']) * 
            float(event['confidence'])
        )
        total += contribution
        logger.debug(
            f"Event {event['id']}: {event['event_type']} | "
            f"contribution = {event['severity']:.3f} × "
            f"{event['india_exposure']:.3f} × "
            f"{event['confidence']:.3f} = {contribution:.4f}"
        )
    
    logger.info(f"Raw score: {total:.4f} from {len(events)} events")
    return total
```

---

## Step 4 — Write the Decay Smoother (`gpr_index/decay_smoother.py`)

Applies intra-day exponential decay (more recent articles weighted higher) and a 3-day rolling average.

```python
# gpr_index/decay_smoother.py

import math
import logging
import psycopg2
from datetime import date, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)

# λ = 0.10 → half-life of ln(2)/0.10 ≈ 6.93 hours
# Calibrated to Indian news cycle — most market-moving news breaks within 6-8h
LAMBDA = 0.10


def compute_decay_weight(publish_ts, collection_ts=None) -> float:
    """
    Compute decay weight for an article based on hours since publication.
    
    w_i = exp(-λ × hours_since_publication)
    
    Uses publication time, NOT hours since midnight.
    Rationale: A story breaking at 23:00 should NOT be penalized for being late in the day.
    
    Args:
        publish_ts: datetime when article was published
        collection_ts: datetime when collection ran (defaults to now)
    
    Returns:
        float in (0, 1] — weight to apply to event contribution
    """
    from datetime import datetime, timezone
    
    if collection_ts is None:
        # At EOD computation (20:30 IST), use that as reference
        collection_ts = publish_ts.replace(hour=20, minute=30, second=0)
    
    # Hours between publication and collection
    delta = collection_ts - publish_ts.replace(tzinfo=publish_ts.tzinfo)
    hours = max(0.0, delta.total_seconds() / 3600)
    
    weight = math.exp(-LAMBDA * hours)
    return weight


def compute_weighted_score(events: List[Dict]) -> float:
    """
    Apply decay weights to event contributions and sum.
    
    weighted_score[t] = Σ (contribution_i × decay_weight_i)
    where contribution_i = severity_i × india_exposure_i × confidence_i
    """
    if not events:
        return 0.0
    
    total = 0.0
    for event in events:
        contribution = (
            float(event['severity']) * 
            float(event['india_exposure']) * 
            float(event['confidence'])
        )
        weight = compute_decay_weight(event['publish_ts'])
        total += contribution * weight
    
    logger.info(f"Weighted score: {total:.4f}")
    return total


def compute_smoothed_score(conn: psycopg2.extensions.connection,
                            target_date: date,
                            todays_weighted_score: float) -> float:
    """
    Apply 3-day backward rolling average.
    
    smoothed_score[t] = mean(weighted_score[t], weighted_score[t-1], weighted_score[t-2])
    
    Handles missing days (holidays, outages) by using the available data points.
    """
    cur = conn.cursor()
    
    # Fetch last 2 days of weighted scores
    cur.execute("""
        SELECT index_date, weighted_score
        FROM gpr_index
        WHERE index_date >= %s AND index_date < %s
        ORDER BY index_date DESC
        LIMIT 2
    """, (target_date - timedelta(days=2), target_date))
    
    past_scores = [row[1] for row in cur.fetchall() if row[1] is not None]
    cur.close()
    
    all_scores = [todays_weighted_score] + past_scores
    smoothed = sum(float(s) for s in all_scores) / len(all_scores)
    
    logger.info(
        f"Smoothing: today={todays_weighted_score:.4f}, "
        f"past={[float(s) for s in past_scores]} → smoothed={smoothed:.4f}"
    )
    return smoothed
```

---

## Step 5 — Write the Normalizer (`gpr_index/normalizer.py`)

```python
# gpr_index/normalizer.py

import logging
import numpy as np
import psycopg2
from datetime import date, timedelta
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# 252 trading days ≈ 1 calendar year (standard finance convention)
NORMALIZATION_WINDOW_DAYS = 252

# Minimum days of history before Z-score normalization is reliable
MIN_HISTORY_DAYS = 126


def fetch_rolling_scores(conn: psycopg2.extensions.connection,
                          target_date: date,
                          window_days: int = 252) -> list:
    """
    Fetch the last `window_days` smoothed scores before target_date.
    Used to compute rolling mean and std for Z-score normalization.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT smoothed_score
        FROM gpr_index
        WHERE index_date >= %s 
          AND index_date < %s
          AND smoothed_score IS NOT NULL
          AND data_quality_flag != 'BLACKOUT_SUSPECTED'  -- exclude unreliable days
        ORDER BY index_date DESC
        LIMIT %s
    """, (
        target_date - timedelta(days=window_days + 30),   # +30 buffer for holidays
        target_date,
        window_days
    ))
    
    scores = [float(row[0]) for row in cur.fetchall()]
    cur.close()
    return scores


def normalize_score(conn: psycopg2.extensions.connection,
                     target_date: date,
                     smoothed_score: float) -> Tuple[float, float, float]:
    """
    Z-score normalize the smoothed score using 252-day rolling statistics.
    
    GPR[t] = (smoothed_score[t] - μ[t]) / σ[t]
    
    Returns:
        (normalized_gpr, rolling_mean, rolling_std)
    
    Falls back to scaled raw score if insufficient history (< 126 days).
    """
    historical_scores = fetch_rolling_scores(conn, target_date)
    
    if len(historical_scores) < MIN_HISTORY_DAYS:
        # Not enough history for reliable Z-score
        # Use a simple 0-1 scaled score as placeholder
        logger.warning(
            f"Only {len(historical_scores)} days of history "
            f"(need {MIN_HISTORY_DAYS}). Using scaled score."
        )
        # Return smoothed score as-is (will be normalized properly once we have enough data)
        return smoothed_score, 0.0, 1.0
    
    scores_array = np.array(historical_scores)
    mu = float(np.mean(scores_array))
    sigma = float(np.std(scores_array, ddof=1))   # sample std, not population
    
    # Prevent division by zero on extremely quiet periods
    if sigma < 1e-6:
        logger.warning("Rolling std near zero — GPR index has no variance. Clamping to 0.")
        return 0.0, mu, sigma
    
    normalized = (smoothed_score - mu) / sigma
    
    logger.info(
        f"Normalization: smoothed={smoothed_score:.4f}, "
        f"mu={mu:.4f}, sigma={sigma:.4f}, GPR={normalized:.4f}"
    )
    
    return normalized, mu, sigma
```

---

## Step 6 — Write the Validator (`gpr_index/validator.py`)

Validates the GPR index spiked correctly at known major events.

```python
# gpr_index/validator.py

import logging
import psycopg2
from datetime import date, timedelta
from scipy import stats
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Ground-truth: India GPR should spike (> 2.0) within ±2 days of these events
KNOWN_SPIKE_EVENTS = [
    {"name": "26/11 Mumbai Attacks",    "date": date(2008, 11, 26), "min_gpr": 2.0},
    {"name": "Uri Attack",              "date": date(2016, 9, 18),  "min_gpr": 2.0},
    {"name": "Pulwama + Balakot",       "date": date(2019, 2, 14),  "min_gpr": 2.5},
    {"name": "Galwan Valley Clash",     "date": date(2020, 6, 15),  "min_gpr": 2.0},
]


def check_spike(conn, event: Dict) -> Tuple[bool, float]:
    """
    Check if GPR spiked above threshold within ±2 days of a known event.
    Returns (passed, max_gpr_in_window).
    """
    cur = conn.cursor()
    window_start = event['date'] - timedelta(days=2)
    window_end   = event['date'] + timedelta(days=2)
    
    cur.execute("""
        SELECT MAX(normalized_gpr)
        FROM gpr_index
        WHERE index_date BETWEEN %s AND %s
    """, (window_start, window_end))
    
    row = cur.fetchone()
    cur.close()
    
    if row[0] is None:
        logger.warning(f"No GPR data around {event['name']} ({event['date']})")
        return False, 0.0
    
    max_gpr = float(row[0])
    passed = max_gpr >= event['min_gpr']
    status = "PASS ✓" if passed else "FAIL ✗"
    
    logger.info(
        f"Spike check [{status}] {event['name']}: "
        f"max GPR in window = {max_gpr:.3f} "
        f"(threshold: {event['min_gpr']:.1f})"
    )
    
    return passed, max_gpr


def compute_benchmark_correlation(conn, 
                                   benchmark_series: List[Tuple[date, float]]) -> float:
    """
    Compute Pearson r between our GPR and Caldara-Iacoviello India benchmark.
    
    Args:
        benchmark_series: List of (date, gpr_value) from C&I dataset
    
    Returns:
        Pearson r (target: > 0.65)
    """
    if not benchmark_series:
        logger.warning("No benchmark data provided — skipping correlation check")
        return 0.0
    
    benchmark_dates = [d for d, _ in benchmark_series]
    benchmark_values = [v for _, v in benchmark_series]
    
    # Fetch our GPR for the same dates
    cur = conn.cursor()
    cur.execute("""
        SELECT index_date, normalized_gpr
        FROM gpr_index
        WHERE index_date = ANY(%s)
          AND normalized_gpr IS NOT NULL
        ORDER BY index_date
    """, ([d for d in benchmark_dates],))
    
    our_data = {row[0]: float(row[1]) for row in cur.fetchall()}
    cur.close()
    
    # Align on common dates
    common_dates = [d for d in benchmark_dates if d in our_data]
    
    if len(common_dates) < 30:
        logger.warning(f"Only {len(common_dates)} overlapping dates — correlation unreliable")
        return 0.0
    
    our_values = [our_data[d] for d in common_dates]
    benchmark_aligned = [benchmark_values[benchmark_dates.index(d)] for d in common_dates]
    
    r, p_value = stats.pearsonr(our_values, benchmark_aligned)
    
    status = "PASS ✓" if r >= 0.65 else "FAIL ✗"
    logger.info(
        f"Benchmark correlation [{status}]: "
        f"r={r:.4f} (p={p_value:.4f}) over {len(common_dates)} common days. "
        f"Target: r > 0.65"
    )
    
    return r


def run_full_validation(conn) -> Dict:
    """Run all validation checks and return a summary dict."""
    results = {"spike_checks": [], "benchmark_correlation": None}
    
    all_spikes_passed = True
    for event in KNOWN_SPIKE_EVENTS:
        passed, max_gpr = check_spike(conn, event)
        results["spike_checks"].append({
            "event": event['name'],
            "passed": passed,
            "max_gpr": max_gpr,
            "threshold": event['min_gpr']
        })
        if not passed:
            all_spikes_passed = False
    
    results["all_spikes_passed"] = all_spikes_passed
    return results
```

---

## Step 7 — Write the Daily Runner (`gpr_index/run_daily.py`)

This is the main entry point that ties Steps 3–6 together.

```python
# gpr_index/run_daily.py

import os
import json
import logging
import psycopg2
import redis as redis_lib
from datetime import date, datetime

from gpr_index.aggregator import fetch_events_for_date, compute_raw_score
from gpr_index.decay_smoother import compute_weighted_score, compute_smoothed_score
from gpr_index.normalizer import normalize_score
from gpr_index.validator import run_full_validation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BLACKOUT_THRESHOLD_PCT = 0.20   # Event count < 20% of 30-day avg = suspected blackout


def run_gpr_index_for_date(target_date: date = None) -> dict:
    """
    Build the India AI-GPR index for `target_date`.
    Defaults to today if not specified.
    """
    if target_date is None:
        target_date = date.today()

    logger.info(f"=== Building GPR index for {target_date} ===")

    conn = psycopg2.connect(
        host=os.environ['POSTGRES_HOST'],
        port=os.environ['POSTGRES_PORT'],
        dbname=os.environ['POSTGRES_DB'],
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD']
    )
    r = redis_lib.Redis(
        host=os.environ['REDIS_HOST'],
        port=int(os.environ['REDIS_PORT']),
        db=0,
        decode_responses=True
    )

    # Step 1: Fetch today's events
    events = fetch_events_for_date(conn, target_date)
    event_count = len(events)

    # Step 2: Detect media blackout
    data_quality_flag = "OK"
    if event_count == 0:
        data_quality_flag = "NO_EVENTS"
        logger.warning(f"No events for {target_date} — checking for blackout")
    else:
        # Check vs 30-day average
        cur = conn.cursor()
        cur.execute("""
            SELECT AVG(event_count) 
            FROM gpr_index 
            WHERE index_date >= %s AND index_date < %s
        """, (target_date.replace(day=1), target_date))
        avg_30d = cur.fetchone()[0]
        cur.close()
        
        if avg_30d and event_count < avg_30d * BLACKOUT_THRESHOLD_PCT:
            data_quality_flag = "BLACKOUT_SUSPECTED"
            logger.warning(
                f"Possible media blackout: {event_count} events "
                f"vs 30-day avg {avg_30d:.0f}"
            )

    # Step 3: Compute scores
    raw_score      = compute_raw_score(events)
    weighted_score = compute_weighted_score(events)
    smoothed_score = compute_smoothed_score(conn, target_date, weighted_score)

    # Step 4: If blackout, carry forward yesterday's GPR value
    if data_quality_flag == "BLACKOUT_SUSPECTED":
        cur = conn.cursor()
        cur.execute("""
            SELECT normalized_gpr FROM gpr_index 
            WHERE index_date < %s 
            ORDER BY index_date DESC LIMIT 1
        """, (target_date,))
        row = cur.fetchone()
        cur.close()
        normalized_gpr = float(row[0]) if row else 0.0
        rolling_mean, rolling_std = 0.0, 1.0
        logger.info(f"Blackout: carrying forward GPR = {normalized_gpr:.4f}")
    else:
        normalized_gpr, rolling_mean, rolling_std = normalize_score(
            conn, target_date, smoothed_score
        )

    # Step 5: Sanity checks
    assert not (normalized_gpr != normalized_gpr), "GPR is NaN!"   # NaN check
    assert -10 < normalized_gpr < 10, f"GPR out of range: {normalized_gpr}"

    # Step 6: Store in PostgreSQL
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO gpr_index 
            (index_date, raw_score, weighted_score, smoothed_score,
             normalized_gpr, rolling_mean_252d, rolling_std_252d,
             event_count, data_quality_flag)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (index_date) DO UPDATE SET
            raw_score        = EXCLUDED.raw_score,
            weighted_score   = EXCLUDED.weighted_score,
            smoothed_score   = EXCLUDED.smoothed_score,
            normalized_gpr   = EXCLUDED.normalized_gpr,
            rolling_mean_252d = EXCLUDED.rolling_mean_252d,
            rolling_std_252d  = EXCLUDED.rolling_std_252d,
            event_count       = EXCLUDED.event_count,
            data_quality_flag = EXCLUDED.data_quality_flag,
            computed_at       = now()
    """, (
        target_date, raw_score, weighted_score, smoothed_score,
        normalized_gpr, rolling_mean, rolling_std,
        event_count, data_quality_flag
    ))
    conn.commit()

    # Step 7: Update Redis hot cache
    payload = json.dumps({
        "date": str(target_date),
        "gpr_score": round(normalized_gpr, 4),
        "event_count": event_count,
        "data_quality_flag": data_quality_flag,
        "updated_at": datetime.utcnow().isoformat() + "Z"
    })
    r.set("india_gpr:latest", payload, ex=86400)   # 24h TTL

    logger.info(
        f"=== GPR index for {target_date}: "
        f"raw={raw_score:.3f}, weighted={weighted_score:.3f}, "
        f"smoothed={smoothed_score:.3f}, normalized={normalized_gpr:.4f} "
        f"[{data_quality_flag}] ==="
    )

    conn.close()
    r.close()
    
    return {
        "date": str(target_date),
        "normalized_gpr": normalized_gpr,
        "event_count": event_count,
        "data_quality_flag": data_quality_flag
    }


if __name__ == "__main__":
    result = run_gpr_index_for_date()
    print(result)
```

---

## Step 8 — Schedule the Daily Runner

Add a cron job inside the container that fires at 20:30 IST every weekday:

```python
# gpr_index/scheduler.py

from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
import pytz

from gpr_index.run_daily import run_gpr_index_for_date
from gpr_index.validator import run_full_validation
import psycopg2, os

IST = pytz.timezone('Asia/Kolkata')

def daily_job():
    from datetime import date
    result = run_gpr_index_for_date(date.today())
    print(f"Daily GPR computed: {result}")

scheduler = BlockingScheduler(timezone=IST)

# Run every day at 20:30 IST (including weekends — GDELT runs 24/7)
scheduler.add_job(daily_job, 'cron', hour=20, minute=30)

print("GPR index scheduler started (fires 20:30 IST daily)")
scheduler.start()
```

---

## Step 9 — Test the Module

```bash
# Run manually for today
python -m gpr_index.run_daily

# Check the output in PostgreSQL
psql -U gpr_user -d india_gpr -c "
  SELECT index_date, raw_score, weighted_score, 
         smoothed_score, normalized_gpr, event_count, data_quality_flag
  FROM gpr_index 
  ORDER BY index_date DESC 
  LIMIT 10;
"

# Check Redis hot cache
redis-cli GET india_gpr:latest
```

**Expected output:**
```
index_date  | raw_score | weighted | smoothed | normalized_gpr | event_count | flag
2026-03-04  |    3.2100 |   2.8470 |   2.5340 |         1.4300 |          14 | OK
```

---

## Step 10 — Run the Spike Validation

Once you have historical data loaded (from Step 2 backfill), validate the index:

```python
# From Python shell or notebook

import psycopg2, os
from gpr_index.validator import run_full_validation

conn = psycopg2.connect(
    host=os.environ['POSTGRES_HOST'],
    dbname=os.environ['POSTGRES_DB'],
    user=os.environ['POSTGRES_USER'],
    password=os.environ['POSTGRES_PASSWORD']
)

results = run_full_validation(conn)

print("=== Spike Validation Results ===")
for check in results['spike_checks']:
    status = "PASS ✓" if check['passed'] else "FAIL ✗"
    print(f"[{status}] {check['event']}: max GPR = {check['max_gpr']:.3f} (threshold: {check['threshold']})")

print(f"\nAll spikes passed: {results['all_spikes_passed']}")
```

---

## Step 11 — Plot the GPR Time Series

Run this in `notebooks/01_caldara_validation.ipynb` to visualize the index:

```python
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

conn = psycopg2.connect(...)

df = pd.read_sql("""
    SELECT index_date, normalized_gpr, event_count, data_quality_flag
    FROM gpr_index
    WHERE normalized_gpr IS NOT NULL
    ORDER BY index_date
""", conn)

df['index_date'] = pd.to_datetime(df['index_date'])

fig, ax = plt.subplots(figsize=(16, 5))
ax.plot(df['index_date'], df['normalized_gpr'], color='navy', linewidth=0.8, label='India AI-GPR')
ax.axhline(y=2.0, color='red', linestyle='--', alpha=0.6, label='2σ threshold')
ax.fill_between(df['index_date'], df['normalized_gpr'], 2.0,
                where=(df['normalized_gpr'] > 2.0), color='red', alpha=0.2)

# Annotate known events
events = [
    (pd.Timestamp('2008-11-26'), '26/11 Mumbai'),
    (pd.Timestamp('2016-09-18'), 'Uri Attack'),
    (pd.Timestamp('2019-02-14'), 'Pulwama'),
    (pd.Timestamp('2020-06-15'), 'Galwan'),
]
for event_date, label in events:
    ax.axvline(x=event_date, color='orange', linestyle=':', alpha=0.8)
    ax.annotate(label, xy=(event_date, 3.0), fontsize=8, rotation=45, color='orange')

ax.set_xlabel('Date')
ax.set_ylabel('India AI-GPR (Z-score)')
ax.set_title('India AI-GPR Index — Normalized Daily Score')
ax.legend()
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig('docs/gpr_timeseries.png', dpi=150)
plt.show()
```

---

## Verification Checklist

- [ ] `gpr_index` table has rows for every day Module 1 was running
- [ ] `normalized_gpr` values are in a reasonable range (−3 to +5 for most days, > 2 for crisis periods)
- [ ] `data_quality_flag = 'OK'` for the vast majority of rows
- [ ] Redis `india_gpr:latest` key exists and returns valid JSON
- [ ] Spike validation: all 4 known events show GPR > 2.0 in their window
- [ ] No NaN values in `normalized_gpr` column
- [ ] The GPR time series **visually** shows elevated values during known conflict periods

---

## Common Errors & Fixes

| Error | Cause | Fix |
|---|---|---|
| `normalized_gpr` is always 0.0 | Fewer than 126 days of history | Run backfill (Step 2) before validating |
| GPR spikes not showing for Pulwama | GDELT data missing for that period | Pull from GDELT historical files for Feb 2019 |
| `AssertionError: GPR is NaN` | `rolling_std` is 0 during early days | Handled by the near-zero sigma check in normalizer.py |
| Redis key not updating | Redis connection failing silently | Check `REDIS_HOST` env var and Redis container health |
| GPR consistently negative | Baseline period had unusually high risk (e.g., COVID) | Consider excluding 2020–2021 from normalization window |
