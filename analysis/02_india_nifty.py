"""
Part B -- Extend the Caldara/Iacoviello framework to INDIA:

  Does India-specific geopolitical risk (the AI-GPR country index for India)
  move and forecast the volatility of the NIFTY 50?

Steps
  1. India-GPR history with major India-centric geopolitical events.
  2. Monthly NIFTY 50 realized volatility & returns from daily ^NSEI (2007-).
  3. Contemporaneous & PREDICTIVE regressions of NIFTY vol on India-GPR
     (Newey-West/HAC standard errors).
  4. Bivariate recursive VAR [India-GPR, NIFTY vol] -> impulse response.
  5. In-sample fit + a conditional next-months volatility forecast.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import statsmodels.api as sm
from statsmodels.tsa.api import VAR

from common import (load_price, monthly_from_daily_price, load_country_monthly,
                    load_gpr_monthly)

plt.rcParams.update({"figure.dpi": 130, "font.size": 10})

IN_EVENTS = {
    "1999-05": "Kargil War", "2001-12": "Parliament\nattack",
    "2008-11": "26/11\nMumbai", "2016-09": "Uri /\nsurgical strike",
    "2019-02": "Pulwama /\nBalakot", "2020-06": "Galwan\n(China)",
    "2025-05": "2025\nPak flare-up",
}

# ---------------------------------------------------------------- data
cty = load_country_monthly()
india = cty["India_all"].rename("gpr_india")
gpr_glob = load_gpr_monthly()["GPR_AI"].rename("gpr_global")   # global AI-GPR
nifty = monthly_from_daily_price(load_price("NIFTY"))   # ret, rvol

# ---- Figure B1: India-GPR history ----------------------------------
fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(india.index, india, lw=0.8, color="#1f6f3d")
ax.axhline(india.loc["1985":"2019"].mean(), color="grey", lw=.7, ls="--")
for ym, lab in IN_EVENTS.items():
    d = pd.Timestamp(ym + "-01")
    if d in india.index:
        ax.annotate(lab, (d, india.loc[d]), fontsize=7, ha="center",
                    xytext=(d, min(india.loc[d] + 12, 55)),
                    arrowprops=dict(arrowstyle="-", lw=.5, color="grey"))
ax.set_title("Figure B1 — AI-GPR Country Geopolitical Risk: INDIA")
ax.set_ylabel("India-GPR index"); ax.set_xlim(pd.Timestamp("1990-01-01"), india.index.max())
fig.tight_layout(); fig.savefig("analysis/figures/B1_india_gpr.png"); plt.close(fig)

# ---------------------------------------------------------------- merge (Nifty era)
df = pd.concat([np.log(india).rename("logGPR"),
                np.log(gpr_glob).rename("logGPR_glob"), nifty], axis=1).dropna()
df = df.loc["2007-10":]
print(f"NIFTY sample: {df.index.min():%Y-%m} to {df.index.max():%Y-%m}  (n={len(df)})")
print("India-GPR vs NIFTY vol  contemp corr:",
      round(df["logGPR"].corr(df["rvol"]), 3))

# ---- Figure B2: India-GPR vs NIFTY realized vol --------------------
fig, ax1 = plt.subplots(figsize=(11, 4))
ax1.plot(df.index, df["rvol"], color="#333", lw=1.0, label="NIFTY realized vol (ann.%)")
ax1.set_ylabel("NIFTY realized volatility (ann.%)")
ax2 = ax1.twinx()
ax2.plot(df.index, np.exp(df["logGPR"]), color="#1f6f3d", lw=1.0, alpha=.7,
         label="India-GPR")
ax2.set_ylabel("India-GPR index", color="#1f6f3d")
ax1.set_title("Figure B2 — India geopolitical risk vs NIFTY 50 volatility")
fig.tight_layout(); fig.savefig("analysis/figures/B2_india_vs_nifty.png"); plt.close(fig)

# ---------------------------------------------------------------- regressions
def hac(y, X, L=6):
    return sm.OLS(y, sm.add_constant(X), missing="drop").fit(
        cov_type="HAC", cov_kwds={"maxlags": L})

d = df.copy()
d["logGPR_l1"] = d["logGPR"].shift(1)
d["logGPRg_l1"] = d["logGPR_glob"].shift(1)
d["rvol_l1"] = d["rvol"].shift(1)
d = d.dropna()

print("\n--- (1) Contemporaneous: NIFTY vol ~ India-GPR ---")
m1 = hac(d["rvol"], d[["logGPR"]])
print(f"  beta(logGPR)={m1.params['logGPR']:+.2f}  t={m1.tvalues['logGPR']:+.2f}"
      f"  R2={m1.rsquared:.3f}")

print("--- (2) Predictive: NIFTY vol_t ~ India-GPR_{t-1} (+ vol_{t-1}) ---")
m2 = hac(d["rvol"], d[["logGPR_l1", "rvol_l1"]])
print(f"  beta(GPR_l1)={m2.params['logGPR_l1']:+.2f}  t={m2.tvalues['logGPR_l1']:+.2f}"
      f"  (persistence rvol_l1={m2.params['rvol_l1']:.2f})  R2={m2.rsquared:.3f}")

print("--- (3) Predictive: NIFTY return_t ~ India-GPR_{t-1} ---")
m3 = hac(d["ret"], d[["logGPR_l1"]])
print(f"  beta(GPR_l1)={m3.params['logGPR_l1']:+.2f}  t={m3.tvalues['logGPR_l1']:+.2f}"
      f"  R2={m3.rsquared:.3f}")

print("--- (4) Horse race: NIFTY vol_t ~ vol_{t-1} + India-GPR_{t-1} + GLOBAL-GPR_{t-1} ---")
m4 = hac(d["rvol"], d[["rvol_l1", "logGPR_l1", "logGPRg_l1"]])
print(f"  India-GPR_l1 ={m4.params['logGPR_l1']:+.2f} (t={m4.tvalues['logGPR_l1']:+.2f})   "
      f"GLOBAL-GPR_l1={m4.params['logGPRg_l1']:+.2f} (t={m4.tvalues['logGPRg_l1']:+.2f})   "
      f"R2={m4.rsquared:.3f}")
print("--- (4b) Contemporaneous global: NIFTY vol ~ GLOBAL-GPR ---")
m4b = hac(d["rvol"], d[["logGPR_glob"]])
print(f"  beta(GLOBAL-GPR)={m4b.params['logGPR_glob']:+.2f} (t={m4b.tvalues['logGPR_glob']:+.2f})"
      f"  R2={m4b.rsquared:.3f}")

# ---------------------------------------------------------------- VAR + IRF
order = ["logGPR", "ret", "rvol"]
vmodel = VAR(df[order]); lag = 2
vres = vmodel.fit(lag)
H = 18
irf = vres.irf(H)
resp = irf.orth_irfs[:, :, 0]                       # shock to India-GPR
ci = irf.errband_mc(orth=True, repl=500, signif=0.10, seed=7)
lo = ci[0][:, :, 0]; hi = ci[1][:, :, 0]

titles = {"logGPR": "India-GPR (log)", "ret": "NIFTY return (%)",
          "rvol": "NIFTY volatility (ann.%)"}
fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
for k, name in enumerate(order):
    ax = axes[k]
    ax.plot(resp[:, k], color="#1f6f3d", lw=1.6)
    ax.fill_between(range(H + 1), lo[:, k], hi[:, k], color="#1f6f3d", alpha=.18)
    ax.axhline(0, color="k", lw=.6); ax.set_title(titles[name]); ax.set_xlabel("months")
fig.suptitle("Figure B3 — NIFTY response to a 1 s.d. India-GPR shock (90% bands)", y=1.03)
# NOTE: the forecast block below is IN-SAMPLE only; see 03_backtest.py for a
# true walk-forward out-of-sample evaluation (India-GPR adds no OOS skill).
fig.tight_layout(); fig.savefig("analysis/figures/B3_india_irf.png",
                                bbox_inches="tight"); plt.close(fig)
print(f"\nVAR: peak NIFTY-vol response to India-GPR shock = "
      f"{resp[:, 2].max():+.2f} ann.% at month {resp[:, 2].argmax()}")

# ---------------------------------------------------------------- forecast model
# Predictive vol model: rvol_t = a + b*rvol_{t-1} + c*logGPR_{t-1}
fit = m2
d["vol_fitted"] = fit.predict(sm.add_constant(d[["logGPR_l1", "rvol_l1"]]))
fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(d.index, d["rvol"], color="#333", lw=1.0, label="Actual NIFTY vol")
ax.plot(d.index, d["vol_fitted"], color="#c1121f", lw=1.2, ls="--",
        label="Model fit (India-GPR + lag)")
ax.legend(); ax.set_ylabel("ann. %")
ax.set_title("Figure B4 — NIFTY 50 volatility vs India-GPR model (IN-SAMPLE fit, "
             "not a forecast — see Fig C1)")
fig.tight_layout(); fig.savefig("analysis/figures/B4_forecast_fit.png"); plt.close(fig)

# one-step conditional prediction for the month after the sample
last = df.iloc[-1]
pred_next = (fit.params["const"] + fit.params["rvol_l1"] * last["rvol"]
             + fit.params["logGPR_l1"] * last["logGPR"])
print(f"\nLatest month {df.index[-1]:%Y-%m}: India-GPR={np.exp(last['logGPR']):.1f}, "
      f"NIFTY vol={last['rvol']:.1f}%")
print(f"Model 1-month-ahead NIFTY volatility forecast: {pred_next:.1f}% ann.")

# save regression summary + fitted series
with open("analysis/output/india_regressions.txt", "w") as f:
    f.write("(1) CONTEMPORANEOUS  NIFTY vol ~ India-GPR\n" + str(m1.summary()) + "\n\n")
    f.write("(2) PREDICTIVE  NIFTY vol_t ~ India-GPR_{t-1} + vol_{t-1}\n" + str(m2.summary()) + "\n\n")
    f.write("(3) PREDICTIVE  NIFTY ret_t ~ India-GPR_{t-1}\n" + str(m3.summary()) + "\n\n")
    f.write("(4) HORSE RACE  NIFTY vol_t ~ vol_{t-1} + India-GPR_{t-1} + GLOBAL-GPR_{t-1}\n"
            + str(m4.summary()) + "\n")
d[["rvol", "vol_fitted", "logGPR"]].to_csv("analysis/output/india_vol_fit.csv")
print("saved figures B1-B4 and analysis/output/india_regressions.txt")
