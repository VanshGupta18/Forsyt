# Getting Started — India AI-GPR Platform
## From Zero to Running in One Day

---

## What You Will Have Running by the End

| Time | Milestone |
|---|---|
| 30 min | All dependencies installed, environment verified |
| 1 hr | PostgreSQL + Redis running, all tables created |
| 2 hr | Module 1 ingesting live GDELT articles into your database |
| 3 hr | Module 2 building the GPR index (with historical backfill) |
| 5 hr | Module 3 trained and producing volatility predictions |
| 6 hr | Module 4 API live, all endpoints responding |

---

## Prerequisites — What You Need Before Starting

### 1. Hardware
- **Minimum**: 8 GB RAM, 4 CPU cores, 20 GB free disk
- **Recommended**: 16 GB RAM, 8 cores (FinBERT loads a ~440 MB model into memory)
- GPU is optional — FinBERT runs on CPU in ~1.2s per article

### 2. Accounts & API Keys
| Service | Purpose | Cost | Sign-Up URL |
|---|---|---|---|
| **OpenAI** | GPT-4o-mini for event extraction | ~$1.91/day | platform.openai.com |
| **GDELT** | Primary news data source | **Free, no key needed** | — |
| **yfinance** | Market data (Nifty, INR/USD, Crude) | **Free, no key needed** | — |

> You only need ONE paid key: OpenAI. Everything else is free.

### 3. Software
```bash
# Verify these are installed
python3 --version      # Must be 3.10 or 3.11
docker --version       # Must be 24+
docker compose version # Must be 2.x (note: "compose" not "compose-cli")
git --version
```

If anything is missing:
```bash
# macOS
brew install python@3.11 docker git

# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y python3.11 docker.io docker-compose-v2 git
```

---

## Step 1 — Clone and Configure Environment

```bash
# 1. Clone the repository (or use your existing folder)
cd ~/
git clone <your-repo-url> india-gpr
cd india-gpr

# 2. Create Python virtual environment
python3.11 -m venv .venv
source .venv/bin/activate     # On Windows: .venv\Scripts\activate

# 3. Install all Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Verify key packages installed correctly
python -c "import torch; print('PyTorch:', torch.__version__)"
python -c "import xgboost; print('XGBoost:', xgboost.__version__)"
python -c "import fastapi; print('FastAPI OK')"
```

### 4. Create Your `.env` File

```bash
cp .env.example .env
```

Open `.env` and fill in:
```bash
# .env — NEVER commit this file to Git

# OpenAI (required)
OPENAI_API_KEY=sk-your-key-here

# PostgreSQL (Docker will create these automatically)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=india_gpr
POSTGRES_USER=gpr_user
POSTGRES_PASSWORD=choose-a-strong-password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# API Keys for consumers of your own API
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
INDIA_GPR_API_KEYS=your-sha256-hash-here

# Environment mode
APP_ENV=development        # Change to "production" when deploying
```

---

## Step 2 — Start Infrastructure (PostgreSQL + Redis)

```bash
# Start only the database containers first (not the full stack yet)
docker compose up -d postgres redis

# Verify they started
docker compose ps

# Expected output:
# NAME       STATUS    PORTS
# postgres   running   0.0.0.0:5432->5432/tcp
# redis      running   0.0.0.0:6379->6379/tcp
```

Wait 15 seconds for PostgreSQL to initialize, then verify connectivity:

```bash
# Test PostgreSQL
docker exec -it postgres psql -U gpr_user -d india_gpr -c "SELECT version();"

# Test Redis
docker exec -it redis redis-cli ping
# Expected: PONG
```

---

## Step 3 — Create Database Tables

Run this once to create all 7 tables:

```bash
python scripts/init_db.py
```

The `init_db.py` script runs this SQL:

```sql
-- Raw articles from GDELT
CREATE TABLE IF NOT EXISTS raw_articles (
    article_id   SERIAL PRIMARY KEY,
    source_url   TEXT NOT NULL UNIQUE,
    url_hash     CHAR(64) NOT NULL UNIQUE,    -- SHA-256, used for dedup
    headline     TEXT,
    body_text    TEXT,
    published_at TIMESTAMPTZ,
    fetched_at   TIMESTAMPTZ DEFAULT now()
);

-- LLM-extracted geopolitical events
CREATE TABLE IF NOT EXISTS structured_events (
    event_id       SERIAL PRIMARY KEY,
    article_id     INT REFERENCES raw_articles(article_id),
    event_type     TEXT NOT NULL,
    severity       FLOAT NOT NULL CHECK (severity BETWEEN 0 AND 1),
    india_exposure FLOAT NOT NULL CHECK (india_exposure BETWEEN 0 AND 1),
    confidence     FLOAT NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    actors         TEXT[],
    locations      TEXT[],
    summary        TEXT,
    extracted_at   TIMESTAMPTZ DEFAULT now()
);

-- Daily GPR index values
CREATE TABLE IF NOT EXISTS gpr_index (
    index_date        DATE PRIMARY KEY,
    raw_score         FLOAT,
    smoothed_score    FLOAT,
    normalized_gpr    FLOAT,
    data_quality_flag TEXT DEFAULT 'OK',
    computed_at       TIMESTAMPTZ DEFAULT now()
);

-- ML volatility predictions
CREATE TABLE IF NOT EXISTS ml_predictions (
    prediction_date   DATE PRIMARY KEY,
    regime            TEXT NOT NULL,
    prob_high_vol     FLOAT NOT NULL,
    top_drivers       JSONB,
    model_version     TEXT,
    features_snapshot JSONB,
    predicted_at      TIMESTAMPTZ DEFAULT now()
);

-- Failed LLM extractions (for retry / audit)
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    dlq_id     SERIAL PRIMARY KEY,
    article_id INT,
    error_msg  TEXT,
    raw_text   TEXT,
    failed_at  TIMESTAMPTZ DEFAULT now()
);

-- Portfolio analysis tables (for investor API)
CREATE TABLE IF NOT EXISTS ticker_sector_map (
    ticker     TEXT PRIMARY KEY,
    sector     TEXT NOT NULL,
    nse_symbol TEXT,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sector_gpr_betas (
    sector       TEXT PRIMARY KEY,
    gpr_beta     FLOAT NOT NULL,
    r_squared    FLOAT,
    computed_on  DATE NOT NULL
);

-- Indexes (critical for query performance)
CREATE INDEX IF NOT EXISTS idx_raw_articles_published ON raw_articles (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_extracted      ON structured_events (extracted_at DESC);
CREATE INDEX IF NOT EXISTS idx_gpr_date              ON gpr_index (index_date DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_date      ON ml_predictions (prediction_date DESC);
```

Verify tables created:
```bash
docker exec -it postgres psql -U gpr_user -d india_gpr -c "\dt"
# Should list all 7 tables
```

---

## Step 4 — Seed Historical GPR Data (Critical — Do This Before Training)

The ML model needs GPR data back to 2010 to train. You have two options:

### Option A — Download Caldara-Iacoviello Public Dataset (Fastest, ~10 min)

The original academic GPR index (Caldara & Iacoviello, 2022) is free and goes back to 1985:

```bash
python scripts/seed_gpr_from_caldara.py \
  --url "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls" \
  --country-col "IGPR"   # India GPR column
```

This script:
1. Downloads the Excel file
2. Extracts the India-specific GPR column
3. Normalizes it to the same Z-score scale as your own computed GPR
4. Inserts rows into `gpr_index` with `data_quality_flag = 'SEEDED_CALDARA'`

### Option B — Backfill From GDELT Historical Archive (Slow, ~6 hrs, more accurate)

GDELT provides daily bulk files going back to 2015:

```bash
# This will take several hours — run overnight
python scripts/backfill_gdelt_historical.py \
  --start-date 2010-01-01 \
  --end-date   2024-12-31
```

> **Recommendation for capstone**: Use Option A to get training running immediately. Use Option B output to later validate that your GPR correlates with Caldara-Iacoviello.

---

## Step 5 — Test Module 1 (Ingestion) — Single Cycle

Before running the scheduler, test one ingestion cycle manually:

```bash
python -c "
from ingestion.pipeline import run_ingestion_cycle
import asyncio
result = asyncio.run(run_ingestion_cycle())
print(result)
"
```

Expected output:
```
INFO | Fetching GDELT articles (last 20 minutes)...
INFO | Fetched 34 URLs from GDELT
INFO | After URL dedup: 27 new articles
INFO | After MinHash dedup: 22 unique articles
INFO | FinBERT rejected 14 articles (positive/neutral sentiment)
INFO | GPT-4o-mini: extracting events from 8 articles...
INFO | Extracted 8 events, 0 failed (DLQ)
{'articles_fetched': 34, 'events_extracted': 8, 'dlq_failures': 0}
```

If you see events being extracted, Module 1 is working. Check the database:

```bash
docker exec -it postgres psql -U gpr_user -d india_gpr -c \
  "SELECT COUNT(*) FROM raw_articles; SELECT COUNT(*) FROM structured_events;"
```

---

## Step 6 — Start Module 1 Scheduler (Background)

```bash
# Runs ingestion every 15 minutes — keep this terminal open OR use tmux/screen
python ingestion/scheduler.py &

# Or run as Docker container
docker compose up -d ingestion_service

# Monitor logs
docker compose logs -f ingestion_service
```

Let Module 1 run for at least 2 hours before proceeding. You need a few hundred events to build a meaningful GPR score for today.

---

## Step 7 — Run Module 2 (Build Today's GPR Index)

```bash
# Run GPR build for today manually first to verify it works
python -c "
from gpr_index.run_daily import run_gpr_index_for_date
from datetime import date
result = run_gpr_index_for_date(date.today())
print(result)
"
```

Expected output:
```
INFO | Computing GPR index for 2026-03-04
INFO | Fetched 47 events for 2026-03-04
INFO | Raw score: 3.24 | Weighted score: 2.87 | Smoothed: 2.91
INFO | Normalized GPR: 1.42 (Z-score vs 252-day window)
INFO | GPR written to PostgreSQL and Redis cache
{'index_date': '2026-03-04', 'normalized_gpr': 1.42, 'data_quality': 'OK'}
```

Then start the scheduler (runs daily at 20:30 IST):
```bash
docker compose up -d gpr_index_builder
```

---

## Step 8 — Train the ML Model (Run Once)

Only run after you have GPR data from at least 2010 (Step 4 must be complete):

```bash
python -c "
import psycopg2, os
from ml_inference.market_data import fetch_market_data
from ml_inference.feature_engineering import load_gpr_series, build_feature_matrix, build_target_variable
from ml_inference.train import run_training_pipeline
from ml_inference.evaluate import evaluate_model

conn = psycopg2.connect(
    host=os.environ['POSTGRES_HOST'], dbname=os.environ['POSTGRES_DB'],
    user=os.environ['POSTGRES_USER'], password=os.environ['POSTGRES_PASSWORD']
)
market_df         = fetch_market_data(start_date='2009-01-01')
gpr_series        = load_gpr_series(conn)
features          = build_feature_matrix(gpr_series, market_df)
labels, threshold = build_target_variable(market_df)

X_train, X_test, y_train, y_test, lr, xgb = run_training_pipeline(features, labels, threshold)

print('=== Evaluation Results ===')
evaluate_model(lr,  X_test, y_test, 'Logistic Regression')
evaluate_model(xgb, X_test, y_test, 'XGBoost')
"
```

Training takes 10–30 minutes depending on hardware. When done:
```bash
ls models/
# logistic_regression_v1.pkl
# xgboost_v1.pkl
# metadata_v1.pkl
```

Run today's inference:
```bash
python ml_inference/run_daily.py

# Verify in Redis
docker exec -it redis redis-cli GET volatility_signal:latest
```

Start the inference scheduler:
```bash
docker compose up -d ml_inference
```

---

## Step 9 — Start the API Gateway

```bash
docker compose up -d api_gateway

# Test all endpoints
curl http://localhost:8000/health

curl -H "X-API-Key: dev-key-insecure" http://localhost:8000/gpr/latest
curl -H "X-API-Key: dev-key-insecure" http://localhost:8000/signals/latest

# Open interactive API docs in browser
open http://localhost:8000/docs
```

---

## Step 10 — Start the Full Stack

Once each module has been tested individually:

```bash
# Bring up all 7 containers
docker compose up -d

# Check all are healthy
docker compose ps

# Expected — all should show "running":
# ingestion_service    running   :8001
# gpr_index_builder    running   :8002
# ml_inference         running   :8003
# api_gateway          running   :8000
# postgres             running   :5432
# redis                running   :6379
# monitoring           running   :9090 (Prometheus), :3000 (Grafana)
```

Open Grafana to monitor the live system:
```bash
open http://localhost:3000
# Default login: admin / admin
# Import the dashboard from: monitoring/grafana_dashboard.json
```

---

## Step 11 — Verify the Full Pipeline End to End

Run this verification script to confirm every component is working together:

```bash
python scripts/verify_pipeline.py
```

It checks:
- [ ] GDELT API is reachable
- [ ] PostgreSQL has articles from the last 30 minutes
- [ ] Redis has `india_gpr:latest` key with a value from today
- [ ] Redis has `volatility_signal:latest` key with a value from today
- [ ] API `/health` returns `{"status": "ok"}`
- [ ] API `/gpr/latest` returns a non-null `normalized_gpr`
- [ ] API `/signals/latest` returns `"regime": "HIGH_VOL"` or `"NORMAL"`
- [ ] No articles stuck in `dead_letter_queue` from the last hour

---

## Common Problems and Fixes

| Problem | Likely Cause | Fix |
|---|---|---|
| `OPENAI_API_KEY not found` | `.env` not loaded | Run `export $(cat .env \| xargs)` or use `python-dotenv` |
| `psycopg2.OperationalError: Connection refused` | PostgreSQL container not ready | Wait 30 sec after `docker compose up` then retry |
| FinBERT download hangs | First run downloads 440MB model | Wait — subsequent runs use local cache at `~/.cache/huggingface` |
| `0 events extracted` | GDELT returned no India conflict news | Normal during calm periods — check with `min_tone = -1` temporarily |
| XGBoost F1 < 0.50 | Seeded GPR not enough variance | Switch to Option B backfill (GDELT historical archive) |
| Redis `GET india_gpr:latest` returns nil | GPR builder hasn't run yet | Run Module 2 manually first (Step 7) |
| Docker memory error | FinBERT needs ~2GB RAM | Increase Docker Desktop memory limit to 8GB in Settings |

---

## Daily Operations (Once Running)

The system is **fully automated** after initial setup. The only manual tasks are:

| Task | Frequency | Command |
|---|---|---|
| Retrain ML model | Quarterly | `python ml_inference/train.py` |
| Recompute sector betas | Quarterly | `python scripts/compute_sector_gpr_betas.py` |
| Update ticker-sector map | Quarterly | `python scripts/update_ticker_sector_map.py` |
| Check dead letter queue | Weekly | `SELECT COUNT(*) FROM dead_letter_queue WHERE failed_at > now() - interval '7d'` |
| Update NSE holiday list | Annually | Edit `ml_inference/market_data.py` → `NSE_HOLIDAYS_20XX` |
| Rotate API keys | As needed | Generate new SHA-256 hash, update `INDIA_GPR_API_KEYS` env var |

---

## Cost Reference

| Component | Monthly Cost |
|---|---|
| GPT-4o-mini (with FinBERT pre-filter) | ~$57 |
| VPS / Cloud VM (8 vCPU, 16GB) | ~$60 |
| Managed PostgreSQL (if not self-hosting) | ~$25 |
| **Total** | **~$142/month** |

All data sources (GDELT, yfinance) are free.
