# gpr_index — Caldara GPR via GDELT GKG

Replicates the Iacoviello & Tong (2026) GPR index using **GDELT Global Knowledge Graph** data for 2025.

**Documentation:** [GPR theory](docs/gpr-theory.md) · [Code reference](docs/code-reference.md)

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
- `caldara_gpr_monthly.xls` (or `data_gpr_export (1).xls`)
- `caldara_gpr_daily.xls` (or `data_gpr_daily_recent.xls`)

## Run (2025 full year)

```bash
cd gpr_index
python main.py download   --start-date 2025-01-01 --end-date 2025-12-31
python main.py preprocess --start-date 2025-01-01 --end-date 2025-12-31
python main.py gpr        --start-date 2025-01-01 --end-date 2025-12-31
python main.py fill-gaps  --start-date 2025-01-01 --end-date 2025-12-31
python main.py validate   --start-date 2025-01-01 --end-date 2025-12-31
```

From repo root: `python gpr_index/main.py validate ...`

## Outputs

| File | Contents |
|------|----------|
| `outputs/gpr_daily_index.csv` | Daily global GPR, acts, threats, 7MA, 30MA |
| `outputs/gpr_monthly_index.csv` | Monthly means |
| `outputs/gpr_event_type.csv` | 8 event-category sub-indices |
| `outputs/gpr_country_level.csv` | Per-country daily GPR |
| `outputs/gpr_daily_index_continuous.csv` | Calendar-complete series after fill-gaps |

## Scripts

| Script | Role |
|--------|------|
| `scripts/download_gkg.py` | Download GDELT 15-min GKG slot files |
| `scripts/preprocess_gkg.py` | Merge slots → daily Parquet |
| `scripts/gkg_gpr_pipeline.py` | Score + aggregate GPR indices |
| `scripts/validate_gpr.py` | 10-check validation vs Caldara |
| `scripts/fill_gpr_gaps.py` | Caldara imputation for missing calendar days |
| `scripts/diagnose_gpr_scoring.py` | Sample scoring diagnostics |
| `scripts/plot_gpr.py` | Charts |
| `scripts/reprocess_gpr_index.py` | Rebuild index from saved daily CSV |
