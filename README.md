# Forsyt — Geopolitical Risk Intelligence System for Indian Markets

<div align="center">

![Forsyt Banner](https://img.shields.io/badge/Forsyt-Geopolitical%20Intelligence-0057B7?style=for-the-badge&logo=globe&logoColor=white)

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active%20Development-orange?style=flat-square)]()
[![Institution](https://img.shields.io/badge/Institution-Thapar%20Institute-red?style=flat-square)]()
[![Capstone](https://img.shields.io/badge/Capstone-CPG%20300-blue?style=flat-square)]()

**A daily geopolitical risk intelligence platform for Indian financial markets.**

[Overview](#overview) · [Features](#features) · [Getting Started](#getting-started) · [Architecture](#system-architecture) · [Modules](#modules) · [API](#api-reference) · [Contributing](#contributing) · [Status](#status--roadmap)

</div>

---

Every section below describes code that actually exists and runs in this repository — nothing here is aspirational. For a beginner-friendly guided tour, start with **[`docs/SITEMAP.md`](docs/SITEMAP.md)** (map of the codebase) and **[`docs/GLOSSARY.md`](docs/GLOSSARY.md)** (plain-English terms). For the fuller "what's built vs. not" status, see **[`docs/PROJECT_GUIDE.md`](docs/PROJECT_GUIDE.md)** and **[`docs/PRODUCT.md`](docs/PRODUCT.md)**. A prior version of this README described a much larger, unbuilt system (ML/SHAP models, a `forsyt` Python package, Docker deployment, etc.) — that content has been removed; the full record of what was cut and why lives in **[`docs/DISCREPANCIES.md`](docs/DISCREPANCIES.md)**.

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
9. [Calling the API Directly](#calling-the-api-directly)
10. [API Reference](#api-reference)
11. [Configuration](#configuration)
12. [Testing](#testing)
13. [Project Structure](#project-structure)
14. [Validation Strategy](#validation-strategy)
15. [Contributing](#contributing)
16. [Team](#team)
17. [Status & Roadmap](#status--roadmap)
18. [FAQ](#faq)
19. [License](#license)
20. [References & Acknowledgements](#references--acknowledgements)

---

## Overview

**Forsyt** is a daily India geopolitical risk intelligence platform. It transforms unstructured Indian news into structured risk insights: a **daily GPR index**, **12 trade-corridor scores**, a **tagged event feed**, and a **dual-signal dashboard** (geo risk + NIFTY vol side-by-side — honest, not "GPR predicts NIFTY").

At its core, Forsyt builds the **India GPR Index** from 9 Indian news sources, validated against the Caldara-Iacoviello benchmark. The product surface is the **unified API + dashboard** — see [`docs/PRODUCT.md`](docs/PRODUCT.md) for the full product definition.

> **Capstone Project** — BE Third Year, Computer Science & Engineering, Thapar Institute of Engineering & Technology, Patiala | CPG No. 300 | 2026

---

## Motivation & Problem Statement

India's financial markets are increasingly sensitive to global geopolitical events — border conflicts, sanctions, commodity shocks, diplomatic crises — yet no dedicated, real-time, India-specific geopolitical intelligence platform exists.

**Existing tools fall short in three ways:**

| Gap | Problem | Forsyt's Approach |
|-----|---------|-------------------|
| **Western bias** | Global GPR tools rely on Western media, missing India-specific regional events | 9 curated Indian news sources — 4 defence-focused feeds ingested unfiltered, plus 5 mainstream feeds passed through a geopolitics keyword filter |
| **Temporal lag** | The academic Caldara-Iacoviello GPR index is published monthly, with a delay | A daily index, refreshed via scheduled jobs roughly every 25 minutes to hourly |
| **No India mapping** | Global tools don't map risk to specific Indian trade routes | 12 India-relevant trade-corridor risk scores, weighted by real energy/goods trade exposure |

With **170 million+ active Demat accounts** in India as of 2024, the demand for localized, data-driven geopolitical intelligence is real — this project is a capstone-scale attempt at that, not a production financial product.

---

## Features

### Shipped today

- **Automated news ingestion** — polls 9 Indian RSS feeds on a schedule, deduplicates near-identical headlines
- **NLP tagging** — every article gets a theme classification (sentence-transformer embedding match), a tone/GCAM score (lexicon-based), and location/corridor tags (regex-based)
- **India GPR Index** — a daily normalized geopolitical risk score, built with the same scoring method as the academic GDELT-GKG GPR replication, calibrated so an average day ≈ 100
- **12-corridor risk board** — Strait of Hormuz, Malacca, the India-China LAC border, Red Sea/Suez, and 8 others, each scored independently
- **Dual-signal dashboard** — the geo-risk regime shown side-by-side with a market-only NIFTY volatility forecast, plus a transparent joint-stress composite
- **6-page React dashboard** — Home, News, Macro, Trade Corridor, Portfolio, Quality (see [Modules](#modules))
- **Fully automated cloud pipeline** — GitHub Actions keep news, NLP tags, the GPR index, and the dual-signal cache fresh; no developer laptop needs to be running

### Explicitly not built (see `docs/PRODUCT.md` for the full "planned" list)

- A portfolio allocation engine or SHAP-based explainability — the Portfolio page is informational/illustrative only, not a real allocation tool
- Any ML model beyond the NIFTY volatility forecaster in `nifty-50/forsyt_gpr/` (which is internal QA, not a public-facing feature)

---

## System Architecture

```mermaid
flowchart LR
    RSS["9 Indian RSS feeds"] -->|scrape ~every 7-12 min| ND["news_dataset/\ningestion + NLP tagging"]
    ND -->|writes articles| DB[(PostgreSQL\nvia Supabase)]
    ND -->|export tagged articles\nas Parquet| GPR["gpr_index/\nscoring engine"]
    GPR -->|writes daily CSVs,\nsyncs back| DB
    N50["nifty-50/forsyt_gpr\n(NIFTY volatility model)"] -.->|imported by| ND
    DB -->|read by| API["news_dataset/api/server.py\n(Flask, port 5001)"]
    API -->|JSON| FE["frontend/\nReact dashboard"]
    GDELT[["GDELT (external database)\none-time historical calibration only"]] -.-> GPR
```

RSS feeds → Postgres → NLP tagging (sentence-transformer theme classifier + lexicon tone scoring + regex location extraction) → GDELT-schema Parquet export → `gpr_index`'s scoring engine → Postgres → Flask API → React dashboard, with `nifty-50`'s volatility model plugged into the API layer as a side input. See [`docs/SITEMAP.md`](docs/SITEMAP.md) for a folder-by-folder walkthrough.

---

## Modules

### Module 1 — News ingestion & NLP tagging (`news_dataset/ingestion/`, `news_dataset/nlp/`)

Polls 9 Indian RSS feeds, split into two tiers:

- **Tier 1** (4 feeds, ingested unfiltered): StratNews Global, Bharat Shakti, Gateway House, ThePrint Defence
- **Tier 2** (5 feeds, filtered to World/International sections + a geopolitics keyword match): India Today, The Hindu, Times of India, NDTV, Hindustan Times

Every stored article gets tagged with:
- a **theme** (sentence-transformer similarity match against ~24 GDELT-style taxonomy codes like `ARMEDCONFLICT`, `SANCTION`)
- a **tone/GCAM score** (word-list-density scoring, not a trained sentiment model)
- **location/corridor tags** (regex-based country and place-name matching)

### Module 2 — India GPR Index (`gpr_index/`)

Aggregates tagged articles into a daily, normalized geopolitical risk index, replicating the Caldara & Iacoviello / Iacoviello & Tong GDELT-GKG methodology. Full math in [`gpr_index/docs/gpr-theory.md`](gpr_index/docs/gpr-theory.md); corridor-specific math in [`gpr_index/docs/corridor-theory.md`](gpr_index/docs/corridor-theory.md).

| Regime | Approx. sigma band |
|--------|------|
| LOW | < 0σ |
| MODERATE | 0–1σ |
| ELEVATED | 1–2σ |
| HIGH | 2–3σ |
| CRITICAL | > 3σ |

### Module 3 — NIFTY volatility model (`nifty-50/forsyt_gpr/`)

A purged walk-forward-validated model forecasting NIFTY 50's forward 5-day realized volatility from market features, with GPR features tested (and found *not* to add out-of-sample value — see [Validation Strategy](#validation-strategy)). Powers the dual-signal panel via `dual_signal.py`, not a standalone product surface.

### Module 4 — Dashboard (`frontend/`)

React 19 + TypeScript + Vite + Tailwind v4 app with 6 pages:

| Route | Page | What it shows |
|------|------|------|
| `/` | Home | Today's verdict, a rotating globe (d3-geo) with risk arcs to top corridors |
| `/news` | News Intelligence | Filterable tagged headline feed |
| `/macroeconomics` | Macro | Geo regime + NIFTY vol side-by-side, joint-stress gauge, historical analogs |
| `/trade-corridor` | Trade & Corridor Risk | Interactive world map (d3-geo/d3-zoom) of all 12 corridors, per-route detail |
| `/portfolio-exposure` | Portfolio | Illustrative sector-sensitivity view driven by the live regime — not a real allocation tool |
| `/quality` | Platform Quality | Validation summary, per-feed health, methodology walkthrough |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend language** | Python 3.10+ |
| **Backend framework** | Flask, served by Gunicorn in production |
| **Theme tagging** | `sentence-transformers` (`distiluse-base-multilingual-cased-v2`) |
| **Tone/GCAM scoring** | Hand-built lexicon (no trained sentiment model) |
| **Volatility model** | XGBoost, purged walk-forward validation (`nifty-50/forsyt_gpr/`) |
| **Database** | PostgreSQL 15+ (hosted via Supabase) |
| **Web scraping** | `feedparser` (RSS only, no full-page scraping) |
| **Market data** | `yfinance`, with a bundled NIFTY CSV fallback |
| **Frontend** | React 19 + TypeScript + Vite + Tailwind CSS v4 |
| **Data fetching** | `@tanstack/react-query` |
| **Maps/visualization** | `d3-geo`, `d3-zoom`, `d3-selection`, `topojson-client`, `world-atlas` (hand-rolled canvas charts, no chart library) |
| **Scheduling/automation** | GitHub Actions (5 scheduled workflows — see [`docs/CLOUD_PIPELINE.md`](docs/CLOUD_PIPELINE.md)) |
| **Data interchange** | Parquet (via `pandas`/`pyarrow`) between `news_dataset` and `gpr_index` |
| **Version control** | Git / GitHub |

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ (for the frontend)
- Git
- A [Supabase](https://supabase.com) Postgres project (no local PostgreSQL install needed)

```bash
python --version   # 3.10.x or above
node --version     # v18.x.x or above
git --version
```

### Installation

**Step 1 — Clone the repository**

```bash
git clone https://github.com/[YOUR_GITHUB_ORG]/forsyt.git
cd forsyt
```

**Step 2 — Create and activate a virtual environment**

```bash
python3.10 -m venv venv
source venv/bin/activate      # Windows: .\venv\Scripts\activate
```

**Step 3 — Install Python dependencies** (there is no root `requirements.txt` — install per module)

```bash
pip install --upgrade pip
pip install -r news_dataset/requirements.txt
pip install -r news_dataset/requirements-nlp.txt
pip install -r gpr_index/requirements.txt
pip install -r nifty-50/requirements.txt
```

**Step 4 — Install frontend dependencies**

```bash
cd frontend && npm install && cd ..
```

The theme-tagging model (`sentence-transformers/distiluse-base-multilingual-cased-v2`) downloads automatically from Hugging Face (~500MB) the first time `news_dataset/nlp/themes.py` runs — no separate download step.

### Environment Configuration

```bash
cp news_dataset/.env.example news_dataset/.env
```

Open `news_dataset/.env` and set your Supabase connection string:

```env
DATABASE_URL=postgresql://postgres.xxxx:password@aws-0-region.pooler.supabase.com:6543/postgres
```

> **Security note:** never commit your `.env` file — it's already in `.gitignore`.

### Database Setup

Forsyt stores all news and indices in **Supabase Postgres**. Tables (`articles`, `gpr_daily`, `corridor_daily`, `dual_signal_daily`, `pipeline_runs`, etc.) are created automatically on first import of `news_dataset.db` — no migration scripts or local Postgres install required.

Also add `DATABASE_URL` as a GitHub Actions secret so the scheduled workflows can run.

---

## Running the Project

Postgres (Supabase) is the source of truth. GitHub Actions keep news, GPR, corridors, and the dual-signal cache fresh in production — a local checkout only needs to run the API and frontend, never the ingestion/scoring pipeline itself (unless you're doing a local GDELT warmup, below).

```bash
# Terminal 1 — API (port 5001)
source "$HOME/.venv/forsyt/bin/activate"
cd "/path/to/Forsyt"
python -m news_dataset.api.server

# Terminal 2 — frontend
cd frontend && npm run dev
```

Open **http://127.0.0.1:5173**. Check freshness without opening Supabase:

```bash
curl -s http://127.0.0.1:5001/api/status | python3 -m json.tool
curl -s http://127.0.0.1:5001/health | python3 -m json.tool
```

**Production** (≤10 concurrent users) — Gunicorn with the bundled config (1 worker, 4 threads, shared in-memory cache):

```bash
gunicorn -c news_dataset/gunicorn.conf.py news_dataset.api.server:app
```

**Production frontend build:**

```bash
cd frontend
cp .env.example .env   # set VITE_API_BASE to your deployed API origin
npm run build
npm run preview
```

### Cloud automation (you do not run these locally)

| Workflow | Schedule | Purpose |
|----------|----------|---------|
| `scrape.yml` | every 25 min | ingest headlines → Postgres |
| `nlp.yml` | hourly | NLP tagging |
| `platform_refresh.yml` | hourly | GPR + corridors + dual-signal sync |
| `daily_index.yml` | daily | authoritative end-of-day close |
| `catch_up_index.yml` | manual | backfill a date range |

After merging pipeline changes, run **Actions → Catch up index → Run workflow** once to backfill missing days. See [`docs/CLOUD_PIPELINE.md`](docs/CLOUD_PIPELINE.md) for the full push + verify checklist.

To run any of the underlying pipeline steps by hand instead of waiting for the schedule:

```bash
python -m news_dataset.ingestion.geo_scheduler --once   # one ingestion cycle
python -m news_dataset.nlp.run_extraction                # tag pending articles
python gpr_index/main.py gpr                              # score + normalize
python gpr_index/main.py fill-gaps                        # impute calendar gaps
python gpr_index/main.py corridor                          # score the 12 corridors
```

### GDELT warmup (optional, local-only — stronger 7-day moving average)

Before `INDIA_GPR_INDEX_START` (2026-08-09), the index can borrow **global GDELT GKG** parquets purely to calibrate normalization baselines. Nothing from this step is inserted into Postgres — the product still starts at the India-news era.

```bash
python -m news_dataset.pipeline.gdelt_warmup --warmup-start 2026-01-01 --slot-step 4
```

See [`docs/GDELT_WARMUP.md`](docs/GDELT_WARMUP.md) for the full runbook. Do **not** add GDELT download to GitHub Actions — it's a local-only convenience.

---

## Calling the API Directly

No client library exists — call the Flask API directly.

```bash
curl http://127.0.0.1:5001/api/pages/home        # today's GPR score, top corridor, quotes
curl http://127.0.0.1:5001/api/pages/corridor     # all 12 corridor risk scores
curl "http://127.0.0.1:5001/api/events/feed?limit=20&theme=ARMEDCONFLICT"
curl http://127.0.0.1:5001/api/market/dual-signal
```

---

## API Reference

The Forsyt backend exposes a REST API (`news_dataset/api/server.py`), consumed by the React frontend and callable directly. All routes are `GET`.

| Endpoint | Description |
|----------|-------------|
| `GET /api/pages/home` | Home bundle (health, GPR, corridors, quotes) |
| `GET /api/pages/macro` | Macro bundle (dual signal, GPR history, market histories) |
| `GET /api/pages/news` | News bundle (events, GPR, history) |
| `GET /api/pages/corridor` | Corridor bundle (scores, metadata, events) |
| `GET /api/pages/portfolio` | Portfolio bundle |
| `GET /api/pages/quality` | Quality / accuracy report |
| `GET /api/events/feed` | Filtered NLP-tagged articles (`limit`, `theme`, `corridor`, `tier`, `start`, `end`, `tagged_only`) |
| `GET /api/news/image?link=` | On-demand article image resolver |
| `GET /api/market/dual-signal` | Geo + NIFTY vol + joint stress (refresh with `?refresh=1`) |
| `GET /health`, `GET /api/status` | Ops health and platform status |

```
Development API:  http://localhost:5001
React dev (Vite): http://localhost:5173
```

---

## Configuration

Configuration is via `.env` files per module (`news_dataset/.env`, `frontend/.env`), plus a few env-overridable constants in `gpr_index/scripts/paths.py`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `GPR_WARMUP_START` | `2026-01-01` | GDELT-warmup calibration baseline start |
| `INDIA_GPR_INDEX_START` | `2026-08-09` | Product era start; Postgres sync cutoff |
| `GPR_INDEX_PROCESSED_DIR` | unset (India-only) | Set to `gpr_index/data/index_processed` for local warmup scoring |
| `DATABASE_URL` | — | Supabase Postgres connection string |
| `VITE_API_BASE` | empty (dev) | Frontend's API origin in production |
| `ALLOW_CSV_FALLBACK` | unset | Lets the API fall back to committed CSVs when Postgres/live data isn't available — leave unset unless working offline |

See [`docs/GDELT_WARMUP.md`](docs/GDELT_WARMUP.md) for the full list and [`gpr_index/scripts/gkg_gpr_pipeline.py`](gpr_index/scripts/gkg_gpr_pipeline.py) for the hardcoded scoring constants (theme/tone/GCAM caps, tail exponent).

---

## Testing

```bash
python -m pytest gpr_index/tests/ -q
```

`gpr_index/tests/` (4 files, `unittest`-based, 32 tests) cover the GPR scoring, normalization, split-era, and corridor-matching logic — the most numerically sensitive part of the codebase. `news_dataset/` and `nifty-50/` currently have no automated test suite; the frontend is checked with `npx tsc -b --noEmit` and `npx oxlint` (no unit tests).

---

## Project Structure

```
Forsyt/
├── frontend/            # React dashboard (Vite + TypeScript + Tailwind)
│   ├── src/
│   │   ├── pages/       # One file per dashboard screen
│   │   ├── components/  # Reusable UI (charts, maps, cards, header/footer)
│   │   ├── hooks/       # Data-fetching hooks
│   │   ├── lib/         # API client, copy/label logic, chart drawing
│   │   └── assets/
│   └── docs/ARCHITECTURE.md
│
├── news_dataset/        # Scraping, NLP tagging, and the Flask API
│   ├── ingestion/       # RSS polling, deduplication
│   ├── nlp/             # Theme/tone/location tagging
│   ├── export/          # Parquet export to gpr_index, CSV sync back from it
│   ├── pipeline/        # Orchestration scripts (what GitHub Actions run)
│   ├── api/             # Flask app + service layer
│   ├── db.py            # All PostgreSQL access
│   └── docs/{codebase,theory}.md
│
├── gpr_index/           # The GPR + corridor scoring engine
│   ├── main.py          # CLI entry point
│   ├── scripts/         # Scoring, normalization, corridor logic
│   ├── tests/           # 32 unit tests
│   ├── outputs/         # Generated CSVs/plots (tracked in git)
│   └── docs/{gpr-theory,corridor-theory}.md
│
├── nifty-50/            # NIFTY volatility model + dual-signal product layer
│   ├── forsyt_gpr/       # data.py, features.py, vol_model.py, dual_signal.py
│   └── docs/INTEGRATION.md
│
├── report/              # Academic capstone report (LaTeX) — not code-dependent
├── docs/                # Project-wide documentation (this file's companions)
├── .github/workflows/   # 5 scheduled GitHub Actions jobs
└── README.md
```

See [`docs/SITEMAP.md`](docs/SITEMAP.md) for a fuller, annotated walkthrough of every subfolder.

---

## Validation Strategy

Forsyt uses **product KPIs** (pipeline reliability + index credibility), not ML headline scores.

### Product success metrics

| Metric | Target | Method |
|--------|--------|--------|
| Pipeline uptime | 30 consecutive daily runs | GitHub Actions `daily_index.yml` |
| Index freshness | GPR updated within 24h | `gpr_daily.updated_at` vs scrape time |
| Caldara correlation | Monthly r ≥ 0.50 | `gpr_index/scripts/validate_gpr.py` |
| Event detection | GPR spike within 3 days | Galwan, Pulwama, 26/11 manual check |
| Corridor sanity | Top corridor matches news | Compare `/api/pages/corridor` to event feed |

### Research validation (internal QA, not product-facing)

| Check | Location |
|-------|----------|
| OOS NIFTY vol backtest (purged walk-forward) | `nifty-50/forsyt_gpr/vol_model.py` |
| GPR vs Caldara benchmark | `gpr_index/scripts/validate_gpr.py` |
| Platform accuracy dashboard | `/quality` (API: `/api/pages/quality`) |

**Honest finding:** GPR does not beat market-only vol forecasts out-of-sample (market-only ROC-AUC ≈0.831 vs. market+GPR ≈0.815) — the product shows both signals side-by-side rather than overclaiming.

---

## Contributing

```bash
git checkout -b feature/your-feature-name
# make your changes
python -m pytest gpr_index/tests/ -q   # if you touched gpr_index/
cd frontend && npx tsc -b --noEmit && npx oxlint && cd ..   # if you touched frontend/
git add <files>
git commit -m "feat: add corridor risk forecast endpoint"
git push origin feature/your-feature-name
```

Then open a Pull Request targeting `main`. Keep commits reasonably scoped, and don't commit `.env` files or secrets.

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

## Status & Roadmap

Full detail in [`docs/PROJECT_GUIDE.md`](docs/PROJECT_GUIDE.md) §3. In short:

**Done:** RSS scraping (9 sources), NLP tagging, India GPR index with split-era normalization, 12-corridor risk scoring, the 6-page dashboard, the dual-signal panel, and the fully automated GitHub Actions cloud pipeline.

**Not built, and not currently planned for the capstone demo:**
- A real portfolio allocation engine (the Portfolio page is illustrative only)
- SHAP or any other model-explainability layer
- Full article text extraction (only the RSS summary is stored today, ~40 words/article)
- Historical event backtesting as an automated test suite (currently a manual spot-check)

**Genuinely on the roadmap:**
- Hindi/regional-language source coverage
- Expanded corridor set beyond the current 12

---

## FAQ

**Q: Does Forsyt provide financial advice?**
> No. Forsyt is a research and intelligence tool for informational purposes only. It is not a SEBI-registered investment advisor and should not be used as the sole basis for financial decisions.

**Q: How accurate is the India GPR Index?**
> The index targets a Pearson correlation of ≥ 0.50 with the Caldara-Iacoviello benchmark (the actual pass threshold used in `gpr_index/scripts/validate_gpr.py`). Actual accuracy depends on news source quality and NLP tagging quality.

**Q: Can I use Forsyt for my own research project?**
> Yes, subject to the project's MIT license. If you use Forsyt in academic work, please cite the project and the references below.

**Q: Why Indian news sources instead of GDELT for live data?**
> GDELT relies heavily on Western media and misses regional Indian events and state-level politics. GDELT is still used, but only as a one-time historical dataset to calibrate normalization baselines — see [`docs/GDELT_WARMUP.md`](docs/GDELT_WARMUP.md).

**Q: What happens when an RSS feed breaks?**
> `news_dataset/db.py` tracks per-feed health (`geo_feed_health`), visible on the `/quality` dashboard page. There's no automated email alerting today.

**Q: Can I add new news sources?**
> Yes — add the feed to `TIER1_FEEDS` or `TIER2_FEEDS` in `news_dataset/ingestion/geo_pipeline.py`. It's picked up on the next scheduled ingestion cycle.

**Q: Does Forsyt work offline?**
> No — it needs an internet connection for RSS feeds, Postgres (Supabase), and market data (`yfinance`).

---

## License

MIT License — Copyright (c) 2026 Forsyt Team, Thapar Institute of Engineering & Technology. See the full [LICENSE](LICENSE) file for details.

---

## References & Acknowledgements

### Core references (methods actually used in this codebase)

1. Caldara, D., & Iacoviello, M. (2022). Measuring Geopolitical Risk. *American Economic Review*, 112(4), 1194–1225.
2. Iacoviello, M., & Tong, J. (2026). The AI-GPR Index: Measuring Geopolitical Risk using Artificial Intelligence. *Federal Reserve Board Working Paper*.
3. Chen, T., & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. *ACM SIGKDD 2016*. (Used in `nifty-50/forsyt_gpr/vol_model.py`.)
4. Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. *EMNLP 2019*. (The `sentence-transformers` library used for theme tagging.)
5. Leetaru, K., & Schrodt, P. A. (2013). GDELT: Global Data on Events, Location and Tone. (The historical dataset used for warmup calibration.)

### Acknowledgements

- **Thapar Institute of Engineering & Technology** — Institutional support and mentorship
- **Dr. Jasmeet Singh & Dr. Kapil Tomar** — Project guidance and mentorship
- **Hugging Face** — Hosting the open-source `sentence-transformers` model used for theme tagging
- **Caldara & Iacoviello** — Public release of the GPR benchmark data this project validates against
- **NSE India** — NIFTY 50 methodology and market data reference

---

<div align="center">

**Forsyt** — Built at Thapar Institute of Engineering & Technology, Patiala

*Capstone Project CPG #300 | Computer Science & Engineering | 2026*

[![GitHub](https://img.shields.io/badge/GitHub-forsyt-181717?style=flat-square&logo=github)](https://github.com/[YOUR_GITHUB_ORG]/forsyt)

</div>
