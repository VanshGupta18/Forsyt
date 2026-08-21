# gpr_index — Caldara GPR via GDELT GKG

Replicates the Iacoviello & Tong (2026) GPR index using **GDELT Global Knowledge Graph** data for 2025.

**Documentation:** [GPR theory](docs/gpr-theory.md) · [Corridor risk](docs/corridor-theory.md)

## Pipeline

```
GDELT GKG zips  →  preprocess  →  gkg_gpr_pipeline  →  validate vs Caldara
data/gkg_raw/       gkg_processed/    outputs/              outputs/validation/
```

All paths are relative to this `gpr_index/` folder.

## Setup

```bash
source "$HOME/.venv/forsyt/bin/activate"
uv pip install -r gpr_index/requirements.txt
mkdir -p gpr_index/data/gkg_raw gpr_index/data/gkg_processed gpr_index/data/benchmarks
```

Place Caldara benchmark files in `gpr_index/data/`:
- `caldara_gpr_monthly.xls`
- `caldara_gpr_daily.xls`

(`scripts/paths.py` also accepts the filenames Iacoviello's site actually exports as — `data_gpr_export (1).xls` and `data_gpr_daily_recent.xls` — as fallbacks, and that's what's currently sitting in `gpr_index/data/` in this repo. Either naming works; `data/benchmarks/` is a third fallback location, not required.)

## Run (2025 full year)

```bash
cd gpr_index
python main.py download   --start-date 2025-01-01 --end-date 2025-12-31
python main.py preprocess --start-date 2025-01-01 --end-date 2025-12-31
python main.py gpr        --start-date 2025-01-01 --end-date 2025-12-31
python main.py fill-gaps  --start-date 2025-01-01 --end-date 2025-12-31
python main.py validate   --start-date 2025-01-01 --end-date 2025-12-31
python main.py corridor   --start-date 2025-01-01 --end-date 2025-12-31
python main.py validate-corridors
python main.py validate-corridors --summarize-daily
python main.py validate-corridors --parity-smoke --sample-size 50000
python main.py reprocess --start-date 2025-01-01 --end-date 2025-12-31
```

From repo root: `python gpr_index/main.py validate ...`

## GDELT warmup (2026, local only)

Mature GPR/corridor **7MA and baselines** by backfilling **2026-01-01 → 2026-08-08** with global GKG, then merging with `india_processed_*` from **2026-08-09** onward:

```bash
# from repo root
python -m news_dataset.pipeline.gdelt_warmup --slot-step 4
python gpr_index/main.py merge-processed
```

Merged symlinks: `data/index_processed/`. Set `GPR_INDEX_PROCESSED_DIR` to that path for scoring; hourly CI keeps `india_processed/` only (do **not** set `GPR_INDEX_PROCESSED_DIR` in GitHub Actions unless intentionally running warmup).

### Score semantics after warmup

- **Jan 1 – Aug 8 (GKG warmup):** internal calibration only — builds corridor hit-days and GKG-scale baselines. Not synced to Postgres or shown in the UI.
- **Aug 9+ (India news):** product scores use an **India-only baseline**; 100 = average India-news stress day. Split-era normalization prevents GKG article volume from compressing India-era levels.
- **7MA / corridor_risk_7ma:** rolling averages computed only on product-era rows (not across the Aug 8→9 boundary).
- **Cloud hourly jobs** score `india_processed/` only — split-era applies locally when the merged dir is used.

## Outputs

| File | Contents |
|------|----------|
| `outputs/gpr_daily_index.csv` | Daily global GPR, acts, threats, 7MA, 30MA |
| `outputs/gpr_monthly_index.csv` | Monthly means |
| `outputs/gpr_event_type.csv` | 8 event-category sub-indices |
| `outputs/gpr_country_level.csv` | Per-country daily GPR |
| `outputs/gpr_daily_index_continuous.csv` | Calendar-complete series after fill-gaps |
| `outputs/gpr_corridor_daily.csv` | Daily threat, exposure channels, and CorridorRisk |
| `outputs/corridor_article_hits.parquet` | Slim positive article/corridor hits |

## Scripts

| Script | Role |
|--------|------|
| `scripts/download_gkg.py` | Download GDELT 15-min GKG slot files |
| `scripts/preprocess_gkg.py` | Merge slots → daily Parquet |
| `scripts/gkg_gpr_pipeline.py` | Score + aggregate GPR indices |
| `scripts/validate_gpr.py` | 10-check validation vs Caldara |
| `scripts/corridor_index.py` | Aggregate and normalize corridor indices |
| `scripts/validate_corridors.py` | Corridor specificity, coverage, sampling, and parity checks |
| `scripts/fill_gpr_gaps.py` | Caldara imputation for missing calendar days |
| `scripts/diagnose_gpr_scoring.py` | Sample scoring diagnostics |
| `scripts/plot_gpr.py` | Charts |
| `scripts/merge_processed_dirs.py` | Symlink GKG warmup + India parquets into `index_processed/` |

## Known quirks (harmless, not cleaned up yet)

A few leftover files in this module are stale but not deleted — see the
repo-root `docs/DISCREPANCIES.md` for the full list. In short:

- `outputs/india_smoke/` — a small one-off smoke-test snapshot from an early
  run, unreferenced by any script or doc. Safe to ignore.
- `data/gkg_processed/data_gpr_daily_recent.xls` — a stray duplicate of the
  Caldara benchmark spreadsheet that ended up inside the Parquet output
  folder; the real copy used by the pipeline lives directly under `data/`.
- Files named `._*` anywhere under this module (e.g. `docs/._README.md`) are
  macOS "AppleDouble" metadata created when copying files onto/off an
  external drive — not real content, safe to ignore or delete.
