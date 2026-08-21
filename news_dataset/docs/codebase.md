# Geopolitical News Dataset — Codebase Architecture

Technical map of the `news_dataset` package: ingestion → NLP → index construction → API → cloud automation.

**Theory (sourcing & dedup):** [theory.md](./theory.md)

---

## System overview

```
RSS feeds (9 sources)
    → geo_scheduler / scrape.yml
    → PostgreSQL (articles, feed health)
    → nlp/scheduler + nlp.yml
    → india_processed_*.parquet export
    → daily_index / hourly_refresh
    → gpr_index scripts (GPR + corridors)
    → sync_all() → Postgres (gpr_daily, corridor_daily, dual_signal)
    → api/server.py page bundles → React frontend
```

---

## 1. Ingestion layer

### `ingestion/feed_utils.py`

Low-level HTTP and RSS parsing.

| Function | Role |
|----------|------|
| `safe_get(url, timeout)` | Browser-like `User-Agent`; catches network errors |
| `parse_feed(url, retries, backoff)` | `feedparser` with exponential backoff (important on GitHub Actions IPs) |
| `parse_rss_time(entry)` | Normalizes `published_parsed` / `updated_parsed` |

### `ingestion/geo_pipeline.py`

Core extraction and filtering.

| Symbol | Role |
|--------|------|
| `TIER1_FEEDS` | StratNews, Bharat Shakti, Gateway House, ThePrint Defence — **every article ingested** |
| `TIER2_FEEDS` | India Today, The Hindu, TOI, NDTV, **Hindustan Times** (world RSS) — keyword filter |
| `matches_geopolitics(text)` | Keyword matrix → confidence + matched terms |
| `find_duplicate(title, published_at, recent_articles)` | Fuzzy dedup via `SequenceMatcher`; threshold **0.85** |
| `fetch_tier(tier)` | Poll one tier's feeds → candidate article dicts |

**Dedup window:** 2 hours (`DEDUP_WINDOW`). Duplicates keep `duplicate_of` pointing to the earliest canonical row.

### `ingestion/geo_scheduler.py`

| Function | Role |
|----------|------|
| `tier_due(tier, health, now)` | Respects tier intervals (Tier 1 ≈ 7 min, Tier 2 ≈ 12 min) |
| `run_cycle()` | Fetch due tiers → sort chronologically → dedup → `insert_geo_article` |
| `run_continuous()` | Local polling loop (`POLL_TICK` 60s) |
| `--once` | Single cycle for CI |

---

## 2. Database — `db.py`

PostgreSQL only (`DATABASE_URL` required at import).

| Table / helper | Purpose |
|----------------|---------|
| `articles` | Raw + NLP-tagged news rows |
| `geo_feed_health`, `geo_cycle_stats` | Scraper telemetry |
| `gpr_daily`, `corridor_daily` | Product index rows (≥ `INDIA_GPR_INDEX_START`) |
| `dual_signal_cache` | Serialized dual-signal JSON |
| `pipeline_runs` | Stage logs (nlp, hourly, daily) |
| `init_db()` | Creates schema on first use |
| `sync_all()` | Upserts GPR/corridor/dual-signal from CSV outputs |

---

## 3. NLP — `nlp/`

| Module | Role |
|--------|------|
| `run_extraction.py` | Theme/tone/location/GCAM tagging to article columns |
| `scheduler.py` | Hourly batch driver (`--once` for cron) |
| `locations.py` | Emits GDELT-style `V2Locations` blocks; imports `CORRIDOR_PLACES` from `gpr_index/scripts/corridors.py` |

Tagged articles export to **`gpr_index/data/india_processed/india_processed_YYYYMMDD.parquet`** for scoring.

---

## 4. Index pipelines

### `pipeline/daily_index.py` — authoritative end-of-day

For one UTC day (default yesterday):

1. Backfill missing parquets (last 14 days)
2. NLP batch (500 articles)
3. Export parquet for target day
4. If ≥ `required_parquet_days()` since Aug 9: `run_gpr_range()` + `sync_all()`
5. `refresh_dual_signal()`

**Important:** `run_gpr_range()` always scores **`india_processed/`** on cloud — never the merged GKG dir.

### `pipeline/hourly_refresh.py` — `platform_refresh`

1. NLP batch (200 articles, env `PLATFORM_REFRESH_NLP_BATCH`)
2. Backfill parquets
3. Export yesterday + today parquets
4. GPR/corridor with `dirty_days=[yesterday, today]`
5. `sync_all()` → Postgres
6. `refresh_dual_signal()`
7. Warm API caches (quality report, article images)

### `pipeline/gdelt_warmup.py` — local only

GKG download → preprocess → `merge_processed_dirs` → full GPR/corridor score → optional Postgres sync. See [`docs/GDELT_WARMUP.md`](../../docs/GDELT_WARMUP.md).

---

## 5. API — `api/server.py`

Unified Flask API (port **5001** in dev). Page bundles return one JSON payload per dashboard screen.

| Route | Handler |
|-------|---------|
| `GET /health` | Health snapshot |
| `GET /api/status` | Platform freshness (GPR, corridors, scrape) |
| `GET /api/events/feed` | Filtered tagged articles |
| `GET /api/news/image?link=` | Article image resolver |
| `GET /api/market/dual-signal` | Geo + NIFTY vol + joint stress |
| `GET /api/pages/home` | Home bundle |
| `GET /api/pages/macro` | Macro / dual-signal bundle |
| `GET /api/pages/news` | News feed bundle |
| `GET /api/pages/corridor` | Corridor board bundle |
| `GET /api/pages/portfolio` | Portfolio context bundle |
| `GET /api/pages/quality` | Accuracy / methodology report |

**Data layer:** `gpr_service.py` (Postgres primary, CSV fallback), `market_service.py`, `metrics_service.py`, `page_bundles.py`, `cache.py`.

**Production:** `gunicorn -c news_dataset/gunicorn.conf.py news_dataset.api.server:app`

---

## 6. GitHub Actions workflows

| Workflow | Schedule | Entrypoint |
|----------|----------|------------|
| `scrape.yml` | */25 min | `ingestion.geo_scheduler --once` |
| `nlp.yml` | hourly :10 | `nlp.scheduler --once` |
| `platform_refresh.yml` | hourly :20 | `pipeline.hourly_refresh` |
| `daily_index.yml` | 18:30 UTC | `pipeline.daily_index` |
| `catch_up_index.yml` | manual | Date-range backfill |

**Parquet cache:** `india-processed-parquets-v1` — accumulates daily parquets so GPR normalization has multi-day history.

**Cloud env:** `INDIA_GPR_INDEX_START=2026-08-09`. Do **not** set `GPR_INDEX_PROCESSED_DIR` in CI.

---

## 7. Key environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | — | Supabase Postgres (required) |
| `INDIA_GPR_INDEX_START` | `2026-08-09` | Product era start; Postgres sync cutoff |
| `GPR_WARMUP_START` | `2026-01-01` | GDELT warmup baseline (local) |
| `GPR_INDEX_PROCESSED_DIR` | unset | Set to merged `index_processed/` for local warmup only |
| `ALLOW_CSV_FALLBACK` | off | Offline dev only — masks stale DB data |

---

## 8. Local development

```bash
# Terminal 1 — API
python -m news_dataset.api.server

# Terminal 2 — frontend (proxies /api → :5001)
cd frontend && npm run dev
```

Verify freshness:

```bash
curl -s http://127.0.0.1:5001/api/status | python3 -m json.tool
```

See also: [`docs/CLOUD_PIPELINE.md`](../../docs/CLOUD_PIPELINE.md), [`docs/PRODUCT.md`](../../docs/PRODUCT.md).
