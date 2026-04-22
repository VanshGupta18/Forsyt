# Forsyt — Geopolitical Risk Intelligence System for Indian Markets

<div align="center">

![Forsyt Banner](https://img.shields.io/badge/Forsyt-Geopolitical%20Intelligence-0057B7?style=for-the-badge&logo=globe&logoColor=white)

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active%20Development-orange?style=flat-square)]()
[![Institution](https://img.shields.io/badge/Institution-Thapar%20Institute-red?style=flat-square)]()
[![Capstone](https://img.shields.io/badge/Capstone-CPG%20300-blue?style=flat-square)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen?style=flat-square)](CONTRIBUTING.md)

**An AI-powered, real-time geopolitical risk intelligence platform built specifically for Indian financial markets.**

[Overview](#overview) · [Features](#features) · [Getting Started](#getting-started) · [Architecture](#architecture) · [Modules](#modules) · [API](#api-reference) · [Contributing](#contributing) · [Roadmap](#roadmap)

</div>

---

## Table of Contents

1. [Overview](#overview)
2. [Motivation & Problem Statement](#motivation--problem-statement)
3. [Features](#features)
4. [System Architecture](#system-architecture)
5. [Modules](#modules)
6. [Tech Stack](#tech-stack)
7. [Getting Started](#getting-started)
   - [Prerequisites](#prerequisites)
   - [Installation](#installation)
   - [Environment Configuration](#environment-configuration)
   - [Database Setup](#database-setup)
8. [Running the Project](#running-the-project)
   - [Running the Data Pipeline](#running-the-data-pipeline)
   - [Running the NLP Extraction](#running-the-nlp-extraction)
   - [Running the GPR Index Builder](#running-the-gpr-index-builder)
   - [Running ML Models](#running-ml-models)
   - [Running the Dashboard](#running-the-dashboard)
9. [Usage Examples](#usage-examples)
10. [API Reference](#api-reference)
11. [Configuration](#configuration)
12. [Testing](#testing)
13. [Project Structure](#project-structure)
14. [Validation Strategy](#validation-strategy)
15. [Deployment](#deployment)
16. [Contributing](#contributing)
17. [Team](#team)
18. [Roadmap](#roadmap)
19. [FAQ](#faq)
20. [License](#license)
21. [References & Acknowledgements](#references--acknowledgements)

---

## Overview

**Forsyt** is an end-to-end AI-powered geopolitical intelligence platform designed specifically for the Indian economic ecosystem. It transforms unstructured global and Indian news into structured, quantified geopolitical risk insights — directly mapped to Indian financial markets, trade corridors, and investment portfolios.

At its core, Forsyt builds and maintains the **India AI-GPR Index** — a daily, normalized geopolitical risk score for India — validated against the academic Caldara-Iacoviello GPR benchmark. This index powers four downstream intelligence modules: a **News Intelligence System**, a **Portfolio Risk Advisor**, a **Supply Chain Risk Screener**, and a **Macro Forecasting Engine** — all backed by Explainable AI (SHAP) to provide transparent, auditable reasoning for every prediction.

> **Capstone Project** — BE Third Year, Computer Science & Engineering, Thapar Institute of Engineering & Technology, Patiala | CPG No. 300 | March–December 2026

---

## Motivation & Problem Statement

India's financial markets are increasingly sensitive to global geopolitical events — border conflicts, sanctions, commodity shocks, diplomatic crises — yet no dedicated, real-time, India-specific geopolitical intelligence platform exists.

**Existing tools fall short in three critical ways:**

| Gap | Problem | Forsyt's Solution |
|-----|---------|-------------------|
| **Western Bias** | Tools rely on Western media (NYT, FT, WSJ), missing India-specific regional events | 15–20 curated Indian news sources |
| **Temporal Lag** | Caldara GPR published monthly with 1-month delay | Daily index, updated every 24 hours |
| **No India Mapping** | Global tools don't map risk to Indian sectors, corridors, or portfolios | Sector-level + corridor-level risk mapping |

With **170 million+ active Demat accounts** in India as of 2024 — a 3.6× increase since 2020 — the demand for localized, data-driven geopolitical intelligence has never been greater.

---

## Features

### Core Capabilities

- **Automated News Aggregation** — Monitors 15–20 Indian news sources (RSS + web scraping) continuously, collecting 300–500 India-relevant articles daily
- **NLP Event Extraction** — Transformer-based NLP pipeline extracts structured geopolitical events (type, severity, India exposure, actors, locations, sectors) from raw articles
- **India AI-GPR Index** — Daily normalized geopolitical risk score (z-score, 2020–present) validated against Caldara-Iacoviello academic benchmark
- **Historical Backtesting** — Validated against 17 major Indian geopolitical events (26/11, Galwan, Pulwama, Farmers' Protests, etc.)

### Intelligence Modules

- **📰 News Intelligence System** — Converts raw news into structured, searchable geopolitical event database with severity and sector tagging
- **💼 Portfolio Risk Advisor** — Quantifies portfolio-level geopolitical exposure by sector weighting; identifies silent risk concentrations
- **🚢 Supply Chain Risk Screener** — Assesses risk across 8–12 major Indian trade corridors (China-India, Taiwan-India, Gulf routes, maritime lanes)
- **📈 Macro Forecasting Engine** — ML models (XGBoost + optional LSTM) predict Nifty 50 volatility regimes (HIGH_VOL vs NORMAL) using GPR + market features

### Explainable AI (XAI) Throughout

- **SHAP Integration** — Every prediction includes a SHAP breakdown showing which factors drove the output
- **Multi-Level Explanations** — Quick summary → Feature chart → Deep-dive waterfall plot
- **Natural Language Justifications** — SHAP values converted to plain-English explanations on the dashboard
- **Confidence Scoring** — Every extracted event and ML prediction carries a calibrated confidence score

### Platform

- **Interactive Dashboard** — Responsive web interface with real-time GPR charts, corridor maps, portfolio calculator, and XAI visualizations
- **Production Pipeline** — Automated daily cron execution, PostgreSQL storage, error handling, alerting, and monitoring

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                                 │
│  15-20 Indian News RSS Feeds + Web Scrapers + Official Sources      │
│  (Times of India, Economic Times, Hindu, PIB, MEA, Mint...)         │
└─────────────────────────┬───────────────────────────────────────────┘
                          │  300-500 articles/day
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│              PHASE 1 — DATA AGGREGATION PIPELINE                    │
│  RSS Parser → Full Article Extractor → Text Cleaner → Deduplicator  │
│  Output: raw_articles table (PostgreSQL)                            │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│              PHASE 2 — NLP EVENT EXTRACTION                         │
│  NER → Event Classification → Severity Scoring →                   │
│  India Exposure Scoring → Sector Tagging → Geo Tagging              │
│  Output: structured_events table (PostgreSQL)                       │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│              PHASE 3 — GPR INDEX CONSTRUCTION                       │
│  Daily Aggregation → Temporal Smoothing → Z-Score Normalization     │
│  Output: gpr_index table + Sub-indices (sector/corridor)            │
└──────────────┬──────────────────────────────┬───────────────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────┐    ┌─────────────────────────────────────┐
│  PHASE 4 — VALIDATION    │    │  PHASE 5 — FEATURE ENGINEERING      │
│  Caldara Correlation     │    │  GPR Lags + Market Features +       │
│  Event Backtesting       │    │  Corridor Features + Sector Weights │
│  Market Alignment Tests  │    │  Train/Test Split (2020–22/23–26)   │
└──────────────────────────┘    └──────────────────┬──────────────────┘
                                                   │
                                                   ▼
                                ┌─────────────────────────────────────┐
                                │  PHASE 6 — ML MODEL DEVELOPMENT     │
                                │  Logistic Regression (Baseline)     │
                                │  XGBoost (Primary)                  │
                                │  LSTM (Optional)                    │
                                │  SHAP Explainability Framework      │
                                └──────────────────┬──────────────────┘
                                                   │
                                                   ▼
                                ┌─────────────────────────────────────┐
                                │  PHASE 7 — INTELLIGENCE DASHBOARD   │
                                │  React.js Frontend + REST APIs      │
                                │  GPR Charts, Corridor Map,          │
                                │  Portfolio Calculator, XAI Views    │
                                └──────────────────┬──────────────────┘
                                                   │
                                                   ▼
                                ┌─────────────────────────────────────┐
                                │  PHASE 8 — USER TESTING & VALIDATION│
                                │  Two-Wave Testing (12-18 Users)     │
                                │  Finance / Supply Chain / Retail    │
                                └─────────────────────────────────────┘
```

---

## Modules

### Module 1: Data Aggregation Pipeline (`/ingestion`)

Continuously monitors and collects articles from 15–20 curated Indian news sources.

**Sources covered:**
- **National:** Times of India, The Hindu, Hindustan Times, Indian Express, NDTV
- **Business/Finance:** Economic Times, Mint, Business Standard, Financial Express, Moneycontrol
- **Regional:** Deccan Herald, Telegraph India, Tribune India
- **Official:** PIB (Press Information Bureau), Ministry of External Affairs
- **Optional Hindi:** Dainik Jagran, Amar Ujala

**Key functions:**
- RSS feed parsing (`feedparser`)
- Full article extraction (`newspaper3k`)
- Text cleaning and normalization
- URL-based deduplication (SHA-256 hashing)
- Automated scheduling (every 6 hours)

---

### Module 2: NLP Event Extraction (`/extraction`)

Transforms unstructured article text into structured geopolitical event records.

**Pipeline stages:**
1. Named Entity Recognition (NER) — actors, locations, organizations
2. Event type classification — 8 categories (military_conflict, sanctions, terrorism, protest, policy_change, diplomatic_tension, cyber_attack, economic_shock)
3. Severity scoring (0.0–1.0)
4. India exposure scoring (0.0–1.0)
5. Confidence scoring (0.0–1.0)
6. Sector tagging (IT, Energy, Banking, Pharma, etc.)
7. Geographic/corridor tagging

**Output schema per event:**
```json
{
  "event_id": "sha256_hash",
  "date": "YYYY-MM-DD",
  "event_type": "border_conflict",
  "severity": 0.78,
  "india_exposure": 0.85,
  "confidence": 0.92,
  "actors": ["China", "India"],
  "location": "Ladakh",
  "sectors_affected": ["Defense", "Energy"],
  "corridor_affected": "China-India (Ladakh)",
  "summary": "One-sentence event description"
}
```

---

### Module 3: India AI-GPR Index Builder (`/gpr_index`)

Aggregates structured events into a daily, normalized geopolitical risk index.

**Methodology:**
```
Step 1 — Raw Aggregation:
  GPR_raw(t) = Σ [severity_i × india_exposure_i × confidence_i]
               for all events on day t

Step 2 — Temporal Smoothing (3-day moving average):
  GPR_smoothed(t) = [GPR_raw(t-1) + GPR_raw(t) + GPR_raw(t+1)] / 3

Step 3 — Z-Score Normalization (rolling 12-month window):
  India_AI_GPR(t) = [GPR_smoothed(t) - μ_12m(t)] / σ_12m(t)
```

**Interpretation scale:**
| Score | Level | Interpretation |
|-------|-------|----------------|
| < 0 | Low | Below-average geopolitical risk |
| 0 – 1 | Moderate | Slightly elevated risk |
| 1 – 2 | Elevated | Significant risk above baseline |
| 2 – 3 | High | Major geopolitical event detected |
| > 3 | Critical | Extreme geopolitical stress |

---

### Module 4: ML Models & Explainability (`/ml_inference`)

Three application-specific ML models backed by a unified SHAP explainability framework.

**Application 1 — Supply Chain Corridor Risk:**
- Predicts risk scores (0–100) for 8–12 major trade corridors
- 7–14 day temporal forecast
- SHAP: explains which events drive corridor risk

**Application 2 — Portfolio Geopolitical Exposure:**
- Quantifies portfolio exposure by sector sensitivity weights
- Input: portfolio holdings (ticker + weight)
- Output: total GPR exposure score + SHAP-based sector decomposition

**Application 3 — Nifty 50 Volatility Regime Prediction:**
- Binary classification: HIGH_VOL vs NORMAL
- Train: 2020–2022 | Test: 2023–2026
- Target: F1 ≥ 0.60, ROC-AUC ≥ 0.65
- SHAP: identifies top drivers of each regime prediction

---

### Module 5: Intelligence Dashboard (`/dashboard`)

React.js web application with five core views:

| View | Description |
|------|-------------|
| **Home** | Real-time India AI-GPR score, risk level, event feed |
| **Corridor Risk** | Interactive map of 8–12 trade corridors color-coded by risk |
| **Portfolio Advisor** | Input holdings → exposure score + sector decomposition |
| **Macro Regime** | Current Nifty volatility regime + contributing factor chart |
| **Event Explorer** | Searchable event database with filters (type, severity, date) |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Language** | Python 3.10+ |
| **NLP Models** | Hugging Face Transformers (BERT-based), open-source |
| **ML Models** | XGBoost, scikit-learn, PyTorch (LSTM optional) |
| **Explainability** | SHAP (TreeExplainer, DeepExplainer) |
| **Database** | PostgreSQL 15+ |
| **Web Scraping** | feedparser, newspaper3k, BeautifulSoup4, Scrapy |
| **Market Data** | yfinance |
| **Frontend** | React.js, Recharts / D3.js, Tailwind CSS |
| **Backend API** | REST APIs (Python) |
| **Scheduling** | APScheduler / cron |
| **Version Control** | GitHub |
| **Development** | VS Code, Jupyter Notebook |
| **Cloud Execution** | Google Colab (model training) |
| **Containerization** | Docker (optional, for deployment) |

---

## Getting Started

### Prerequisites

Ensure the following are installed and configured on your system before proceeding.

**System Requirements:**
- OS: Ubuntu 22.04 / macOS 13+ / Windows 11 (WSL2 recommended)
- RAM: 8 GB minimum (16 GB recommended for model training)
- Storage: 10 GB free space minimum
- Internet connection required (for RSS feeds, API access, market data)

**Required Software:**

```bash
# Python 3.10 or higher
python --version   # Should output Python 3.10.x or above

# Node.js 18+ (for dashboard)
node --version     # Should output v18.x.x or above

# PostgreSQL 15+
psql --version     # Should output psql 15.x or above

# Git
git --version
```

**Install Python (if not installed):**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install python3.10 python3.10-venv python3-pip -y

# macOS (using Homebrew)
brew install python@3.10

# Windows
# Download from https://www.python.org/downloads/
```

**Install PostgreSQL (if not installed):**
```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib -y
sudo systemctl start postgresql
sudo systemctl enable postgresql

# macOS
brew install postgresql@15
brew services start postgresql@15

# Windows
# Download from https://www.postgresql.org/download/windows/
```

---

### Installation

**Step 1 — Clone the Repository**

```bash
git clone https://github.com/[YOUR_GITHUB_ORG]/forsyt.git
cd forsyt
```

**Step 2 — Create and Activate a Virtual Environment**

```bash
# Create virtual environment
python3.10 -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
.\venv\Scripts\activate
```

**Step 3 — Install Python Dependencies**

```bash
# Upgrade pip first
pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt
```

**Step 4 — Install Frontend Dependencies**

```bash
cd dashboard
npm install
cd ..
```

**Step 5 — Download NLP Model Weights**

```bash
# Run the model download script
python scripts/download_models.py
```

> This downloads the pre-trained transformer models from Hugging Face (~500 MB). Ensure a stable internet connection.

---

### Environment Configuration

**Step 1 — Copy the Example Environment File**

```bash
cp .env.example .env
```

**Step 2 — Fill in Required Values**

Open `.env` in your editor and configure the following:

```env
# ─── DATABASE ────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://forsyt_user:your_password@localhost:5432/forsyt_db
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=forsyt_db
DATABASE_USER=forsyt_user
DATABASE_PASSWORD=your_secure_password

# ─── NLP / AI MODELS ─────────────────────────────────────────────────────────
# If using a paid API for LLM-assisted extraction (optional)
OPENAI_API_KEY=your_openai_key_here          # Optional: leave blank for open-source only
HUGGINGFACE_TOKEN=your_hf_token_here         # Optional: required for gated models

# ─── MARKET DATA ─────────────────────────────────────────────────────────────
# yfinance does not require a key, but you can specify a Yahoo Finance proxy if needed
YFINANCE_PROXY=                              # Optional

# ─── PIPELINE CONFIGURATION ──────────────────────────────────────────────────
PIPELINE_SCHEDULE_HOURS=6                    # How often to run ingestion (hours)
MAX_ARTICLES_PER_RUN=600                     # Max articles to fetch per run
MIN_ARTICLE_LENGTH=100                       # Minimum word count to process

# ─── ALERT CONFIGURATION ─────────────────────────────────────────────────────
ALERT_EMAIL=your_email@example.com           # Email for pipeline failure alerts
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_smtp_user@gmail.com
SMTP_PASSWORD=your_smtp_app_password

# ─── LOGGING ─────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO                               # DEBUG / INFO / WARNING / ERROR
LOG_DIR=./logs

# ─── DASHBOARD ───────────────────────────────────────────────────────────────
REACT_APP_API_BASE_URL=http://localhost:8000
DASHBOARD_PORT=3000

# ─── DEPLOYMENT ──────────────────────────────────────────────────────────────
ENVIRONMENT=development                      # development / staging / production
```

> **Security Note:** Never commit your `.env` file. It is already listed in `.gitignore`.

---

### Database Setup

**Step 1 — Create PostgreSQL User and Database**

```bash
# Access PostgreSQL shell
sudo -u postgres psql

# Inside psql
CREATE USER forsyt_user WITH PASSWORD 'your_secure_password';
CREATE DATABASE forsyt_db OWNER forsyt_user;
GRANT ALL PRIVILEGES ON DATABASE forsyt_db TO forsyt_user;
\q
```

**Step 2 — Run Database Migrations**

```bash
python scripts/init_database.py
```

This creates all required tables:

| Table | Description |
|-------|-------------|
| `raw_articles` | Raw fetched articles from all sources |
| `structured_events` | NLP-extracted geopolitical events |
| `gpr_index` | Daily India AI-GPR scores (2020–present) |
| `corridor_risk` | Daily corridor risk scores per trade route |
| `sector_sensitivity` | Historical sector sensitivity weights |
| `ml_predictions` | Stored ML model outputs with SHAP values |
| `pipeline_logs` | Execution logs and error records |

**Step 3 — Verify Setup**

```bash
python scripts/verify_setup.py
```

Expected output:
```
✅ Database connection: OK
✅ All tables created: OK
✅ NLP models loaded: OK
✅ Market data (yfinance): OK
✅ RSS feed access (sample): OK
Setup complete. Ready to run.
```

---

## Running the Project

### Running the Data Pipeline

```bash
# Run once manually (fetch today's articles)
python ingestion/run_pipeline.py --mode once

# Run continuously on schedule (every 6 hours, as per .env)
python ingestion/run_pipeline.py --mode scheduled

# Run for a specific date range (backfill)
python ingestion/run_pipeline.py --mode backfill --start 2024-01-01 --end 2024-12-31

# Dry run (test without writing to database)
python ingestion/run_pipeline.py --mode once --dry-run
```

**Sample output:**
```
[2026-03-24 03:00:12] INFO  Starting ingestion run...
[2026-03-24 03:00:15] INFO  Fetching Times of India... 42 articles
[2026-03-24 03:00:18] INFO  Fetching Economic Times... 38 articles
[2026-03-24 03:00:20] INFO  Fetching The Hindu... 35 articles
...
[2026-03-24 03:04:01] INFO  Total fetched: 487 articles
[2026-03-24 03:04:03] INFO  After deduplication: 183 unique articles
[2026-03-24 03:04:04] INFO  Stored to database: 183 records
[2026-03-24 03:04:04] INFO  Ingestion complete. Duration: 232s
```

---

### Running the NLP Extraction

```bash
# Process articles from today
python extraction/run_extraction.py --date today

# Process articles from a specific date
python extraction/run_extraction.py --date 2026-03-24

# Process a date range
python extraction/run_extraction.py --start 2026-01-01 --end 2026-03-24

# Run with verbose output (shows each article processed)
python extraction/run_extraction.py --date today --verbose

# Run quality check (outputs accuracy report for sampled events)
python extraction/quality_check.py --sample-size 100
```

**Sample output:**
```
[2026-03-24 04:00:02] INFO  Loading NLP model...
[2026-03-24 04:00:08] INFO  Model loaded. Processing 183 articles...
[2026-03-24 04:02:41] INFO  Extracted 183 raw event records
[2026-03-24 04:02:42] INFO  After deduplication: 67 unique events
[2026-03-24 04:02:43] INFO  Events by type:
                            - border_conflict: 8
                            - policy_change: 22
                            - diplomatic_tension: 15
                            - economic_shock: 12
                            - other: 10
[2026-03-24 04:02:44] INFO  Average confidence: 0.81
[2026-03-24 04:02:44] INFO  Stored 67 structured events to database
```

---

### Running the GPR Index Builder

```bash
# Build GPR index for today
python gpr_index/build_index.py --date today

# Build GPR index for a date range
python gpr_index/build_index.py --start 2020-01-01 --end 2026-03-24

# Build full historical backfill (2020–present)
python gpr_index/build_index.py --mode backfill

# View current GPR score
python gpr_index/query_index.py --date today

# Export GPR series to CSV
python gpr_index/export_index.py --start 2020-01-01 --end 2026-03-24 --output gpr_export.csv
```

**Sample output:**
```
[2026-03-24 05:00:01] INFO  Building GPR index for 2026-03-24...
[2026-03-24 05:00:02] INFO  Events loaded: 67
[2026-03-24 05:00:02] INFO  GPR_raw: 12.43
[2026-03-24 05:00:02] INFO  GPR_smoothed: 11.87 (3-day moving average)
[2026-03-24 05:00:02] INFO  Rolling mean (12m): 10.52
[2026-03-24 05:00:02] INFO  Rolling std  (12m): 2.31
[2026-03-24 05:00:02] INFO  India_AI_GPR (normalized): +0.58σ → MODERATE
[2026-03-24 05:00:03] INFO  Index record stored successfully.
```

---

### Running ML Models

```bash
# ─── TRAIN MODELS ────────────────────────────────────────────────────────────

# Train all models (baseline + XGBoost)
python ml_inference/train.py --model all

# Train specific model
python ml_inference/train.py --model xgboost
python ml_inference/train.py --model logistic_regression
python ml_inference/train.py --model lstm            # Optional

# ─── EVALUATE MODELS ─────────────────────────────────────────────────────────

# Evaluate on test set (2023-2026)
python ml_inference/evaluate.py --model xgboost

# Run walk-forward validation
python ml_inference/evaluate.py --model xgboost --walk-forward

# ─── RUN INFERENCE ───────────────────────────────────────────────────────────

# Get today's volatility regime prediction
python ml_inference/predict.py --date today

# Get SHAP explanation for today's prediction
python ml_inference/explain.py --date today

# Generate SHAP summary plot (saves to /outputs/shap_summary.png)
python ml_inference/explain.py --plot summary

# ─── CORRIDOR & PORTFOLIO MODELS ─────────────────────────────────────────────

# Run corridor risk assessment
python ml_inference/corridor_risk.py --corridor "China-India"

# Run portfolio exposure analysis
python ml_inference/portfolio_risk.py --holdings portfolio_sample.json
```

---

### Running the Dashboard

```bash
# Start backend API server
python api/server.py --port 8000

# In a separate terminal, start the React frontend
cd dashboard
npm start
```

Open your browser at: **http://localhost:3000**

**Production build:**
```bash
cd dashboard
npm run build
# Serve build/ with any static server or Nginx
```

---

## Usage Examples

### Example 1: Get the Current India AI-GPR Score

```python
from forsyt.gpr_index import GPRIndex

gpr = GPRIndex()
result = gpr.get_current()

print(f"Date: {result['date']}")
print(f"GPR Score: {result['gpr_normalized']:.2f}σ")
print(f"Risk Level: {result['risk_level']}")
print(f"Top Contributing Events: {result['top_events']}")
```

**Output:**
```
Date: 2026-03-24
GPR Score: +0.58σ
Risk Level: MODERATE
Top Contributing Events: ['Iran oil tensions', 'India-China border talks', 'RBI policy review']
```

---

### Example 2: Analyze Portfolio Geopolitical Exposure

```python
from forsyt.ml_inference import PortfolioAdvisor

advisor = PortfolioAdvisor()

portfolio = {
    "TCS": 0.25,        # 25% IT
    "Infosys": 0.15,    # 15% IT
    "ONGC": 0.20,       # 20% Energy
    "HDFC": 0.20,       # 20% Banking
    "SunPharma": 0.20   # 20% Pharma
}

result = advisor.analyze(portfolio)

print(f"Total GPR Exposure: {result['total_exposure']}/100")
print("\nSector Breakdown:")
for sector, data in result['sector_breakdown'].items():
    print(f"  {sector}: {data['exposure']:.0f}/100 ({data['shap_contribution']:.1%} of total risk)")
print(f"\nExplanation: {result['natural_language_explanation']}")
```

**Output:**
```
Total GPR Exposure: 68/100

Sector Breakdown:
  IT (40%):      82/100  (48% of total risk)
  Energy (20%):  71/100  (28% of total risk)
  Banking (20%): 45/100  (18% of total risk)
  Pharma (20%):  22/100  (6% of total risk)

Explanation: Your portfolio carries HIGH geopolitical risk.
IT holdings are most exposed due to US-China tech decoupling tensions.
Consider reducing IT concentration or hedging with defensive Pharma/FMCG holdings.
```

---

### Example 3: Assess Trade Corridor Risk

```python
from forsyt.ml_inference import CorridorRisk

corridor = CorridorRisk()
result = corridor.assess("China-India-Ladakh")

print(f"Corridor: {result['corridor']}")
print(f"Risk Score: {result['risk_score']}/100  [{result['risk_level']}]")
print(f"7-Day Forecast: {result['forecast_7d']}/100")
print(f"\nSHAP Drivers:")
for driver in result['shap_drivers']:
    print(f"  +{driver['contribution']} — {driver['factor']}: {driver['explanation']}")
```

**Output:**
```
Corridor: China-India (Ladakh Border)
Risk Score: 82/100  [HIGH]
7-Day Forecast: 78/100

SHAP Drivers:
  +38 — Border Tension Index: Ladakh GPR sub-index at +2.4σ (3-month high)
  +24 — Diplomatic Events: 0 high-level bilateral meetings in past 30 days
  +12 — Historical Pattern: Monsoon season historically correlates with patrol incidents
  +8  — INR/CNY Volatility: Currency stress elevated during border tensions
```

---

### Example 4: Predict Nifty Volatility Regime

```python
from forsyt.ml_inference import MacroForecaster
from forsyt.explainability import SHAPExplainer

forecaster = MacroForecaster()
explainer = SHAPExplainer(forecaster.model)

prediction = forecaster.predict_today()
explanation = explainer.explain(prediction['features'])

print(f"Regime: {prediction['regime']}")
print(f"Probability: {prediction['probability_high_vol']:.1%}")
print(f"\nTop Drivers:")
for i, driver in enumerate(explanation['top_drivers'][:3], 1):
    print(f"  {i}. {driver['feature']}: {driver['direction']} (+{driver['contribution']:.1%} risk)")
```

**Output:**
```
Regime: NORMAL (leaning elevated)
Probability HIGH_VOL: 61%

Top Drivers:
  1. Crude Oil Return (+3.5% today): Increases risk (+15.2%)
  2. GPR_lag1 (+0.58σ): Moderate geopolitical elevation (+8.4%)
  3. Nifty Return yesterday (-0.8%): Negative momentum (+10.1%)
```

---

## API Reference

The Forsyt backend exposes a REST API consumed by the frontend dashboard.

### Base URL
```
Development:  http://localhost:8000
```

---

### Endpoints

#### `GET /api/gpr/current`
Returns the latest India AI-GPR score.

**Response:**
```json
{
  "date": "2026-03-24",
  "gpr_normalized": 0.58,
  "gpr_raw": 12.43,
  "risk_level": "MODERATE",
  "num_events": 67,
  "top_events": [
    {
      "summary": "Iran oil facility strike raises crude prices",
      "event_type": "economic_shock",
      "severity": 0.68,
      "sectors_affected": ["Energy", "Aviation"]
    }
  ],
  "updated_at": "2026-03-24T05:00:03Z"
}
```

---

#### `GET /api/gpr/history`
Returns historical GPR series.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | string (YYYY-MM-DD) | Yes | Start of date range |
| `end_date` | string (YYYY-MM-DD) | Yes | End of date range |
| `format` | string | No | `json` (default) or `csv` |

**Response:**
```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "count": 365,
  "data": [
    { "date": "2024-01-01", "gpr_normalized": 0.32, "risk_level": "LOW" },
    { "date": "2024-01-02", "gpr_normalized": 0.45, "risk_level": "MODERATE" },
    ...
  ]
}
```

---

#### `GET /api/events/feed`
Returns structured geopolitical events with optional filtering.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `date` | string | No | Filter by specific date |
| `event_type` | string | No | Filter by event type |
| `min_severity` | float | No | Minimum severity threshold (0.0–1.0) |
| `sector` | string | No | Filter by affected sector |
| `limit` | integer | No | Max results (default: 50) |

---

#### `GET /api/volatility/signal`
Returns ML-based volatility regime prediction with SHAP explanation.

**Response:**
```json
{
  "date": "2026-03-24",
  "regime": "NORMAL",
  "probability_high_vol": 0.61,
  "confidence": "MEDIUM",
  "shap_drivers": [
    {
      "feature": "crude_oil_return",
      "value": 0.035,
      "contribution": 0.152,
      "direction": "increases_risk",
      "explanation": "Oil up 3.5% — historically linked to elevated market stress"
    }
  ]
}
```

---

#### `POST /api/portfolio/exposure`
Analyzes geopolitical exposure for a given portfolio.

**Request Body:**
```json
{
  "holdings": {
    "TCS.NS": 0.25,
    "ONGC.NS": 0.20,
    "HDFCBANK.NS": 0.20,
    "SUNPHARMA.NS": 0.20,
    "INFY.NS": 0.15
  }
}
```

**Response:**
```json
{
  "total_exposure": 68,
  "risk_level": "HIGH",
  "sector_breakdown": {
    "IT": { "weight": 0.40, "exposure": 82, "shap_contribution": 0.48 },
    "Energy": { "weight": 0.20, "exposure": 71, "shap_contribution": 0.28 }
  },
  "natural_language_explanation": "Your portfolio carries HIGH geopolitical risk...",
  "recommendations": ["Reduce IT concentration", "Consider increasing Pharma allocation"]
}
```

---

#### `GET /api/corridor/risk`
Returns risk scores for all or a specific trade corridor.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `corridor` | string | Specific corridor name (optional — returns all if omitted) |
| `forecast_days` | integer | Number of days to forecast (default: 7) |

---

## Configuration

All configurable parameters are managed through `.env` (for secrets/environment) and `config/settings.yaml` (for application logic).

### `config/settings.yaml`

```yaml
# ─── NEWS SOURCES ─────────────────────────────────────────────────────────────
news_sources:
  max_sources: 20
  request_timeout_seconds: 10
  max_retries: 3
  backoff_factor: 2
  min_article_words: 100
  user_agent: "Forsyt-Bot/1.0 (Research Project; contact@forsyt.dev)"

# ─── NLP PIPELINE ─────────────────────────────────────────────────────────────
nlp:
  model_name: "bert-base-multilingual-cased"   # Change to preferred model
  batch_size: 32
  max_token_length: 512
  confidence_threshold: 0.50                   # Events below this are excluded
  high_confidence_threshold: 0.80

# ─── GPR INDEX ────────────────────────────────────────────────────────────────
gpr_index:
  smoothing_window_days: 3
  normalization_window_days: 365
  alert_threshold_sigma: 2.0                   # GPR spike alert (in σ)

# ─── ML MODELS ────────────────────────────────────────────────────────────────
ml:
  train_start: "2020-01-01"
  train_end: "2022-12-31"
  test_start: "2023-01-01"
  volatility_window_days: 10
  volatility_regime_percentile: 75
  walk_forward_retrain_months: 6
  xgboost:
    n_estimators: 100
    max_depth: 5
    learning_rate: 0.1
    subsample: 0.8

# ─── CORRIDORS ────────────────────────────────────────────────────────────────
corridors:
  monitored:
    - "China-India-Ladakh"
    - "Pakistan-India-Wagah"
    - "Bangladesh-India-Petrapole"
    - "Nepal-India-Raxaul"
    - "Strait-of-Malacca"
    - "Persian-Gulf"
    - "Red-Sea-Suez"
    - "Delhi-Mumbai-Industrial"

# ─── SECTORS ──────────────────────────────────────────────────────────────────
sectors:
  monitored:
    - "IT"
    - "Energy"
    - "Banking"
    - "Pharma"
    - "Manufacturing"
    - "Agriculture"
    - "Defense"
    - "Telecom"
    - "Metals"
    - "Automobiles"
```

---

## Testing

We maintain a comprehensive test suite across all modules.

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run tests for a specific module
pytest tests/test_ingestion.py -v
pytest tests/test_extraction.py -v
pytest tests/test_gpr_index.py -v
pytest tests/test_ml_models.py -v
pytest tests/test_api.py -v

# Run with coverage report
pytest tests/ --cov=forsyt --cov-report=html
# Open htmlcov/index.html in browser to view coverage

# Run only fast tests (skip slow integration tests)
pytest tests/ -v -m "not slow"

# Run integration tests only
pytest tests/ -v -m "integration"
```

### Test Coverage Targets

| Module | Target Coverage |
|--------|----------------|
| `ingestion/` | ≥ 80% |
| `extraction/` | ≥ 75% |
| `gpr_index/` | ≥ 85% |
| `ml_inference/` | ≥ 75% |
| `api/` | ≥ 80% |
| **Overall** | **≥ 78%** |

### Test Categories

```
tests/
├── unit/                    # Fast, isolated unit tests
│   ├── test_rss_parser.py
│   ├── test_deduplication.py
│   ├── test_gpr_formula.py
│   └── test_shap_output.py
├── integration/             # Slower tests requiring DB connection
│   ├── test_pipeline_end_to_end.py
│   ├── test_ml_training.py
│   └── test_api_endpoints.py
├── validation/              # Backtesting and benchmark validation
│   ├── test_caldara_correlation.py
│   ├── test_event_backtesting.py
│   └── test_ml_performance.py
└── fixtures/                # Sample data for tests
    ├── sample_articles.json
    ├── sample_events.json
    └── sample_portfolio.json
```

### Key Validation Tests

```bash
# Run Caldara GPR correlation test (requires historical index data)
pytest tests/validation/test_caldara_correlation.py -v
# Target: r ≥ 0.60, p < 0.05

# Run event backtesting (17 major Indian geopolitical events)
pytest tests/validation/test_event_backtesting.py -v
# Target: hit rate ≥ 80% (14/17 events)

# Run ML performance benchmark
pytest tests/validation/test_ml_performance.py -v
# Target: F1 ≥ 0.60, ROC-AUC ≥ 0.65
```

---

## Project Structure

```
forsyt/
│
├── ingestion/                    # Phase 1: Data aggregation pipeline
│   ├── rss_parser.py             # RSS feed fetcher and parser
│   ├── web_scraper.py            # Web scraper for non-RSS sources
│   ├── article_extractor.py      # Full article text extraction
│   ├── text_cleaner.py           # Text normalization and cleaning
│   ├── deduplicator.py           # URL-hash-based deduplication
│   ├── scheduler.py              # APScheduler-based scheduling
│   ├── run_pipeline.py           # Pipeline entry point
│   └── sources.yaml              # List of all 15-20 news sources
│
├── extraction/                   # Phase 2: NLP event extraction
│   ├── ner_tagger.py             # Named entity recognition
│   ├── event_classifier.py       # Event type classification
│   ├── severity_scorer.py        # Severity + India exposure scoring
│   ├── sector_tagger.py          # Sector and corridor tagging
│   ├── deduplicator.py           # Semantic event deduplication
│   ├── quality_check.py          # Accuracy validation on samples
│   └── run_extraction.py         # Extraction entry point
│
├── gpr_index/                    # Phase 3: GPR index construction
│   ├── aggregator.py             # Daily event aggregation
│   ├── smoother.py               # Temporal smoothing
│   ├── normalizer.py             # Z-score normalization
│   ├── build_index.py            # Index builder entry point
│   ├── query_index.py            # Index query utilities
│   └── export_index.py           # CSV/JSON export
│
├── validation/                   # Phase 4: Validation suite
│   ├── caldara_correlation.py    # Caldara GPR benchmark test
│   ├── event_backtesting.py      # 17-event backtesting
│   ├── market_alignment.py       # GPR vs Nifty volatility test
│   └── events_list.yaml          # 17 major events + expected spikes
│
├── ml_inference/                 # Phases 5-6: ML models
│   ├── feature_engineering.py    # Feature construction (GPR + market)
│   ├── label_construction.py     # Volatility regime labels
│   ├── train.py                  # Model training entry point
│   ├── evaluate.py               # Performance evaluation
│   ├── predict.py                # Inference entry point
│   ├── corridor_risk.py          # Corridor risk models
│   ├── portfolio_risk.py         # Portfolio exposure models
│   ├── macro_forecaster.py       # Nifty regime predictor
│   └── explain.py                # SHAP explainability
│
├── api/                          # REST API layer
│   ├── server.py                 # API server entry point
│   ├── routes/
│   │   ├── gpr_routes.py
│   │   ├── event_routes.py
│   │   ├── volatility_routes.py
│   │   ├── portfolio_routes.py
│   │   └── corridor_routes.py
│   └── schemas.py                # Pydantic response schemas
│
├── dashboard/                    # React.js frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── GPRChart.jsx
│   │   │   ├── CorridorMap.jsx
│   │   │   ├── PortfolioAdvisor.jsx
│   │   │   ├── RegimeIndicator.jsx
│   │   │   ├── EventExplorer.jsx
│   │   │   └── SHAPExplainer.jsx
│   │   ├── pages/
│   │   │   ├── Home.jsx
│   │   │   ├── Corridors.jsx
│   │   │   ├── Portfolio.jsx
│   │   │   ├── Macro.jsx
│   │   │   └── Events.jsx
│   │   └── App.jsx
│   ├── public/
│   └── package.json
│
├── models/                       # Saved model artifacts
│   ├── xgboost_regime_v1.pkl
│   ├── lr_baseline_v1.pkl
│   ├── corridor_risk_models/
│   └── sector_sensitivity_weights.json
│
├── notebooks/                    # Jupyter notebooks (exploration/analysis)
│   ├── 01_eda_news_data.ipynb
│   ├── 02_gpr_index_analysis.ipynb
│   ├── 03_caldara_validation.ipynb
│   ├── 04_ml_model_training.ipynb
│   └── 05_shap_analysis.ipynb
│
├── data/                         # Sample/reference data
│   ├── caldara_india_gpr.xlsx    # Caldara benchmark (downloaded)
│   ├── nifty50_historical.csv    # Nifty 50 historical prices
│   └── validation_events.yaml   # 17 backtesting events
│
├── scripts/                      # Utility scripts
│   ├── download_models.py        # Download NLP model weights
│   ├── init_database.py          # Database initialization
│   ├── verify_setup.py           # Setup verification
│   └── backfill_history.py       # Backfill 2020-present index
│
├── tests/                        # Full test suite (see Testing section)
├── config/
│   └── settings.yaml             # Application configuration
├── logs/                         # Pipeline execution logs (gitignored)
├── outputs/                      # Generated reports/plots (gitignored)
├── docs/                         # Extended documentation
│   ├── methodology.md
│   ├── validation_report.md
│   └── api_docs.md
│
├── .env.example                  # Environment template
├── .gitignore
├── requirements.txt              # Python dependencies
├── docker-compose.yml            # Docker configuration (optional)
├── Dockerfile                    # Container definition (optional)
└── README.md                     # This file
```

---

## Validation Strategy

Forsyt uses three independent validation methods to prove accuracy. Full details in `/docs/validation_report.md`.

### Validation 1: Academic Benchmark Correlation

| Metric | Target | Method |
|--------|--------|--------|
| Pearson r | ≥ 0.60 | Monthly correlation vs. Caldara-Iacoviello India GPR |
| p-value | < 0.05 | Significance test |

```bash
python validation/caldara_correlation.py --plot
```

### Validation 2: Historical Event Backtesting (17 Events)

| Category | Events | Detection Target |
|----------|--------|-----------------|
| Tier 1 — Security | 26/11, Uri, Pulwama, Galwan, Art. 370 | 100% (5/5) |
| Tier 2 — Political | Farmers Protests ×2, CAA, Manipur, Delhi Riots, COVID | ≥ 80% (5–6/7) |
| Tier 3 — Economic | Demonetization, Afghanistan, Sri Lanka, Bangladesh, GST | ≥ 60% (3/5) |
| **Overall** | | **≥ 80% (14/17)** |

```bash
python validation/event_backtesting.py --output backtesting_report.html
```

### Validation 3: ML Performance (Out-of-Sample 2023–2026)

| Metric | Target |
|--------|--------|
| F1 Score | ≥ 0.60 |
| ROC-AUC | ≥ 0.65 |
| Precision | ≥ 0.55 |
| Recall | ≥ 0.55 |

```bash
python ml_inference/evaluate.py --model xgboost --report
```

---

## Deployment

### Option 1: Local Development (Default)

Already covered in [Running the Project](#running-the-project). Suitable for development and testing.

### Option 2: Docker (Recommended for Reproducibility)

```bash
# Build and start all services
docker-compose up --build

# Run in background
docker-compose up -d

# Stop services
docker-compose down
```

The `docker-compose.yml` starts:
- `forsyt-db` — PostgreSQL 15
- `forsyt-pipeline` — Data ingestion + NLP pipeline
- `forsyt-api` — REST API server (port 8000)
- `forsyt-dashboard` — React frontend (port 3000)

### Option 3: Cloud Deployment (Google Cloud Run)

```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Build and push container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/forsyt-api

# Deploy to Cloud Run
gcloud run deploy forsyt-api \
  --image gcr.io/YOUR_PROJECT_ID/forsyt-api \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL=$DATABASE_URL
```

### Environment-Specific Notes

| Environment | Database | Pipeline | Dashboard |
|-------------|----------|----------|-----------|
| Development | Local PostgreSQL | Manual trigger | `npm start` |
| Docker | Docker PostgreSQL | Scheduled via cron | Docker container |
| Production | Cloud SQL | Cloud Scheduler | Static build + CDN |

---

## Contributing

We welcome contributions from the community and teammates. Please follow this workflow.

### Development Workflow

```bash
# 1. Fork the repository and clone your fork
git clone https://github.com/YOUR_USERNAME/forsyt.git
cd forsyt

# 2. Create a feature branch
git checkout -b feature/your-feature-name

# 3. Make your changes (follow code style guidelines below)

# 4. Run tests to ensure nothing is broken
pytest tests/ -v

# 5. Commit with a descriptive message
git add .
git commit -m "feat: add corridor risk forecast endpoint"

# 6. Push to your fork
git push origin feature/your-feature-name

# 7. Open a Pull Request on GitHub targeting the main branch
```

### Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat:     New feature
fix:      Bug fix
docs:     Documentation changes
test:     Adding or updating tests
refactor: Code restructuring without feature change
chore:    Build process or auxiliary tool changes
perf:     Performance improvement
```

**Examples:**
```
feat: add SHAP waterfall plot to portfolio advisor
fix: correct z-score normalization for edge case on sparse event days
docs: update API reference for /api/portfolio/exposure endpoint
test: add unit tests for text cleaning module
```

### Code Style

```bash
# Format code
black forsyt/ tests/

# Lint code
flake8 forsyt/ tests/ --max-line-length=100

# Type checking
mypy forsyt/

# Sort imports
isort forsyt/ tests/

# Run all style checks at once
make lint
```

### Pull Request Checklist

Before opening a PR, ensure:

- [ ] Code follows PEP 8 and project style (run `make lint`)
- [ ] All new functions have docstrings
- [ ] Tests written for new functionality
- [ ] All existing tests pass (`pytest tests/ -v`)
- [ ] `.env.example` updated if new env variables added
- [ ] `CHANGELOG.md` updated with a brief description
- [ ] PR description explains what changes were made and why
- [ ] No secrets, API keys, or personal data committed

### Reporting Issues

When reporting a bug, include:

1. **Description** — What happened vs. what you expected
2. **Steps to reproduce** — Minimal, reproducible example
3. **Environment** — OS, Python version, relevant package versions
4. **Logs** — Relevant error messages or stack traces
5. **Screenshots** — If applicable (especially for dashboard issues)

Use the GitHub Issues template at: `https://github.com/[YOUR_GITHUB_ORG]/forsyt/issues/new`

---

## Team

| Name | Role | Responsibilities |
|------|------|-----------------|
| **Devasya Kanwar** (102303749) | AI/ML Engineer | NLP pipeline design and predictive analytics |
| **Aaditi Verma** (102303603) | Domain Analyst | Geopolitical analysis and risk modelling |
| **Aadi Jain** (102303629) | Backend Developer | Data pipeline architecture and API development |
| **Vansh Gupta** (102303909) | Frontend Engineer | Dashboard design and data visualization |
| **Arianna Vohra** (102303934) | Project Manager | Financial analysis and project coordination |

**Mentors:**
- Dr. Jasmeet Singh — Assistant Professor, CSE, Thapar Institute
- Dr. Kapil Tomar — Assistant Professor, CSE, Thapar Institute

---

## Roadmap

### Phase I — Core Development (Weeks 1–10)
- [x] Repository setup and team onboarding
- [ ] Data aggregation pipeline (15-20 sources)
- [ ] NLP event extraction (≥75% accuracy)
- [ ] India AI-GPR Index construction (2020–present)

### Phase II — Validation & ML (Weeks 11–20)
- [ ] Caldara GPR correlation validation (target r ≥ 0.60)
- [ ] 17-event historical backtesting (target ≥ 80% hit rate)
- [ ] Feature engineering (14-15 features)
- [ ] XGBoost model training + evaluation (target F1 ≥ 0.60)
- [ ] SHAP explainability integration

### Phase III — Dashboard & Deployment (Weeks 21–27)
- [ ] REST API layer (5 core endpoints)
- [ ] React.js dashboard (5 modules)
- [ ] Corridor risk and portfolio advisor modules
- [ ] Performance optimization (API response < 500ms)

### Phase IV — Testing & Finalization (Weeks 28–34)
- [ ] Two-wave user testing (12–18 users)
- [ ] Wave 1 feedback implementation
- [ ] Wave 2 validation (target satisfaction ≥ 7.5/10)
- [ ] Final documentation and video demonstration
- [ ] Capstone presentation (December 2026)

### Future Enhancements (Post-Capstone)
- [ ] Hindi/regional language NLP support (Dainik Jagran, Amar Ujala)
- [ ] Social media signals integration (Twitter/X geopolitical sentiment)
- [ ] Real-time intraday GPR updates (sub-hourly)
- [ ] Options market volatility integration (India VIX)
- [ ] Expanded corridor coverage (50+ routes)
- [ ] Mobile application (React Native)
- [ ] B2B SaaS API offering for institutional clients
- [ ] Integration with NSE/BSE live data feeds

---

## FAQ

**Q: Does Forsyt provide financial advice?**
> No. Forsyt is a research and intelligence tool for informational purposes only. It is not a SEBI-registered investment advisor and should not be used as the sole basis for financial decisions.

**Q: How accurate is the India AI-GPR Index?**
> The index targets a Pearson correlation of ≥ 0.60 with the Caldara-Iacoviello benchmark and ≥ 80% detection rate on 17 historical events. Actual accuracy depends on news source quality and NLP model performance.

**Q: Can I use Forsyt for my own research project?**
> Yes, subject to the project's license. If you use Forsyt in academic work, please cite the project and relevant references.

**Q: Why Indian news sources instead of GDELT?**
> GDELT relies heavily on Western media and misses regional Indian events, state-level politics, and regulatory changes. Indian sources provide better coverage of events that actually affect Indian markets.

**Q: How much does it cost to run Forsyt?**
> The core system runs on free and open-source components. Optional paid components include LLM APIs for assisted extraction (~₹8,000–10,000 for 6 months) and cloud hosting (~₹3,000). Total estimated cost: ~₹17,000 for the full project duration.

**Q: What happens when an RSS feed breaks?**
> The pipeline logs the failure and sends an email alert. If a source fails for 3+ consecutive runs, it is flagged for manual review. Each source has a scraper fallback.

**Q: Can I add new news sources?**
> Yes. Add the source configuration to `ingestion/sources.yaml` and run the pipeline. New sources are automatically picked up on the next scheduled run.

**Q: Does Forsyt work offline?**
> No. The system requires an internet connection for RSS feeds, market data (yfinance), and optional LLM API calls.

---

## License

```
MIT License

Copyright (c) 2026 Forsyt Team — Thapar Institute of Engineering & Technology

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

See the full [LICENSE](LICENSE) file for details.

---

## References & Acknowledgements

### Core References

1. Caldara, D., & Iacoviello, M. (2022). Measuring Geopolitical Risk. *American Economic Review*, 112(4), 1194–1225.
2. Iacoviello, M., & Tong, J. (2026). The AI-GPR Index: Measuring Geopolitical Risk using Artificial Intelligence. *Federal Reserve Board Working Paper*.
3. Baker, S. R., Bloom, N., & Davis, S. J. (2016). Measuring Economic Policy Uncertainty. *Quarterly Journal of Economics*, 131(4), 1593–1636.
4. Devlin, J., et al. (2018). BERT: Pre-training of Deep Bidirectional Transformers. *arXiv:1810.04805*.
5. Chen, T., & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. *ACM SIGKDD 2016*.
6. Lundberg, S. M., & Lee, S.-I. (2017). A Unified Approach to Interpreting Model Predictions. *NeurIPS 2017*.
7. Hochreiter, S., & Schmidhuber, J. (1997). Long Short-Term Memory. *Neural Computation*, 9(8), 1735–1780.

### Acknowledgements

- **Thapar Institute of Engineering & Technology** — Institutional support and mentorship
- **Dr. Jasmeet Singh & Dr. Kapil Tomar** — Project guidance and mentorship
- **Hugging Face** — Open-source transformer model ecosystem
- **Caldara & Iacoviello** — Public release of India GPR benchmark data
- **NSE India** — Nifty 50 methodology and market data access

---

<div align="center">

**Forsyt** — Built at Thapar Institute of Engineering & Technology, Patiala

*Capstone Project CPG #300 | Computer Science & Engineering | 2025–2026*

[![GitHub](https://img.shields.io/badge/GitHub-forsyt-181717?style=flat-square&logo=github)](https://github.com/[YOUR_GITHUB_ORG]/forsyt)

</div>