# Reproducing Caldara–Iacoviello with the AI-GPR, and an India / NIFTY 50 extension

**Data:** `ai_gpr_*.csv` from matteoiacoviello.com (AI-GPR, an LLM/GPT-4o-mini
re-implementation of the Caldara & Iacoviello 2022 *AER* geopolitical-risk
index), plus daily market data (`^GSPC`, `^VIX`, `^NSEI`) and FRED `INDPRO`.
All code in `analysis/`; run `01_us_reproduction.py` then `02_india_nifty.py`.

---

## Part A — Reproducing the core Caldara–Iacoviello result (US / global)

**Claim being reproduced (CI 2022):** a geopolitical-risk shock *lowers stock
returns, raises stock-market volatility, and depresses real activity.*

**Method.** Recursive (Cholesky) monthly VAR, 1985m1–2026m5 (n=497), variables
`[log AI-GPR, IP growth, S&P 500 return, S&P realized volatility]`, GPR ordered
first (treated as the exogenous/fast-moving shock), 3 lags (AIC). Impulse
responses to a **1-s.d. AI-GPR shock**, 90% Monte-Carlo bands.
→ `figures/A2_us_irf.png`, table `output/us_irf_to_gpr_shock.csv`.

**Result — matches the paper qualitatively:**

| Variable | On-impact response | Peak / trough |
|---|---|---|
| S&P 500 return | **−0.54%** | reverses within ~2 months (transitory) |
| Stock volatility | **+0.18 → +0.43** ann.% | peak at month 2 |
| Industrial production | ~0 | **trough −0.08%** at month 3 |

So the AI-GPR reproduces CI's signature pattern: **stocks fall and volatility
jumps on impact, real activity dips over the following quarter,** and the equity
*return* effect is short-lived while volatility and the activity drag are more
persistent. `figures/A1_aigpr_index.png` shows the index itself spiking at the
Gulf War, 9/11, Iraq, Crimea, the 2022 Ukraine invasion, and Gaza.

---

## Part B — Extension to India and NIFTY 50 volatility

**Question.** Does India-specific geopolitical risk (`India_all`, the AI-GPR
country index) move and *forecast* NIFTY 50 volatility?

**Method.** Monthly NIFTY realized volatility & returns from daily `^NSEI`
(2007m10–2026m5, n=224). HAC (Newey–West, 6 lags) regressions plus a bivariate
recursive VAR `[log India-GPR, NIFTY return, NIFTY vol]`.

**India-GPR history (`figures/B1_india_gpr.png`)** validates the index — the
largest India spikes are 26/11 (2008), Kargil (1999), Pulwama/Balakot (2019) and
the 2025 Pakistan flare-up.

**Regression results:**

| Spec | Coefficient | t (HAC) | R² |
|---|---|---|---|
| (1) NIFTY vol ~ India-GPR (contemp.) | +3.20 | +1.43 | 0.03 |
| (2) NIFTY vol_t ~ India-GPR_{t-1} + vol_{t-1} | +0.83 | +0.69 | 0.44 |
| (3) NIFTY ret_t ~ India-GPR_{t-1} | +0.18 | +0.25 | 0.00 |
| (4) horse race: + global AI-GPR_{t-1} | India +1.60 (t=1.25) / **global −5.40 (t=−2.59)** | | 0.45 |

**VAR impulse response (`figures/B3_india_irf.png`)** — an India-GPR shock gives
the *correct Caldara signs*: NIFTY return dips (≈ −0.5% around month 2) and NIFTY
volatility rises (**peak +0.75 ann.% at month 1**), but the 90% bands are wide.

### Honest interpretation

1. **The direction of the effect carries over to India** — a local geopolitical-
   risk shock raises NIFTY volatility and lowers returns, just as in CI. This is
   the clean, orthogonalized-shock statement (VAR IRF).

2. **But it is statistically weak, and raw correlations are even misleading.**
   The India-GPR coefficient on volatility has the right (+) sign but is not
   significant; global AI-GPR's *raw* correlation with NIFTY vol is **negative**.
   `figures/B2_india_vs_nifty.png` explains why: the two dominant NIFTY-vol
   episodes in this sample — the **2008 GFC** and **COVID-2020** (~80% ann. vol)
   — were *financial/health* crises with *low* geopolitical risk, while the
   genuine GPR spikes (Pulwama, 2025 flare-up) produced comparatively modest
   volatility. Over the short NIFTY era, non-geopolitical shocks dominate the
   variance, so geopolitical risk is a real but second-order driver.

3. **Caveat on the index.** The AI-GPR (incl. `India_all`) is built from *US*
   newspapers (NYT, WaPo, Chicago Tribune), so it measures US-media salience of
   India risk — a noisy proxy for what actually trades in Mumbai.

### Forecast (in-sample only — NOT evidence of forecasting skill)
`figures/B4_forecast_fit.png` is an **in-sample fit**: the model is estimated on
the full sample, so it has seen every point it "predicts". The 15.7% 1-month
figure it implies from 2026-05 is a projection, not a validated forecast. For
real evidence see Part C.

---

## Part C — Out-of-sample backtest (`03_backtest.py`)

**Design.** Strict walk-forward / expanding window. For each month *t*: estimate
every model on data through *t−1* only, predict vol in *t*. All predictors dated
*t−1* or earlier; the high-vol threshold is also computed from training data only
(no look-ahead). **152 monthly forecasts, 2013m10–2026m5**, min 60m training.
Benchmarks: RW (`vol_t = vol_{t-1}`), AR1, and HAR (vol lags 1 / 3m / 12m).

| Model | RMSE | MAE | R² vs RW | R² vs HAR | DirAcc% | SpikePrec% | SpikeRecall% |
|---|---|---|---|---|---|---|---|
| RW | 7.79 | 4.49 | 0.00 | −0.24 | n/a | 44.4 | 42.1 |
| AR1 | 7.06 | 4.26 | +0.18 | −0.02 | 61.2 | 46.7 | 36.8 |
| **HAR** | **7.00** | **4.01** | **+0.19** | 0.00 | **63.8** | 50.0 | 31.6 |
| AR1+India-GPR | 7.13 | 4.37 | +0.16 | −0.04 | 63.2 | 38.1 | 42.1 |
| HAR+India-GPR | 7.03 | 4.09 | +0.19 | **−0.01** | 61.8 | 43.8 | 36.8 |
| HAR+India+global GPR | 7.19 | 4.31 | +0.15 | **−0.06** | 61.8 | 47.1 | 42.1 |

Diebold–Mariano (squared errors): HAR vs HAR+India-GPR **p=0.78**; AR1 vs
AR1+GPR **p=0.55**; HAR vs HAR+both-GPR **p=0.31**; RW vs HAR **p=0.18**.

### Verdict — India-GPR has NO out-of-sample forecasting value for NIFTY vol

- **Volatility persistence does all the work.** HAR cuts RMSE to 7.00 from the
  random walk's 7.79 (R² +19% vs RW) — though even that edge is not significant
  (DM p=0.18).
- **Adding India-GPR makes forecasts slightly *worse*, never better** (R² vs HAR
  = −0.01; adding global GPR too: −0.06). Every DM test is insignificant: the
  GPR-augmented models are statistically indistinguishable from — and point-
  estimate worse than — plain persistence.
- **The "87% spike accuracy" is a mirage.** Only **12.5%** of OOS months are
  high-vol, so "never predict a spike" scores 87.5% — *no model beats that
  baseline*. Precision ~44–50% / recall ~32–42% is the real story: coin-flip.
- **Directional accuracy ~62–64%** is the one modest positive, but HAR alone is
  the best (63.8%); GPR does not improve it.
- `figures/C1_backtest.png` shows why: the forecasts essentially track realized
  vol with a one-month lag. COVID-2020 (81% vol) is **missed entirely on the way
  up** and then over-predicted on the way down — the largest error in the sample
  is a non-geopolitical event.

**Bottom line.** The Caldara–Iacoviello *structural* result reproduces (Part A),
and the *sign* survives for India in a VAR (Part B) — a geopolitical shock does
raise NIFTY volatility. But "GPR forecasts NIFTY volatility" is **not supported
out of sample**. The honest use of India-GPR here is as a contemporaneous
risk-attribution/event-study tool, not as a predictive signal.

---

---

## Part D — `application.md` implemented (`forsyt_gpr/`, `run_application.py`)

Three modules, each consuming a generic GPR frame so Forsyt's own index plugs in
unchanged. See `forsyt_gpr/README.md` for the contract.

### Module 2 (MD §2) — XGBoost forward realized volatility, purged walk-forward

Target: realized vol over the next 5 trading days. Three feature blocks fit on
identical folds; **GPR's contribution is `market+gpr` minus `market_only`.**

| | NIFTY R²vs.persist | NIFTY ROC-AUC | S&P R² | S&P ROC-AUC |
|---|---|---|---|---|
| persistence | 0.000 | — | 0.000 | — |
| XGB market_only | **+0.387** | **0.831** | **+0.166** | **0.831** |
| XGB gpr_only | −0.582 | 0.636 | −0.623 | 0.596 |
| XGB market+gpr | +0.280 | 0.815 | +0.038 | 0.828 |
| **incremental GPR** | **−0.107** | **−0.016** | **−0.129** | **−0.002** |

**GPR features have negative incremental value in both markets over 40 years.**
`gpr_only` (AUC 0.64 / 0.60) shows weak standalone signal, fully redundant once
market features are present. SHAP on NIFTY: top features are all market (`rv22`,
`ret22`, `drawdown`, `ret5`); GPR is 16.9% of top-12 importance.

> **The number that matters for Forsyt:** `market_only` scores **ROC-AUC 0.831
> with zero geopolitical input**. Forsyt's stated targets are F1 ≥ 0.60 /
> ROC-AUC ≥ 0.65 — clearable by pure volatility clustering. A headline AUC
> cannot test the geopolitical thesis; only the incremental delta can.

### Module A1 (MD §A) — VAR: investment & employment

1 s.d. GPR shock → **investment trough −0.169% (month 2)**, **employment trough
−0.085% (month 3)**, stock returns −0.396% on impact. Sign and timing match
Caldara & Iacoviello (2022).

*Caveat:* the IRFs **oscillate** (investment: +0.13, −0.17, +0.10, −0.06 …) —
ringing from a VAR(3) on noisy monthly growth rates, not the clean hump-shape
the paper reports. Bands are wide and the 24-month cumulative reverts positive.
Treat the trough as indicative, not as a precise magnitude. `figures/D1_macro_var.png`

### Module A2 (MD §A) — downside / "disaster" risk: **claim not supported**

Claim: higher GPR ⇒ larger downside risk, i.e. β(0.05) strongly negative.

| spec | NIFTY left-tail β | S&P left-tail β |
|---|---|---|
| **shock** (correct) | **+2.25** (vs median +0.63) | **+1.26** (vs median +0.22) |
| level (confounded) | +4.46 | +0.78 |

**Wrong sign in every specification and both markets** — the left tail *compresses*
after GPR shocks. `figures/D2_downside.png` shows the left side sitting above the
right, the inverse of a tail-risk signature.

Two methodological notes:
- **Level vs shock matters.** Regressing on the GPR *level* is confounded: the
  GFC and COVID were low-GPR, worst-return events, anchoring the left tail at low
  GPR and forcing β(0.05) positive. That inflated NIFTY's from +2.25 to +4.46.
  Caldara's equity effect comes from *innovations*; a stable high level is priced.
- **This does not refute Caldara.** Their disaster claim concerns *macro* downside
  (GDP), not 21-day equity returns. This tests the equity adaptation only.

### Reconciling Parts A/D

GPR has identified *structural* effects (Module A1, Part A) but **no incremental
predictive power** (Module 2, Part C). Not a contradiction: an orthogonalized
shock in a VAR and out-of-sample forecasting answer different questions. A shock
can move markets on impact while the *level* carries no exploitable signal.

---

### Files
- `forsyt_gpr/` package + `run_application.py`; `figures/D1_macro_var.png`, `D2_downside.png`
- `figures/A1_aigpr_index.png`, `A2_us_irf.png`
- `figures/B1_india_gpr.png`, `B2_india_vs_nifty.png`, `B3_india_irf.png`, `B4_forecast_fit.png` *(in-sample)*
- `figures/C1_backtest.png` *(true OOS)*
- `output/us_irf_to_gpr_shock.csv`, `output/india_regressions.txt`, `output/india_vol_fit.csv`
- `output/backtest_metrics.csv`, `output/backtest_predictions.csv`
