# Integrating `forsyt_gpr` with the Forsyt daily pipeline

How the modelling package plugs into the Newsemble scraper → GPR-index → API/dashboard
flow, what a daily run produces, and how the numbers are meant to be displayed.

---

## 1. Where this sits in the pipeline

```
  scraper.py (every 15 min)          <- YOU already built this (Newsemble)
        |
        v
  news.db  (articles)
        |
        v
  [ NLP scoring + index construction ]   <- Forsyt Phase 2-3 (to build)
        |
        v
  gpr_index table:  day | india_gpr | threats | acts     <- the hand-off point
        |
        v
  forsyt_gpr.data.as_gpr_frame(...)      <- THIS PACKAGE starts here
        |
        v
  vol_model.latest_forecast(...)  ->  JSON  ->  api/  ->  dashboard/
```

The package needs exactly one thing from Forsyt: a table of **daily GPR values**.
Everything else (features, model, forecast) is internal.

---

## 2. The hand-off contract

The only coupling is `as_gpr_frame`. Point it at your columns:

```python
import pandas as pd
from forsyt_gpr.data import as_gpr_frame, load_price
from forsyt_gpr import vol_model

# 1. pull your index out of Postgres/SQLite
raw = pd.read_sql("select day, india_gpr, threats, acts from gpr_index "
                  "order by day", con)

# 2. coerce to the canonical GPR frame (validates + raises on bad data)
gf = as_gpr_frame(raw.set_index("day"),
                  gpr="india_gpr", threats="threats", acts="acts")

# 3. daily NIFTY forecast
nifty = load_price("NIFTY")           # swap for your own NSE price feed
record = vol_model.latest_forecast(gf, nifty, horizon=5)
```

`threats`/`acts` are optional — omit them and only benchmark features are built.
`as_gpr_frame` raises early on a non-datetime index, unsorted dates, duplicate
days, negative values, or an all-NaN column, so a broken upstream job fails loudly
instead of producing a plausible-looking wrong number. Zeros are allowed (a narrow
India-only corpus will have quiet days; everything uses `log1p`).

### Price feed
`load_price("NIFTY")` reads a cached Yahoo CSV — fine for development, **not for
production** (unofficial, ~1-day lag, starts 2007). In production pass your own
daily close series (NSE Bhavcopy, broker API) as a `pd.Series` indexed by date.
Any `pd.Series` of daily closes works; nothing else changes.

---

## 3. What one daily run returns

`latest_forecast` fits on all history whose 5-day-ahead outcome is already known,
then scores the newest day. It returns a JSON-ready dict:

```json
{
  "as_of": "2026-04-30",
  "horizon_days": 5,
  "target": "annualized realized vol, next 5 trading days (%)",
  "high_vol_threshold": 17.91,
  "target_resolves_on": "2026-05-08",
  "market_only":  { "vol_forecast": 13.56, "high_vol_prob": 0.143 },
  "gpr_only":     { "vol_forecast": 15.08, "high_vol_prob": 0.222 },
  "market+gpr":   { "vol_forecast": 14.43, "high_vol_prob": 0.204 },
  "headline":     { "vol_forecast": 14.43, "high_vol_prob": 0.204 },
  "gpr_added_vol": 0.87
}
```

Every run reports **three models side by side on purpose**. `market_only` has zero
geopolitical input; `gpr_added_vol` is the honest contribution of your index. Never
show `headline` alone — the delta is the whole point of the platform.

`high_vol_prob` is the probability that realized vol over the next 5 trading days
lands in the top 25% (the "HIGH_VOL regime" Forsyt promises). `high_vol_threshold`
is the annualized-vol level (%) that defines that regime, learned from training
data only.

---

## 4. Wiring it into `app.py`

Add one endpoint. Cache the day's result; do not refit per request (a fit is
seconds, but there is no reason to repeat it intraday).

```python
# api/forecast.py
from functools import lru_cache
import datetime as dt, pandas as pd
from forsyt_gpr.data import as_gpr_frame, load_price
from forsyt_gpr import vol_model

@lru_cache(maxsize=1)
def _todays_forecast(day: str):            # day in the key => auto-invalidates daily
    raw = pd.read_sql("select day, india_gpr, threats, acts from gpr_index", ENGINE)
    gf = as_gpr_frame(raw.set_index("day"), gpr="india_gpr",
                      threats="threats", acts="acts")
    return vol_model.latest_forecast(gf, load_price("NIFTY"), horizon=5)

@app.route("/api/nifty_vol_forecast")
def nifty_vol_forecast():
    return jsonify(_todays_forecast(dt.date.today().isoformat()))
```

### Scheduling
Reuse `scheduler.py`. Run the forecast **once per day, after the index updates and
after NSE close** — realized-vol features need the day's close. A daily cron
(`.github/workflows/scrape.yml` already runs on a schedule) is the right cadence;
intraday refits add nothing because the features only move on new daily bars.

### Weekly validation job (recommended)
Once a week, run the real evaluator and store the tables — this is what proves the
model is (or is not) working, and it is the number an examiner will ask for:

```python
reg, clf, _ = vol_model.run_vol_experiment(gf, load_price("NIFTY"), horizon=5)
# persist reg / clf to a metrics table; expose on an /api/model_health route
```

---

## 5. How to show it on the dashboard

The forecast maps to Forsyt's "volatility intelligence" module like this:

| UI element | Field | Note |
|---|---|---|
| Big regime badge | `headline.high_vol_prob` | `>0.5` → "HIGH VOL WATCH", else "NORMAL" |
| Vol gauge | `headline.vol_forecast` vs `high_vol_threshold` | needle vs the red line |
| "GPR contribution" chip | `gpr_added_vol` | **the differentiator** — +/- pts from geopolitics |
| Sub-caption | `as_of` → `target_resolves_on` | "forecast for Apr 30 – May 8" |
| Honesty panel | all three `*_forecast` | market-only vs +gpr, side by side |
| Model-health page | weekly `run_vol_experiment` tables | ROC-AUC, incremental ΔR² |

**Design rule that protects the project's credibility:** the "GPR contribution"
chip must be able to show a *negative* number. On current data (AI-GPR) it often
does — that is a true statement about the index, and hiding it would make the
dashboard dishonest. When Forsyt's own daily India index makes that chip reliably
positive and significant in the weekly validation, *that* is your headline result.

Sketch:

```
┌───────────────────────────────────────────────┐
│  NIFTY 50 · 5-day volatility        as_of 30 Apr │
│                                                 │
│     ┌─────────┐     Forecast   14.4%  ann.       │
│     │ NORMAL  │     Threshold  17.9%             │
│     └─────────┘     P(high vol) 20%              │
│                                                 │
│  Geopolitical contribution:  +0.9 pts           │
│  ──────────────────────────────────────────     │
│  market-only 13.6% | +GPR 14.4% | GPR-only 15.1%│
└───────────────────────────────────────────────┘
```

---

## 6. Operational checklist

- [ ] `gpr_index` table populated daily by the scoring job
- [ ] daily close feed wired into `load_price` replacement
- [ ] `/api/nifty_vol_forecast` returns the JSON above
- [ ] result cached per calendar day, refreshed after NSE close
- [ ] weekly `run_vol_experiment` persisted to a metrics table
- [ ] dashboard shows all three models, `gpr_added_vol` allowed to be negative
- [ ] staleness guard: if `gf.index.max()` is > 2 days old, flag on the dashboard
      rather than silently serving a stale forecast
