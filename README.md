# Forsyt GPR — geopolitical risk models for NIFTY 50

Tests whether geopolitical risk (GPR) has any incremental value for Indian
market volatility, returns, and downside risk — beyond what plain market data
already tells you. Built against the public Caldara/Iacoviello AI-GPR index as
a stand-in, through a pluggable contract so Forsyt's own daily India GPR index
drops in later with no code changes.

**Headline finding:** on an honest out-of-sample backtest, GPR adds **no**
forecasting value for NIFTY volatility over a market-only baseline
(market-only ROC-AUC 0.83; adding GPR makes it worse). Full writeup in
[analysis/REPORT.md](analysis/REPORT.md).

## What it does

Two things live side by side:

1. **`forsyt_gpr/`** — a reusable modelling package. Point it at any GPR
   series and it fits three modules from `application.md`: a forward-
   volatility model, a macro impulse-response model, and a downside-risk
   model. Run it with `python run_application.py`.
2. **`analysis/`** — the one-off research notebook (as scripts) that produced
   the finding above: the India/NIFTY extension of Caldara-Iacoviello, and the
   walk-forward backtest that is the real evidence.

## Input data

| File | Source | Used for |
|---|---|---|
| `ai_gpr_data_daily.csv` | matteoiacoviello.com AI-GPR | daily GPR index (benchmark, threats, acts, oil sub-index) |
| `ai_gpr_data_monthly.csv` | same | monthly global GPR |
| `ai_gpr_country_monthly.csv` | same | monthly India-only GPR (`India_all`) |
| `analysis/data/NIFTY.csv` | Yahoo `^NSEI` | NIFTY 50 daily close |
| `analysis/data/SP500.csv` | Yahoo `^GSPC` | S&P 500 daily close (comparison market) |
| `analysis/data/NEWORDER.csv` | FRED | new orders, nondefense capex ex-aircraft (investment proxy) |
| `analysis/data/PAYEMS.csv` | FRED | US nonfarm payrolls (employment proxy) |

`download_data.py` refreshes the three `ai_gpr_*.csv` files from source.

## The GPR-frame contract

Every module consumes a `DatetimeIndex` frame with one required column,
`gpr`, plus optional `gpr_threats` / `gpr_acts` / `gpr_oil`. Today that's the
AI-GPR (`forsyt_gpr.data.load_aigpr_daily()`); wiring in Forsyt's own India
index later is a one-line `as_gpr_frame(...)` call — see
[forsyt_gpr/INTEGRATION.md](forsyt_gpr/INTEGRATION.md).

## Modules (`forsyt_gpr/`)

| Module | Question | Method |
|---|---|---|
| `vol_model.py` | Does GPR predict NIFTY volatility over the next 5 days? | XGBoost, purged walk-forward, `market_only` vs `market+gpr` |
| `macro_var.py` | Does a GPR shock foreshadow investment/employment declines? | Recursive monthly VAR, impulse responses |
| `downside.py` | Does GPR raise downside/tail risk in equity returns? | Quantile regression across the return distribution |

Every module fits a `market_only` baseline alongside `market+gpr` on
identical folds — GPR's contribution is always reported as the *difference*,
never a standalone score, because volatility clustering alone already scores
well.

## Analysis (`analysis/`)

- `02_india_nifty.py` — India-GPR history, monthly NIFTY vol/return
  regressions, VAR impulse response, in-sample fit.
- `03_backtest.py` — the real test: strict expanding-window walk-forward
  forecast of NIFTY volatility, RW/AR1/HAR benchmarks vs GPR-augmented models,
  Diebold-Mariano significance tests.
- `common.py` — shared data loaders for the two scripts above.

Run in order: `python analysis/02_india_nifty.py` then
`python analysis/03_backtest.py`.

## Output

- **Console tables**: RMSE/MAE/R² and ROC-AUC/PR-AUC per model, always with
  the GPR-only-vs-market-only delta called out.
- **Figures** (`analysis/figures/`): `B1` India-GPR history, `B2` India-GPR
  vs NIFTY, `B3` India VAR impulse response, `B4` in-sample fit, `C1`
  out-of-sample backtest, `D1` macro VAR, `D2` downside quantile curves.
- **Tables** (`analysis/output/`): `india_regressions.txt`
  (checked in); `india_vol_fit.csv`, `backtest_metrics.csv`,
  `backtest_predictions.csv` (regenerated on each run, gitignored).
- **Production forecast**: `forsyt_gpr.vol_model.latest_forecast(gf, price)`
  returns a JSON-ready record — point vol forecast, high-vol probability, and
  `gpr_added_vol` (market+gpr minus market-only) — for a daily job to call.

## Setup

```
pip install -r requirements.txt
python download_data.py       # refresh the AI-GPR csvs
python run_application.py     # forsyt_gpr package, all 3 modules
python analysis/02_india_nifty.py
python analysis/03_backtest.py
```

`vol_model.shap_importance` additionally needs `pip install shap` (kept
optional — it's an in-sample explanation tool, not part of the validated
result).
