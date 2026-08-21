# Integrating `forsyt_gpr` with the Forsyt daily pipeline

How the modelling package plugs into the news → GPR → API/dashboard flow in **2026**.

**Product framing:** Geo GPR and NIFTY vol are shown **side by side** — not a combined "GPR predicts NIFTY" headline model.

---

## 1. Where this sits in the pipeline

```
  geo_scheduler (scrape.yml)
        |
        v
  PostgreSQL articles + NLP
        |
        v
  india_processed_*.parquet  →  gkg_gpr_pipeline  →  CSV outputs
        |
        v
  sync_all()  →  gpr_daily / corridor_daily (Postgres)
        |
        v
  gpr_service.build_dual_signal_payload()
        |
        v
  GET /api/market/dual-signal  +  page bundles  →  React dashboard
```

The package needs a **daily GPR frame** (`gpr`, optional `gpr_7ma`, `gpr_threats`, `gpr_acts`). Everything else is internal to `forsyt_gpr`.

---

## 2. The hand-off contract

```python
import pandas as pd
from forsyt_gpr.data import as_gpr_frame, load_price
from forsyt_gpr.dual_signal import build_dual_signal

# From Postgres or gpr_daily_index.csv
raw = pd.read_sql(
    "SELECT date, gpr_index, gpr_7ma, gpr_threats_index, gpr_acts_index "
    "FROM gpr_daily ORDER BY date",
    con,
)
gf = as_gpr_frame(
    raw.set_index("date"),
    gpr="gpr_index",
    threats="gpr_threats_index",
    acts="gpr_acts_index",
)
nifty = load_price("NIFTY")  # replace with production NSE feed

payload = build_dual_signal(gf, nifty, index_days=len(gf))
```

`as_gpr_frame` validates datetime index, sort order, duplicates, and negative values.

**Production note:** `load_price("NIFTY")` uses cached Yahoo CSV for dev only. Pass your own daily close `pd.Series` in production.

---

## 3. What `build_dual_signal` returns

JSON-ready structure with three blocks:

### Geopolitical (`geo_regime`)

- Baseline: Caldara scale **100 / 35** (`caldara` or `caldara_ramp` when &lt; 60 index days)
- `z_score = (gpr_today - 100) / 35`
- Regimes: LOW / MODERATE / ELEVATED / HIGH
- `geo_percentile` over full history; confidence `low` if &lt; 8 index days

### NIFTY vol (`nifty_vol_signal`)

- Primary: `vol_model.latest_market_forecast()` — **market-only** XGB (no GPR in forecast features)
- Fallback: 22-day trailing realized vol if model unavailable
- Regime from `high_vol_prob`: NORMAL / ELEVATED / HIGH_VOL

### Joint stress (`joint_stress`)

- `stress_score = 0.6 × geo_percentile + 0.4 × vol_percentile`
- Regimes: CALM / WATCH / HIGH_STRESS
- Historical analog: past days with similar GPR → median forward 5d NIFTY vol/return

---

## 4. Wiring into the API (shipped)

Dual-signal is **already integrated** in `news_dataset/api/gpr_service.py`:

```python
# news_dataset/api/server.py
@app.get("/api/market/dual-signal")
def dual_signal():
    return jsonify(build_dual_signal_payload(refresh=request.args.get("refresh") == "1"))
```

Page bundles embed the same payload:

- `/api/pages/home` — hero dual-signal + joint stress
- `/api/pages/macro` — full chart context
- `/api/pages/portfolio` — stress context

**Refresh:** Cloud pipelines call `refresh_dual_signal()` after each GPR sync. Pass `?refresh=1` to bypass cache.

---

## 5. How to show it on the dashboard (shipped)

| UI element | Source field | Component |
|------------|--------------|-----------|
| Geo dial | `geo_regime.regime`, `gpr_today` | `DualSignalChart`, `HeroVerdictBlock` |
| Vol dial | `nifty_vol_signal.regime`, `vol_forecast` | `DualSignalChart` |
| Joint stress gauge | `joint_stress.stress_score`, `regime` | Home hero |
| Historical analog | `historical_analog` | `HistoricalAnalogPanel` |
| Honesty | Side-by-side layout | Macro dashboard copy |

**Design rule:** Never claim GPR forecasts NIFTY better than market data. OOS backtests show market-only wins — the product shows both signals transparently.

---

## 6. Scheduling

| Job | When | Action |
|-----|------|--------|
| `platform_refresh.yml` | hourly :20 UTC | GPR dirty-day rescore + `refresh_dual_signal()` |
| `daily_index.yml` | 18:30 UTC | Authoritative EOD close + dual-signal |
| `gdelt_warmup` | local only | Full rebuild + dual-signal cache |

---

## 7. Operational checklist

- [x] `gpr_daily` populated from India news pipeline (≥ Aug 9, 2026)
- [x] `/api/market/dual-signal` returns geo + vol + joint stress
- [x] Dual-signal cached in Postgres (`dual_signal_cache`)
- [x] Dashboard shows side-by-side dials (not GPR-only headline)
- [ ] Production NSE close feed wired (replace Yahoo dev CSV)
- [ ] Weekly `run_vol_experiment` persisted for examiner metrics (optional QA)

---

## 8. Research vs product

| Artifact | Location | Audience |
|----------|----------|----------|
| OOS vol backtest, ROC-AUC tables | `nifty-50/forsyt_gpr/vol_model.py`, `research/` | Internal QA |
| Shipped dual-signal | `dual_signal.py` + API | Product / dashboard |
| Academic write-up | `nifty-50/research/REPORT.md` | Capstone report |

See also: [`docs/PRODUCT.md`](../../docs/PRODUCT.md), [`nifty-50/README.md`](../README.md).
