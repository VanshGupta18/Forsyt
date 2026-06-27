# Forsyt — India GPR Research Pipeline

Dual-source Geopolitical Risk Index for India, implementing Iacoviello & Tong (2026) methodology on two parallel news corpora:

- **News path** — 10 Indian newspapers (5 English + 5 Hindi), scraped live, forward from anchor day
- **GKG path** — GDELT Global Knowledge Graph, historical

Both paths use the same GPR scorer (`scripts/gkg_gpr_pipeline.py`) and validation suite.

---

## Repository layout

```
Forsyt/
│
├── main.py                      # Single CLI entry point
├── requirements.txt
├── pyproject.toml
│
├── scraper/                     # Layer 1a — Live ingest (10 outlets)
│   ├── __main__.py              # python -m scraper {schedule|once|api}
│   ├── scheduler.py             # 5-min async RSS → SQLite → JSONL
│   ├── fetcher.py               # aiohttp client
│   ├── db.py                    # SQLite schema
│   ├── api.py                   # Flask read API
│   └── outlets/                 # One module per newspaper
│       ├── base.py              # BaseOutlet ABC
│       ├── the_hindu.py         # TH  en
│       ├── times_of_india.py    # TOI en
│       ├── indian_express.py    # TIE en
│       ├── india_today.py       # IT  en
│       ├── ndtv.py              # NDTV en
│       ├── amar_ujala.py        # AU  hi
│       ├── bbc_hindi.py         # BBC hi
│       ├── oneindia_hindi.py    # OI  hi
│       ├── live_hindustan.py    # LH  hi
│       └── news18_hindi.py      # N18 hi
│
├── scripts/                     # Layers 2–4 — Pipeline logic
│   │
│   │  ── Shared GPR core ──
│   ├── gkg_gpr_pipeline.py      # Score + aggregate → daily/monthly/event/country
│   ├── theme_tagger.py          # DistilBERT theme + tone tagging
│   ├── tag_cache.py             # SQLite cache for tagging results
│   ├── location_tagger.py       # Country-mention → V2Locations (news path)
│   ├── fill_gpr_gaps.py         # Caldara imputation (pre-anchor only for news)
│   ├── validate_gpr.py          # 10-check validation vs Caldara
│   ├── compare_gpr_sources.py   # News vs GKG diff report
│   ├── diagnose_gpr_scoring.py
│   ├── plot_gpr.py
│   ├── reprocess_gpr_index.py
│   │
│   │  ── News path ──
│   ├── export_news_db.py        # SQLite → india_raw/ JSONL
│   ├── preprocess_indian_news.py# JSONL → india_processed/ parquet
│   ├── incremental_update.py    # Hourly: export → preprocess → gpr-news
│   ├── series_state.py          # anchor_date read/write
│   │
│   │  ── GKG path ──
│   ├── download_gkg.py          # GDELT zip download
│   ├── fill_gkg_bigquery.py     # BigQuery gap fill
│   └── preprocess_gkg.py        # Raw slots → gkg_processed/ parquet
│
├── deploy/                      # Layer 5 — Ops
│   ├── README.md
│   ├── news-scheduler.service
│   ├── news-api.service
│   ├── hourly_update.sh
│   ├── daily_gpr_india.sh
│   └── weekly_validate.sh
│
└── plan/                        # Design docs (not runtime)
```

### Runtime data layout (gitignored)

```
data/
├── india_db/news.db             # Live SQLite (7-day rolling)
├── india_raw/YYYY-MM-DD.jsonl.gz# Durable daily article log
├── india_processed/             # Tagged parquet → GPR input
├── india_archive/
│   ├── series_state.json        # anchor_date, last_processed
│   └── tag_cache.sqlite
├── gkg_raw/                     # GDELT 15-min slot zips
├── gkg_processed/               # Preprocessed GKG parquet
└── benchmarks/                  # Caldara reference XLS files

outputs/
├── news/                        # Scraper-based GPR (forward from anchor)
│   ├── gpr_daily_index.csv      # global + acts + threats + MA
│   ├── gpr_monthly_index.csv
│   ├── gpr_event_type.csv       # 8 event categories
│   ├── gpr_country_level.csv    # per-country daily
│   ├── gpr_article_scores.parquet
│   └── validation/
│
├── gkg/                         # GDELT-based GPR (historical)
│   ├── gpr_daily_index.csv
│   ├── gpr_monthly_index.csv
│   ├── gpr_event_type.csv
│   ├── gpr_country_level.csv
│   ├── gpr_daily_index_continuous.csv
│   └── validation/
│
└── compare/                     # Cross-path comparison
    ├── compare_news_vs_gkg.csv
    ├── spike_comparison.csv
    └── volume_news_vs_gkg.csv
```

---

## Setup

```bash
git clone https://github.com/VanshGupta18/Forsyt.git
cd Forsyt
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

---

## News path — Day 1 bootstrap

```bash
# 1. Scrape one cycle (all 10 outlets)
python -m scraper once

# 2. Export to JSONL
python main.py export-news

# 3. Preprocess (tag themes + tone + locations)
python main.py preprocess-india --start-date 2026-06-27 --end-date 2026-06-27 --force

# 4. Build GPR index
python main.py gpr-news --start-date 2026-06-27 --end-date 2026-06-27

# 5. Validate
python main.py validate-news --start-date 2026-06-27 --end-date 2026-06-27
```

## News path — Ongoing (cron)

```bash
# Terminal 1: continuous scraper (every 5 min, 10 outlets)
python -m scraper schedule

# Hourly cron:
python main.py incremental-update
```

---

## GKG path — Historical (2025)

```bash
python main.py download    --start-date 2025-01-01 --end-date 2025-12-31
python main.py preprocess  --start-date 2025-01-01 --end-date 2025-12-31
python main.py gpr-gkg     --start-date 2025-01-01 --end-date 2025-12-31
python main.py fill-gaps   --output-dir outputs/gkg --start-date 2025-01-01 --end-date 2025-12-31
python main.py validate-gkg --start-date 2025-01-01 --end-date 2025-12-31
```

---

## Compare news vs GKG

```bash
python main.py compare-gpr \
  --news-dir outputs/news \
  --gkg-dir  outputs/gkg
```

Outputs written to `outputs/compare/`:
- `compare_news_vs_gkg.csv` — Pearson/Spearman correlations
- `spike_comparison.csv` — top spike days per source
- `volume_news_vs_gkg.csv` — article volume by day

---

## GPR outputs (both paths)

| File | Contents |
|------|----------|
| `gpr_daily_index.csv` | Daily GPR (global), acts index, threats index, 7MA, 30MA |
| `gpr_monthly_index.csv` | Monthly means |
| `gpr_event_type.csv` | 8 event-category sub-indices |
| `gpr_country_level.csv` | Per-country daily GPR (news path: via location_tagger) |
| `gpr_article_scores.parquet` | Article-level scores and gpr_type (act / threat) |

---

## Validation

10 checks (same for both paths):
1. Statistical properties (mean, std, skew, autocorr, positive share 10–25%)
2. Component contributions (theme / tone / GCAM)
3. Event spike validation
4. Caldara monthly correlation (global GPR + GPRC_IND)
5. Daily Caldara correlation
6. MA30 correlation
7. Spike cross-check
8. Gap / coverage report
9. Source coverage
10. Theme tag distribution

News path primary benchmark: **GPRC_IND** (Caldara India country index).
