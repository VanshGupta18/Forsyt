# `forsyt_gpr` — geopolitical risk → market models

Implements `application.md` against **any** geopolitical-risk index.

```
data.py       the pluggable GPR-frame contract + loaders
features.py   MD §1  GPRT / GPRA / benchmark features, and the market baseline
vol_model.py  MD §2  XGBoost forward-volatility model, purged walk-forward
```

> **Note (2026-08):** this package used to also ship `macro_var.py` (MD §A,
> VAR → corporate investment & employment impulse responses), `downside.py`
> (MD §A, quantile regression → downside / "disaster" risk), and a
> `run_application.py` entry point that ran everything end to end, all under
> `nifty-50/research/`. That directory was removed in commit `eff8091`
> ("nlp scheduler", 2026-08-13) and is no longer part of this repo. The
> figures/table those scripts produced (`nifty-50/output/figures/B2_*`,
> `B3_*`, `D1_*`, `D2_*`, and `output/tables/india_regressions.txt`) are
> still on disk as historical snapshots, but nothing in the current codebase
> can regenerate them. See the root `docs/DISCREPANCIES.md` for the full
> cross-module list of stale/orphaned artifacts.

Run the research backtest that's actually still here:

```bash
python -c "
from forsyt_gpr import data, vol_model
gf = data.load_aigpr_daily()
reg, clf, _ = vol_model.run_vol_experiment(gf, data.load_price('NIFTY'))
print(reg); print(clf)
"
```

---

## Plugging in the Forsyt index

Every module consumes a **canonical GPR frame**: a `DatetimeIndex` plus

| column | required | meaning |
|---|---|---|
| `gpr` | ✅ | benchmark geopolitical risk index |
| `gpr_threats` | optional | GPRT — *anticipated* conflict |
| `gpr_acts` | optional | GPRA — *realized* conflict |
| `gpr_oil` | optional | oil-supply-disruption sub-index |

Nothing downstream knows or cares where the numbers came from. Today it's the
Caldara/Iacoviello AI-GPR; when the scraper's India index is ready:

```python
from forsyt_gpr.data import as_gpr_frame, load_price
from forsyt_gpr import vol_model

# NOTE: this is an illustrative/simplified example, not the literal query.
# The real production hand-off lives in news_dataset/api/gpr_service.py
# (gpr_frame_from_db_or_csv()), which queries a `gpr_daily` table with
# columns `date`, `gpr_index`, `gpr_threats_index`, `gpr_acts_index` (or
# falls back to gpr_index/outputs/gpr_daily_index.csv with the same column
# names) -- the exact table/column names shown here are just placeholders
# to demonstrate the shape of the hand-off.
raw = pd.read_sql("select date, gpr_index, gpr_threats_index, gpr_acts_index "
                  "from gpr_daily", con)
gf  = as_gpr_frame(raw.set_index("date"), gpr="gpr_index",
                   threats="gpr_threats_index", acts="gpr_acts_index")

reg, clf, _ = vol_model.run_vol_experiment(gf, load_price("NIFTY"), horizon=5)
```

Every model, backtest and figure then runs unchanged. `as_gpr_frame` validates
and raises on the failure modes that otherwise show up as "weak results":
non-`DatetimeIndex`, unsorted index, duplicate dates, negative values, all-NaN.

**Zeros are allowed and expected.** A narrow India-only news corpus will produce
many zero-risk days. Everything uses `log1p`, never `log`, so a zero day is a
floor rather than `-inf`. (This is not hypothetical: the AI-GPR oil sub-index is
zero on 8,124 of 24,258 days, and an early `log` here silently collapsed the
sample from 4,315 rows to 8.)

---

## The one rule this package exists to enforce

**Report incremental value, never a headline score.**

`run_vol_experiment` always fits three blocks on identical folds:

| block | features | role |
|---|---|---|
| `market_only` | trailing vol + momentum | **the baseline GPR must beat** |
| `gpr_only` | GPRT/GPRA/MAs/spikes | is there *any* signal? |
| `market+gpr` | both | the actual proposal |

GPR's contribution is `market+gpr` **minus** `market_only`. Nothing else.

This matters because volatility clusters. On NIFTY, `market_only` — with **zero
geopolitical input** — scores **ROC-AUC 0.831**. Any project reporting "ROC-AUC
0.72, target ≥0.65, GPR works!" would be reporting vol clustering and calling it
geopolitics. SHAP will still hand importance to GPR features, because they ride
along with the vol regime; SHAP explains what a model *used*, never whether the
model is any *good*. Judge that from the walk-forward tables only.

## Leakage controls

- **Purged walk-forward.** The 5-day target at *t* spans *t+1..t+5*, so
  consecutive targets overlap. Training right up to the test date leaks future
  returns backwards. Training stops `horizon` days before each test block.
- **Expanding window**, refit every `refit_every` days; parameters only ever see
  the past.
- **Thresholds fit in-fold.** The HIGH_VOL cutoff comes from training data only.
- **Base rate always reported.** With a top-quartile label the OOS base rate is
  ~12%, so "88% accuracy" is the trivial never-predict-a-spike rule. Read PR-AUC.

## Known limits

- Country-level AI-GPR (incl. India) is **monthly only**; only the global index
  is daily. Monthly indices are forward-filled to a step function — usable, but
  it is why a daily India index (Forsyt's actual contribution) is the real unlock.
- Nifty history from Yahoo starts **2007-09**, excluding Kargil (1999) and the
  2001–02 standoff — the most informative Indian geopolitical episodes. Sourcing
  real NSE history back to 1996 would materially strengthen every test here.
- `run_application.py` uses Yahoo data — fine for development, not citable.
