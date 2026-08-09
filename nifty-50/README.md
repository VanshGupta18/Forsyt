# Forsyt GPR — product + research

## Product (shippable)

**Dual-signal market context** for the Forsyt dashboard and API:

| Module | Role |
|---|---|
| `forsyt_gpr/dual_signal.py` | Geo GPR regime + NIFTY vol (`market_only`) + joint stress + historical analog |
| `forsyt_gpr/vol_model.py` | XGBoost forward-vol model — product uses `market_only` block only |
| `forsyt_gpr/data.py` | Pluggable GPR-frame contract (Forsyt India index plugs in here) |

Wire via `GET /api/market/dual-signal` (see repo root [`docs/PRODUCT.md`](../docs/PRODUCT.md)).

## Research (internal QA)

Academic validation — **not the product surface**:

```
research/
  analysis/       02_india_nifty.py, 03_backtest.py (OOS evidence)
  run_application.py   VAR + vol + downside on benchmark AI-GPR
  macro_var.py, downside.py
  REPORT.md       full write-up
```

**Headline finding:** GPR adds no OOS forecasting value for NIFTY vol over market-only
(ROC-AUC 0.831 vs 0.815 with GPR). See [`research/REPORT.md`](research/REPORT.md).

## Setup

```bash
cd nifty-50
pip install -r requirements.txt
python download_data.py

# Product module (from repo root, with DATABASE_URL set):
python -m news_dataset.pipeline.daily_index

# Research scripts (from nifty-50/):
python research/run_application.py
python research/analysis/02_india_nifty.py
python research/analysis/03_backtest.py
```

## Input data (`data/`)

| File | Source | Used for |
|---|---|---|
| `ai_gpr_data_daily.csv` | matteoiacoviello.com AI-GPR | benchmark GPR (fallback until Forsyt index in DB) |
| `NIFTY.csv` | Yahoo `^NSEI` | dual-signal market half |
| Other CSVs | FRED / Yahoo | research modules only |

See [`docs/INTEGRATION.md`](docs/INTEGRATION.md) for wiring Forsyt's daily India GPR into the GPR frame.
