# GDELT warmup runbook

Local-only backfill to strengthen India GPR **7MA and corridor baselines** without writing GDELT articles to Postgres.

## What it does

| Layer | Source | In Postgres? |
|-------|--------|--------------|
| 2026-01-01 → 2026-08-08 | Global GDELT GKG → `gkg_processed_*.parquet` | No |
| 2026-08-09 → today | India news → `india_processed_*.parquet` | Index rows only (≥ Aug 9) |

**Split-era rule:** Warmup and product eras use **separate normalization baselines**. Mixing them in one baseline compressed India-era scores to ~1–2 instead of ~100. Product scores mean: **100 = average India-news stress day**.

## Full run (laptop, overnight)

```bash
source "$HOME/.venv/forsyt/bin/activate"
cd "/Volumes/My Passport/Forsyt"

python -m news_dataset.pipeline.gdelt_warmup \
  --warmup-start 2026-01-01 \
  --slot-step 4 \
  --delay-seconds 0.3
```

## Resume

```bash
python -m news_dataset.pipeline.gdelt_warmup \
  --skip-download \
  --skip-preprocess
```

## Verify

```bash
# CSV has Jan rows; API does not
wc -l gpr_index/outputs/gpr_daily_index.csv
curl -s http://127.0.0.1:5001/api/status | python3 -m json.tool
```

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `GPR_WARMUP_START` | `2026-01-01` | GDELT + normalization baseline |
| `INDIA_GPR_INDEX_START` | `2026-08-09` | Product era; Postgres sync cutoff |
| `GPR_INDEX_PROCESSED_DIR` | unset (india only) | Set to `gpr_index/data/index_processed` for warmup scoring |

Note: `docs/` is gitignored — copy this file into README if you need it in the repo.
