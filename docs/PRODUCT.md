# Forsyt — Product Overview

**Daily India geopolitical risk intelligence with dual-signal market context.**

Forsyt answers operational questions for analysts, investors, and supply-chain teams:

1. **How risky is India's geopolitical environment today?** → Daily GPR index from 9 Indian news sources
2. **Which trade routes are under stress?** → 12 corridor risk scores (Hormuz, LAC, Malacca, Red Sea…)
3. **What news is driving the score?** → Tagged event feed with themes and locations
4. **How does market volatility look alongside geo risk?** → Dual-signal panel (honest, side-by-side)

## What Forsyt is NOT

- Not a NIFTY prediction engine — GPR does not beat market-only vol forecasts out of sample
- Not investment advice — intelligence and context only
- Not a portfolio optimizer — exposure view is informational, not allocation advice

## Dual-signal design

| Signal | Source | What it tells you |
|--------|--------|-------------------|
| **Geopolitical** | Forsyt daily GPR from Indian news | News attention to wars, sanctions, border crises |
| **NIFTY Volatility** | Market data only (`market_only` XGB) | Trailing vol + 5-day forward vol estimate |
| **Joint Stress** | 60% geo percentile + 40% vol percentile | Combined glance metric |

Both dials are shown **side by side**. When they diverge (geo hot, market calm), that gap is itself useful intelligence.

Geo regime uses Caldara-scale baseline (**100 / 35 σ**) with low-confidence flag when index history &lt; 60 days.

## Score semantics (2026)

| Era | Dates | Shown in UI? |
|-----|-------|--------------|
| GDELT warmup | Jan 1 – Aug 8, 2026 | No (local calibration only) |
| India product | Aug 9, 2026 → today | Yes — **100 = average India-news day** |

Split-era normalization prevents mixing GKG volume (~15k–30k articles/day) with India news (~200–400/day). See [`gpr_index/docs/gpr-theory.md`](../gpr_index/docs/gpr-theory.md#9-split-era-normalization-2026-product).

## Product success metrics

| Metric | Target |
|--------|--------|
| Pipeline uptime | Daily job succeeds 30 consecutive days |
| Index freshness | GPR updated within 24h of news scrape |
| Caldara correlation | Monthly r ≥ 0.50 vs academic benchmark |
| Event detection | Known crises (Galwan, Pulwama) show GPR spike within 3 days |
| Corridor sanity | Highest-risk corridor matches news coverage |

## API endpoints

GPR and corridor data are delivered via **page bundles** (one JSON per screen), not standalone `/api/gpr/*` routes.

| Endpoint | Description |
|----------|-------------|
| `GET /api/pages/home` | Health, GPR, corridors, quotes, dual-signal, status |
| `GET /api/pages/macro` | Dual-signal, GPR history, market histories, corridors |
| `GET /api/pages/news` | Tagged events + GPR context |
| `GET /api/pages/corridor` | Corridor scores (sorted by 7MA), events, metadata |
| `GET /api/pages/portfolio` | GPR + dual-signal + market quotes |
| `GET /api/pages/quality` | Methodology / accuracy report |
| `GET /api/events/feed` | Filtered NLP-tagged articles |
| `GET /api/market/dual-signal` | Geo + NIFTY vol + joint stress + analog |
| `GET /health`, `GET /api/status` | Ops health and freshness |

## Dashboard screens

| Route | Screen |
|-------|--------|
| `/` | Home — verdict, live pulse, dual-signal hero |
| `/macroeconomics` | Macro — GPR vs NIFTY chart, dual-signal panels |
| `/trade-corridor` | 12 corridors map + risk board |
| `/news` | Searchable tagged event feed |
| `/portfolio-exposure` | Portfolio context + stress signals |
| `/quality` | Accuracy / methodology dashboard |

Frontend architecture: [`frontend/docs/ARCHITECTURE.md`](../frontend/docs/ARCHITECTURE.md)

## Research appendix

Academic validation (VAR, OOS backtest, quantile regression) lives in `nifty-50/research/`. Internal QA only — not the product surface.
