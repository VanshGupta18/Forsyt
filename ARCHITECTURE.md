# India AI-GPR Platform — System Architecture

---

## Table of Contents
1. [High-Level Overview](#high-level-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Layer-by-Layer Breakdown](#layer-by-layer-breakdown)
4. [Database Schema](#database-schema)
5. [Container Architecture](#container-architecture)
6. [API Gateway Design](#api-gateway-design)
7. [Caching Strategy](#caching-strategy)
8. [Monitoring Infrastructure](#monitoring-infrastructure)
9. [Data Flow (Detailed)](#data-flow-detailed)
10. [Security Design](#security-design)
11. [Scalability Considerations](#scalability-considerations)
12. [Repository Structure](#repository-structure)

---

## High-Level Overview

This platform is a **real-time geopolitical risk intelligence system** purpose-built for India. It ingests live news from GDELT every 15 minutes, uses a two-stage LLM pipeline to extract structured geopolitical events, aggregates them into a proprietary daily risk index (India AI-GPR), and uses that index alongside market data to predict Nifty 50 volatility regimes. Everything is served via REST APIs with sub-500ms latency.

The system has **4 processing modules** and **7 Docker containers**, operating as a continuous pipeline with Redis acting as the hot-path cache for real-time queries.

---

## Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                           DATA SOURCES LAYER                                 ║
║                                                                              ║
║   ┌──────────────────────┐   ┌──────────────────┐   ┌──────────────────┐   ║
║   │    GDELT GKG API     │   │   RSS Feeds      │   │  NewsAPI / etc.  │   ║
║   │  (Primary Source)    │   │  (Supplementary) │   │  (Supplementary) │   ║
║   │                      │   │                  │   │                  │   ║
║   │  Pull every 15 min   │   │  Optional feeds  │   │  Optional APIs   │   ║
║   │  Filter: India +     │   │  for gap-fill    │   │  for redundancy  │   ║
║   │  CAMEO conflict      │   │  during GDELT    │   │  if GDELT is     │   ║
║   │  event codes         │   │  outages         │   │  rate-limited    │   ║
║   └──────────┬───────────┘   └────────┬─────────┘   └────────┬─────────┘   ║
╚══════════════╪══════════════════════════╪══════════════════════╪═════════════╝
               └──────────────────────────┴──────────────────────┘
                                          │
                                          ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║         MODULE 1 — INGESTION + DEDUPLICATION + LLM EXTRACTION               ║
║         [Container 1: ingestion_service]                                     ║
║                                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  STEP 1: INGESTION (gdelt_puller.py)                                │    ║
║  │                                                                     │    ║
║  │  • Scheduler fires every 15 minutes via APScheduler                │    ║
║  │  • HTTP GET to GDELT GKG API with query params:                    │    ║
║  │      - Actor1CountryCode = IND                                      │    ║
║  │      - EventBaseCode = 19 (Use of Force) + CAMEO conflict codes    │    ║
║  │      - SOURCECOUNTRY, TONE filter (negative tone only)             │    ║
║  │  • Fetch article URLs from GKG response                            │    ║
║  │  • HTTP GET each article URL with 10s timeout                      │    ║
║  │  • BeautifulSoup HTML parsing → raw text extraction                │    ║
║  │  • Metadata: url, headline, source, publish_ts, gdelt_event_id     │    ║
║  └─────────────────────────┬───────────────────────────────────────────┘    ║
║                             │                                                ║
║                             ▼                                                ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  STEP 2: CLEANING (cleaner.py)                                      │    ║
║  │                                                                     │    ║
║  │  • Strip HTML tags, CSS, JS                                        │    ║
║  │  • Normalize Unicode (NFKC normalization)                          │    ║
║  │  • Remove boilerplate: nav bars, cookie banners, footer text       │    ║
║  │  • Truncate to first 1,500 tokens (GPT context budget)             │    ║
║  │  • Reject articles < 100 words (likely paywalled/stub pages)       │    ║
║  └─────────────────────────┬───────────────────────────────────────────┘    ║
║                             │                                                ║
║                             ▼                                                ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  STEP 3: DEDUPLICATION (deduplicator.py)                            │    ║
║  │                                                                     │    ║
║  │  Layer 1 — Exact URL match:                                         │    ║
║  │    • SHA-256 hash of normalized URL stored in Redis SET             │    ║
║  │    • O(1) lookup — discard if hash already exists                   │    ║
║  │                                                                     │    ║
║  │  Layer 2 — Near-duplicate detection:                                │    ║
║  │    • Compute MinHash signature of article body (128 permutations)   │    ║
║  │    • LSH (Locality-Sensitive Hashing) bucket lookup in Redis        │    ║
║  │    • Jaccard similarity threshold: 0.80                             │    ║
║  │    • Discard if a similar article was processed within 48h          │    ║
║  │                                                                     │    ║
║  │  Why MinHash over embedding cosine similarity:                      │    ║
║  │    • 10-100x faster for high-volume streams                         │    ║
║  │    • No GPU required                                                │    ║
║  │    • Embedding deduplication reserved for edge cases                │    ║
║  └─────────────────────────┬───────────────────────────────────────────┘    ║
║                             │                                                ║
║                             ▼                                                ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  STEP 4: LLM EXTRACTION (2-Stage Pipeline)                          │    ║
║  │                                                                     │    ║
║  │  Stage 1 — FinBERT Classifier (finbert_classifier.py):             │    ║
║  │    • Model: ProsusAI/finbert (HuggingFace)                        │    ║
║  │    • Input: cleaned article text (first 512 tokens)               │    ║
║  │    • Output: {positive, negative, neutral} sentiment label        │    ║
║  │    • Routing rule:                                                  │    ║
║  │        negative → proceed to Stage 2                               │    ║
║  │        positive / neutral → discard (not a risk event)            │    ║
║  │    • Estimated cost reduction: ~60-70% fewer GPT-4o-mini calls    │    ║
║  │                                                                     │    ║
║  │  Stage 2 — GPT-4o-mini Extraction (gpt_extractor.py):             │    ║
║  │    • Model: gpt-4o-mini (OpenAI API, JSON mode enabled)           │    ║
║  │    • Prompt version: tracked in DB (prompt_version field)         │    ║
║  │    • Temperature: 0.0 (deterministic output)                      │    ║
║  │    • Max retries: 3 (exponential backoff on 429/500)              │    ║
║  │    • Fallback: if JSON parse fails 3× → route to dead_letter_queue│    ║
║  │    • Response schema validated via Pydantic before DB insert       │    ║
║  └─────────────────────────┬───────────────────────────────────────────┘    ║
║                             │                                                ║
║                             ▼                                                ║
║               ┌─────────────────────────────┐                               ║
║               │  PostgreSQL: raw_articles   │                               ║
║               │  PostgreSQL: structured_events│                             ║
║               │  PostgreSQL: dead_letter_queue│                             ║
║               └───────────────┬─────────────┘                               ║
╚═══════════════════════════════╪══════════════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║         MODULE 2 — INDIA AI-GPR INDEX BUILDER                                ║
║         [Container 2: gpr_index_builder]                                     ║
║                                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  Runs daily at 20:30 IST (after market close + GDELT stabilizes)   │    ║
║  │                                                                     │    ║
║  │  aggregator.py:                                                     │    ║
║  │    raw_score[t] = Σ (severity_i × india_exposure_i × confidence_i) │    ║
║  │    for all events i on date t                                       │    ║
║  │                                                                     │    ║
║  │  decay_smoother.py:                                                 │    ║
║  │    decay_weight_i = exp(−λ × hours_since_pub_i)                    │    ║
║  │    λ = 0.10 (half-life ≈ 7 hours — calibrated to Indian news cycle)│    ║
║  │    weighted_score[t] = Σ (contribution_i × decay_weight_i)        │    ║
║  │    smoothed_score[t] = 3-day rolling mean of weighted_score        │    ║
║  │                                                                     │    ║
║  │  normalizer.py:                                                     │    ║
║  │    mu[t]    = rolling mean of smoothed_score (window = 252 days)   │    ║
║  │    sigma[t] = rolling std of smoothed_score (window = 252 days)    │    ║
║  │    GPR[t]   = (smoothed_score[t] − mu[t]) / sigma[t]              │    ║
║  │                                                                     │    ║
║  │  validator.py:                                                      │    ║
║  │    • Spike assertion: GPR > 2.0 on Galwan/Pulwama/Uri/26-11 +−2d  │    ║
║  │    • Pearson r vs Caldara-Iacoviello India benchmark               │    ║
║  └─────────────────────────┬───────────────────────────────────────────┘    ║
║                             │                                                ║
║                             ▼                                                ║
║        ┌─────────────────────────────────────────────┐                      ║
║        │  PostgreSQL: gpr_index                      │                      ║
║        │  Redis: key="india_gpr:latest"              │                      ║
║        │         key="india_gpr:rolling_7d"          │                      ║
║        └─────────────────────────────────────────────┘                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
                                │
          ┌─────────────────────┴───────────────────┐
          │         EXTERNAL MARKET DATA             │
          │  yfinance pulled daily at 18:30 IST:     │
          │    ^NSEI  — Nifty 50 close prices        │
          │    USDINR=X — INR/USD spot rate          │
          │    CL=F    — WTI Crude Oil futures       │
          │  Market holiday calendar: NSE official   │
          │  Missing data: forward-fill (max 1 day)  │
          └─────────────────────┬───────────────────┘
                                │
                                ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║         MODULE 3 — ML INFERENCE SERVICE                                      ║
║         [Container 3: ml_inference]                                          ║
║                                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  FEATURE ENGINEERING (feature_engineering.py)                       │    ║
║  │                                                                     │    ║
║  │  All features are point-in-time safe:                              │    ║
║  │  Feature at time t only uses data known before market open at t    │    ║
║  │                                                                     │    ║
║  │  GPR Features (lagged to prevent lookahead):                       │    ║
║  │    india_ai_gpr_t1      = GPR[t−1]                                 │    ║
║  │    india_ai_gpr_t3      = GPR[t−3]                                 │    ║
║  │    india_ai_gpr_t7      = GPR[t−7]                                 │    ║
║  │    gpr_shock_flag       = 1 if GPR[t−1] > rolling_mean + 2σ       │    ║
║  │    gpr_rolling_mean_7   = mean(GPR[t−7 : t−1])                    │    ║
║  │                                                                     │    ║
║  │  Market Features (lagged returns only):                            │    ║
║  │    inr_usd_return   = (INRUSD[t−1] − INRUSD[t−2]) / INRUSD[t−2]  │    ║
║  │    crude_oil_return = (CL[t−1] − CL[t−2]) / CL[t−2]              │    ║
║  │    nifty_return_t1  = (Nifty[t−1] − Nifty[t−2]) / Nifty[t−2]    │    ║
║  │    nifty_return_t5  = (Nifty[t−5] − Nifty[t−6]) / Nifty[t−6]    │    ║
║  │    nifty_vol_lag1   = std(Nifty_returns[t−11 : t−1], window=10)   │    ║
║  │                       ← uses t−11 to t−1, NOT t−10 to t          │    ║
║  │                       ← target uses t−10 to t (non-overlapping)   │    ║
║  └─────────────────────────┬───────────────────────────────────────────┘    ║
║                             │                                                ║
║                             ▼                                                ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  TARGET CONSTRUCTION (no_lookahead confirmed)                       │    ║
║  │                                                                     │    ║
║  │  daily_return[t] = (Nifty[t] − Nifty[t−1]) / Nifty[t−1]          │    ║
║  │  rolling_vol[t]  = std(daily_return[t−9 : t], window=10)          │    ║
║  │  threshold       = 75th percentile of rolling_vol (train set only) │    ║
║  │  label[t]        = HIGH_VOL (1) if rolling_vol[t] > threshold      │    ║
║  │                    NORMAL   (0) otherwise                           │    ║
║  │                                                                     │    ║
║  │  Class balance check (train set 2010-2022):                        │    ║
║  │    Expected: ~25% HIGH_VOL, ~75% NORMAL                           │    ║
║  │    Handled via: class_weight='balanced' in all sklearn models      │    ║
║  │                 scale_pos_weight = n_neg/n_pos in XGBoost          │    ║
║  └─────────────────────────┬───────────────────────────────────────────┘    ║
║                             │                                                ║
║                             ▼                                                ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  MODEL TRAINING (train.py)                                          │    ║
║  │                                                                     │    ║
║  │  Train window: 2010-01-01 → 2022-12-31                            │    ║
║  │  OOS test:     2023-01-01 → present                                │    ║
║  │  No cross-contamination: threshold computed on train set only      │    ║
║  │                                                                     │    ║
║  │  Model 1: Logistic Regression                                      │    ║
║  │    C=1.0, solver='lbfgs', class_weight='balanced'                 │    ║
║  │    StandardScaler applied to all features                          │    ║
║  │                                                                     │    ║
║  │  Model 2: XGBoost (primary)                                        │    ║
║  │    n_estimators=300, max_depth=4, learning_rate=0.05              │    ║
║  │    scale_pos_weight = n_neg/n_pos                                  │    ║
║  │    early_stopping_rounds=20 on validation fold                    │    ║
║  │    HPO via 5-fold TimeSeriesSplit cross-validation                │    ║
║  │                                                                     │    ║
║  │  Model 3: LSTM (optional)                                          │    ║
║  │    Input: rolling 30-day window of all 10 features                 │    ║
║  │    2 LSTM layers (64 units) + Dropout(0.3) + Dense(1, sigmoid)    │    ║
║  │    Included only if F1_LSTM > F1_XGBoost + 0.03 on val set        │    ║
║  └─────────────────────────┬───────────────────────────────────────────┘    ║
║                             │                                                ║
║                             ▼                                                ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  INFERENCE + SHAP (shap_explainer.py)                              │    ║
║  │                                                                     │    ║
║  │  Online inference: triggered once daily after GPR is computed      │    ║
║  │  SHAP: TreeExplainer for XGBoost (fast, exact)                    │    ║
║  │  Output cached in Redis: key="volatility_signal:latest"           │    ║
║  │                                                                     │    ║
║  │  Response payload:                                                  │    ║
║  │    {                                                                │    ║
║  │      "regime": "HIGH_VOL" | "NORMAL",                             │    ║
║  │      "probability_high_vol": 0.73,                                 │    ║
║  │      "top_drivers": [                                              │    ║
║  │         {"feature": "india_ai_gpr_t1", "shap_value": +0.31},     │    ║
║  │         {"feature": "nifty_vol_lag1",  "shap_value": +0.18},     │    ║
║  │         {"feature": "crude_oil_return","shap_value": +0.09}      │    ║
║  │      ]                                                             │    ║
║  │    }                                                               │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
╚══════════════════════════════════════════════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║         MODULE 4 — API GATEWAY + MONITORING                                  ║
║         [Container 4: api_gateway]                                           ║
║                                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  FastAPI REST Endpoints                                             │    ║
║  │                                                                     │    ║
║  │  GET  /current-gpr           → Redis read (hot path, <10ms)       │    ║
║  │  GET  /gpr-history           → PostgreSQL query (indexed on date)  │    ║
║  │  GET  /event-feed            → PostgreSQL query (indexed on date)  │    ║
║  │  GET  /volatility-signal     → Redis read (hot path, <10ms)       │    ║
║  │  POST /portfolio-exposure    → PostgreSQL + computation (optional) │    ║
║  │  GET  /health                → liveness check for all containers   │    ║
║  │  GET  /metrics               → Prometheus scrape endpoint          │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  MONITORING (Container 7)                                           │    ║
║  │                                                                     │    ║
║  │  Prometheus scrapes /metrics every 15s                             │    ║
║  │  Grafana dashboards:                                                │    ║
║  │    1. Pipeline Health: ingest_rate, extract_latency_ms, error_%    │    ║
║  │    2. Model Health: llm_confidence_mean, event_volume_24h          │    ║
║  │    3. API Health: p50/p95/p99 latency, req/min, error_rate        │    ║
║  │                                                                     │    ║
║  │  Alerts:                                                            │    ║
║  │    • llm_confidence_mean < 0.65 for 3 consecutive hours           │    ║
║  │    • event_volume_24h < 20% of 30-day average (media blackout)    │    ║
║  │    • api_p99_latency > 500ms for 5 consecutive minutes            │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## Layer-by-Layer Breakdown

### Layer 0 — Data Sources

The primary data source is the **GDELT Global Knowledge Graph (GKG) API**. GDELT monitors news in 65 languages across 250+ countries and codes events using the CAMEO (Conflict and Mediation Event Observations) taxonomy. We filter specifically for:

- **Actor country code: IND** — Events where India is Actor1 or Actor2
- **CAMEO codes 14–20** — Ranging from protest → use of conventional force
- **Tone threshold: < −3.0** — Only articles with a meaningfully negative tone score

Supplementary sources (RSS, NewsAPI) act as **failover fallbacks** in case of GDELT API downtime or rate limiting. They are not used by default.

**GDELT API Rate Limits:**
| Tier | Limit | Our usage |
|---|---|---|
| Free public GKG | 10 req/min | We pull every 15 min → 4/hr → well within limits |
| Article HTML fetching | No API limit (direct HTTP) | Respect robots.txt, 1s delay between fetches |

---

### Layer 1 — Ingestion + Extraction (Module 1)

#### Why 2-Stage LLM (not just GPT-4o-mini directly)?

Running every GDELT article through GPT-4o-mini would cost approximately:
- GDELT pulls ~200–500 India-tagged articles every 15 minutes
- At ~750 tokens/article average input + 200 output ≈ 950 tokens/call
- At $0.00015/1K input, $0.00060/1K output: ~$0.000225/article
- At 400 articles × 96 pulls/day = 38,400 articles/day → **$8.64/day → $3,153/year**

After FinBERT Stage 1 filtering (rejecting ~65% as non-negative):
- ~134 articles/day pass to GPT-4o-mini → **$3.02/day → $1,100/year**
- **43% cost reduction with negligible precision loss**

#### Deduplication Design

GDELT frequently syndicates the same wire story (e.g., Reuters India) to hundreds of outlets with slightly different URLs. Without deduplication:
- The same Pulwama attack article could be counted 80+ times
- It would artificially spike the GPR index

Our two-layer approach:
1. **URL hash** catches exact reposts
2. **MinHash LSH** catches syndicated variants (same content, different URL)

We chose MinHash over embedding similarity because:
- At 400 articles/pull, embedding every article costs time and money
- MinHash runs in microseconds with no API call
- Jaccard threshold 0.80 is validated against known duplicate pairs

---

### Layer 2 — GPR Index Builder (Module 2)

See full mathematical derivation in [METHODOLOGY.md](METHODOLOGY.md).

**Why run at 20:30 IST?**

The GPR index is designed as a **daily-frequency signal**, not a live tick-by-tick indicator. Running at 20:30 ensures:
1. All GDELT pulls for the calendar day are complete (GDELT indexes articles with ~2h lag)
2. Nifty market data for the day is fully settled via yfinance
3. The index value is stable for next-day feature engineering

---

### Layer 3 — ML Inference (Module 3)

The feature window is intentionally designed to be **strictly backward-looking**:

```
Timeline:
─────────────────────────────────────────────────────
t-11  t-10  t-9  t-8  ...  t-2  t-1  |  t (today)
                                      |
 ◄─── nifty_vol_lag1 window ──────►  |  ◄─ target vol window ─►
      (uses t-11 to t-1)             |     (uses t-9 to t)
                                      |
      ← overlapping range: t-9 to t-1 (9 days overlap) →
```

The 1-day offset (`t-11 to t-1` vs `t-9 to t`) ensures the feature is available at prediction time (close of day t-1) and the target is what we're forecasting (realized vol through close of t). There is **no lookahead**.

---

## Database Schema

### PostgreSQL Tables

```sql
-- Raw article storage
CREATE TABLE raw_articles (
    id              BIGSERIAL PRIMARY KEY,
    url_hash        CHAR(64) UNIQUE NOT NULL,       -- SHA-256 of normalized URL
    url             TEXT NOT NULL,
    headline        TEXT,
    body_text       TEXT,
    source_domain   VARCHAR(255),
    publish_ts      TIMESTAMPTZ,
    gdelt_event_id  VARCHAR(64),
    ingested_at     TIMESTAMPTZ DEFAULT now(),
    is_deduplicated BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_raw_articles_publish_ts ON raw_articles (publish_ts);
CREATE INDEX idx_raw_articles_url_hash   ON raw_articles (url_hash);

-- Structured events from LLM extraction
CREATE TABLE structured_events (
    id              BIGSERIAL PRIMARY KEY,
    raw_article_id  BIGINT REFERENCES raw_articles(id),
    event_type      VARCHAR(50) NOT NULL,            -- military_conflict, sanctions, etc.
    severity        NUMERIC(4,3) NOT NULL,            -- 0.000 to 1.000
    india_exposure  NUMERIC(4,3) NOT NULL,
    confidence      NUMERIC(4,3) NOT NULL,
    actors          JSONB,                           -- ["India", "Pakistan"]
    locations       JSONB,                           -- ["Kashmir", "Galwan Valley"]
    event_date      DATE NOT NULL,
    extracted_at    TIMESTAMPTZ DEFAULT now(),
    prompt_version  VARCHAR(20) NOT NULL,            -- e.g. "v1.3" for drift tracking
    finbert_label   VARCHAR(20),                     -- FinBERT Stage 1 output
    llm_raw_output  TEXT                             -- archived for audit
);

CREATE INDEX idx_events_event_date  ON structured_events (event_date);
CREATE INDEX idx_events_event_type  ON structured_events (event_type);
CREATE INDEX idx_events_severity    ON structured_events (severity);

-- Daily GPR index values
CREATE TABLE gpr_index (
    id                  BIGSERIAL PRIMARY KEY,
    index_date          DATE UNIQUE NOT NULL,
    raw_score           NUMERIC(10,4),
    weighted_score      NUMERIC(10,4),               -- after decay
    smoothed_score      NUMERIC(10,4),               -- after 3-day rolling avg
    normalized_gpr      NUMERIC(8,4),                -- final Z-score normalized value
    rolling_mean_252d   NUMERIC(10,4),
    rolling_std_252d    NUMERIC(10,4),
    event_count         INTEGER,                      -- # events that day
    computed_at         TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_gpr_index_date ON gpr_index (index_date);

-- ML model predictions
CREATE TABLE ml_predictions (
    id                  BIGSERIAL PRIMARY KEY,
    prediction_date     DATE UNIQUE NOT NULL,
    regime              VARCHAR(10) NOT NULL,         -- HIGH_VOL | NORMAL
    prob_high_vol       NUMERIC(5,4) NOT NULL,
    top_drivers         JSONB,                       -- SHAP values top 3
    model_version       VARCHAR(20) NOT NULL,
    features_snapshot   JSONB,                       -- full feature vector archived
    predicted_at        TIMESTAMPTZ DEFAULT now()
);

-- Dead letter queue for failed extractions
CREATE TABLE dead_letter_queue (
    id              BIGSERIAL PRIMARY KEY,
    raw_article_id  BIGINT REFERENCES raw_articles(id),
    failure_reason  TEXT,
    retry_count     SMALLINT DEFAULT 0,
    failed_at       TIMESTAMPTZ DEFAULT now()
);
```

---

## Container Architecture

```
docker-compose.yml defines 7 services:

┌─────────────────────────────────────────────────────────────────────┐
│  Service Name         Port   Depends On          Restart Policy     │
├─────────────────────────────────────────────────────────────────────┤
│  ingestion_service    8001   postgres, redis      always            │
│  gpr_index_builder    8002   postgres, redis      always            │
│  ml_inference         8003   postgres, redis      always            │
│  api_gateway          8000   all above            always            │
│  postgres             5432   (none)               always            │
│  redis                6379   (none)               always            │
│  monitoring           9090/3000 (none — pushgateway) always         │
└─────────────────────────────────────────────────────────────────────┘

Port Mapping:
  api_gateway:8000     → host:8000   (public API)
  monitoring:3000      → host:3000   (Grafana dashboard)
  monitoring:9090      → host:9090   (Prometheus — internal only)
  postgres:5432        → host:5432   (dev access only, not exposed in prod)
  redis:6379           → not exposed to host

Volume Mounts:
  postgres_data        → /var/lib/postgresql/data  (persistent)
  redis_data           → /data                     (persistent)
  grafana_data         → /var/lib/grafana          (persistent)
  model_artifacts      → /app/models               (trained model files)
```

### Startup Sequence

```
1. postgres  → starts first (healthcheck: pg_isready)
2. redis     → starts after postgres healthy
3. ingestion_service → starts after redis healthy, runs initial pull
4. gpr_index_builder → starts, waits for first day of events
5. ml_inference      → starts, loads trained model from /app/models/
6. api_gateway       → starts after all 3 services healthy
7. monitoring        → starts independently, self-configuring
```

---

## API Gateway Design

### Full Endpoint Specification

```
GET /current-gpr
  Auth: API-Key header required
  Response: {
    "date": "2026-03-04",
    "gpr_score": 1.43,
    "regime": "HIGH_VOL",
    "prob_high_vol": 0.73,
    "event_count_today": 12,
    "updated_at": "2026-03-04T20:35:00Z"
  }
  Latency target: < 20ms (Redis hot path)

GET /gpr-history?start=2025-01-01&end=2025-12-31
  Auth: API-Key header required
  Response: {
    "start": "2025-01-01",
    "end": "2025-12-31",
    "series": [
      {"date": "2025-01-01", "gpr_score": 0.21, "event_count": 4},
      ...
    ]
  }
  Latency target: < 200ms (PostgreSQL with date index)

GET /event-feed?date=2026-03-04
  Auth: API-Key header required
  Response: {
    "date": "2026-03-04",
    "events": [
      {
        "event_type": "military_conflict",
        "severity": 0.82,
        "india_exposure": 0.91,
        "confidence": 0.87,
        "actors": ["India", "Pakistan"],
        "locations": ["Line of Control"],
        "source_url": "https://...",
        "publish_ts": "2026-03-04T08:14:00Z"
      },
      ...
    ]
  }

GET /volatility-signal
  Auth: API-Key header required
  Response: {
    "prediction_date": "2026-03-04",
    "regime": "HIGH_VOL",
    "probability_high_vol": 0.73,
    "top_drivers": [
      {"feature": "india_ai_gpr_t1", "shap_value": 0.31,
       "feature_value": 1.43},
      {"feature": "nifty_vol_lag1", "shap_value": 0.18,
       "feature_value": 0.0142},
      {"feature": "crude_oil_return", "shap_value": 0.09,
       "feature_value": 0.023}
    ],
    "model_version": "xgboost_v2.1",
    "predicted_at": "2026-03-04T20:40:00Z"
  }

POST /portfolio-exposure
  Auth: API-Key header required
  Body: {
    "sectors": ["IT", "Defence", "Energy", "Banking"]
  }
  Response: {
    "date": "2026-03-04",
    "current_gpr": 1.43,
    "sector_exposure": {
      "IT":      {"gpr_beta": 0.3, "risk_level": "LOW"},
      "Defence": {"gpr_beta": 1.8, "risk_level": "HIGH"},
      "Energy":  {"gpr_beta": 1.2, "risk_level": "ELEVATED"},
      "Banking": {"gpr_beta": 0.7, "risk_level": "MODERATE"}
    }
  }
```

---

## Caching Strategy

### Redis Key Structure

```
india_gpr:latest               → STRING  {date, gpr_score, ...}    TTL: 24h
india_gpr:rolling_7d           → STRING  {mean_7d, std_7d}          TTL: 24h
volatility_signal:latest       → STRING  {regime, prob, drivers}    TTL: 24h
dedup:url_hash:<sha256>        → STRING  "1"                        TTL: 7d
dedup:minhash:bucket:<bucket_id> → SET  {url_hash1, url_hash2}     TTL: 48h
```

**Cache Invalidation:** After each daily run of `gpr_index_builder` completes, it writes fresh values to all relevant Redis keys. API reads always hit Redis first; PostgreSQL is the source of truth for historical data.

---

## Monitoring Infrastructure

### Prometheus Metrics Exported

```python
# Ingestion metrics (ingestion_service/metrics.py)
gdelt_articles_pulled_total        # Counter
gdelt_articles_deduplicated_total  # Counter
article_fetch_duration_ms          # Histogram (buckets: 100,500,1000,5000)
finbert_classification_duration_ms # Histogram
gpt_calls_total                    # Counter
gpt_call_duration_ms               # Histogram
gpt_confidence_score               # Gauge (rolling mean)
dead_letter_queue_size             # Gauge

# GPR index metrics (gpr_index_builder/metrics.py)
gpr_index_compute_duration_ms      # Histogram
gpr_daily_score                    # Gauge
gpr_event_count_daily              # Gauge

# API metrics (api_gateway/metrics.py) — auto via prometheus-fastapi-instrumentator
http_request_duration_ms           # Histogram by endpoint
http_requests_total                # Counter by status code
```

### Grafana Alert Rules

| Alert | Condition | Severity |
|---|---|---|
| LLM Confidence Drift | `avg(gpt_confidence_score[1h]) < 0.65` | Warning |
| Media Blackout Detected | `gpr_event_count_daily < 0.2 * avg(gpr_event_count_daily[30d])` | Critical |
| API Latency Breach | `p99(http_request_duration_ms[5m]) > 500` | Warning |
| Dead Letter Buildup | `dead_letter_queue_size > 50` | Warning |
| Pipeline Stale | `time() - last_success_ts > 3600` (no successful run in 1h) | Critical |

---

## Data Flow (Detailed)

```
T+0:00   APScheduler fires in ingestion_service
T+0:01   GDELT GKG API queried for last 15-min window
T+0:05   Article URLs collected, HTML fetched with rate limiting
T+0:08   Cleaning pipeline processes raw HTML → text
T+0:09   Layer-1 dedup (URL hash) → ~5% articles dropped
T+0:10   Layer-2 dedup (MinHash LSH) → ~25% articles dropped
T+0:12   FinBERT runs on remaining articles (batch inference)
         ~65% labeled POSITIVE/NEUTRAL → dropped
         ~35% labeled NEGATIVE → routed to GPT-4o-mini
T+0:18   GPT-4o-mini extracts structured JSON for each negative article
         Failed JSON → dead_letter_queue
T+0:20   Pydantic schema validation
T+0:21   structured_events rows inserted to PostgreSQL

─── repeated every 15 minutes throughout the day ───

T EOD:
20:15    yfinance pulls Nifty, INR/USD, Crude for the day
20:30    gpr_index_builder cron fires
20:31    Reads all structured_events for date=today from PostgreSQL
20:32    aggregator.py: computes raw_score
20:33    decay_smoother.py: applies decay weights + 3-day rolling avg
20:34    normalizer.py: Z-score against 252-day rolling stats
20:35    gpr_index row inserted to PostgreSQL
20:35    Redis keys updated: india_gpr:latest, india_gpr:rolling_7d
20:36    validator.py: sanity checks (score in valid range, no NaN)

20:37    ml_inference cron fires (triggered after gpr_index_builder)
20:38    feature_engineering.py: reads GPR and market data, builds vector
20:39    XGBoost model loaded from /app/models/xgboost_v2.1.pkl
20:40    Prediction computed + SHAP values computed via TreeExplainer
20:41    ml_predictions row inserted to PostgreSQL
20:41    Redis key updated: volatility_signal:latest

─── API continuously serves from Redis + PostgreSQL ───
```

---

## Security Design

| Layer | Mechanism |
|---|---|
| API authentication | API key via `X-API-Key` header (hashed+stored in PostgreSQL) |
| Rate limiting | 100 req/min per key via FastAPI middleware |
| Database access | All containers use env-injected credentials (never hardcoded) |
| OpenAI API key | Injected via Docker secret / environment variable |
| PostgreSQL exposure | Port 5432 NOT exposed to host in production Compose |
| Redis exposure | Port 6379 NOT exposed to host |
| HTTPS | Nginx reverse proxy with TLS terminates before api_gateway |

---

## Scalability Considerations

The current architecture is designed for a **single-server deployment** sufficient for research/capstone purposes. Production scaling paths:

| Component | Current | Scale Option |
|---|---|---|
| Ingestion | Single container | Celery workers + message queue |
| GPT calls | Sequential | Async batch via asyncio + semaphore limiting |
| PostgreSQL | Single instance | Read replicas for API queries |
| Redis | Single node | Redis Cluster for HA |
| ML inference | Daily batch | Real-time streaming with Kafka |

---

## Repository Structure

```
india-ai-gpr/
├── ingestion/
│   ├── gdelt_puller.py          # GDELT API client + scheduler
│   ├── cleaner.py               # HTML stripping + text normalization
│   └── deduplicator.py          # URL hash + MinHash LSH dedup
│
├── extraction/
│   ├── finbert_classifier.py    # FinBERT Stage 1 routing
│   ├── gpt_extractor.py         # GPT-4o-mini Stage 2 extraction
│   └── schema.py                # Pydantic EventSchema for validation
│
├── gpr_index/
│   ├── aggregator.py            # Daily event → raw_score aggregation
│   ├── decay_smoother.py        # Exponential decay + rolling avg
│   ├── normalizer.py            # Z-score normalization (252-day window)
│   └── validator.py             # Spike assertions + benchmark correlation
│
├── ml_inference/
│   ├── feature_engineering.py   # Point-in-time safe feature matrix
│   ├── train.py                 # LR + XGBoost + optional LSTM training
│   ├── evaluate.py              # OOS metrics: F1, AUC, confusion matrix
│   └── shap_explainer.py        # TreeExplainer + top-3 driver extraction
│
├── api_gateway/
│   ├── main.py                  # FastAPI app factory
│   ├── routes/
│   │   ├── gpr.py               # /current-gpr, /gpr-history
│   │   ├── events.py            # /event-feed
│   │   └── signals.py           # /volatility-signal, /portfolio-exposure
│   └── schemas.py               # Pydantic response models
│
├── monitoring/
│   ├── prometheus_config.yml    # Scrape config for all services
│   └── grafana_dashboard.json   # Pre-built dashboard definition
│
├── data/
│   ├── sample_events.json       # 50 hand-labelled validation events
│   └── validation_events.csv    # Known event dates for spike testing
│
├── notebooks/
│   ├── 01_caldara_validation.ipynb      # Benchmark correlation analysis
│   ├── 02_gdelt_exploration.ipynb       # GDELT data quality + volume stats
│   ├── 03_feature_engineering.ipynb     # Feature distribution + lookahead audit
│   └── 04_model_evaluation.ipynb        # OOS results, SHAP plots, ROC curves
│
├── docs/
│   ├── proposal.pdf
│   └── architecture.png
│
├── docker-compose.yml
├── requirements.txt
├── ARCHITECTURE.md              # ← this file
├── METHODOLOGY.md               # ← companion methodology document
└── README.md
```
