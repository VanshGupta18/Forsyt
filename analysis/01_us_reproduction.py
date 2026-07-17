"""
Part A -- Reproduce the core Caldara & Iacoviello (2022, AER) result with the
newer LLM-based AI-GPR index:

  A geopolitical-risk shock lowers stock returns, raises stock-market
  volatility, and depresses real activity (industrial production).

We estimate a recursive (Cholesky) monthly VAR with GPR ordered first and trace
impulse responses to a one-standard-deviation GPR shock, with bootstrap bands.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from statsmodels.tsa.api import VAR

from common import (load_price, monthly_from_daily_price, load_gpr_monthly,
                    load_indpro)

plt.rcParams.update({"figure.dpi": 130, "font.size": 10})
START = "1985-01-01"      # AI-GPR normalization baseline start
EVENTS = {
    "1990-08": "Gulf War", "2001-09": "9/11", "2003-03": "Iraq War",
    "2014-03": "Crimea", "2022-02": "Russia\ninvades\nUkraine",
    "2023-10": "Gaza",
}

# ---------------------------------------------------------------- data
gpr = load_gpr_monthly()
sp = monthly_from_daily_price(load_price("SP500"))
ip = load_indpro()

# ---- Figure A1: the AI-GPR index through history --------------------
fig, ax = plt.subplots(figsize=(11, 4))
g = gpr["GPR_AI"]
ax.plot(g.index, g, lw=0.8, color="#b3202c")
ax.axhline(100, color="grey", lw=0.7, ls="--")
for ym, lab in EVENTS.items():
    d = pd.Timestamp(ym + "-01")
    if d in g.index:
        ax.annotate(lab, (d, g.loc[d]), fontsize=7, ha="center",
                    xytext=(d, min(g.loc[d] + 60, 260)),
                    arrowprops=dict(arrowstyle="-", lw=0.5, color="grey"))
ax.set_title("Figure A1 — AI-GPR Geopolitical Risk Index (mean 1985–2019 = 100)")
ax.set_ylabel("Index"); ax.set_xlim(pd.Timestamp("1985-01-01"), g.index.max())
fig.tight_layout(); fig.savefig("analysis/figures/A1_aigpr_index.png"); plt.close(fig)

# ---------------------------------------------------------------- VAR
df = pd.DataFrame({
    "logGPR":   np.log(gpr["GPR_AI"]),
    "ip":       ip["ip_growth"],
    "ret":      sp["ret"],
    "vol":      sp["rvol"],
}).dropna()
df = df.loc[START:]
print(f"VAR sample: {df.index.min():%Y-%m} to {df.index.max():%Y-%m}  (n={len(df)})")

order = ["logGPR", "ip", "ret", "vol"]        # GPR first => exogenous shock
model = VAR(df[order])
lag = model.select_order(12).selected_orders["aic"]
lag = int(max(2, min(lag, 6)))
res = model.fit(lag)
print(f"Selected lag (AIC, capped): {lag}")

H = 24
irf = res.irf(H)
# ORTHOGONALIZED (Cholesky, 1 s.d.) response to a shock in logGPR (column 0)
resp = irf.orth_irfs[:, :, 0]
ci = irf.errband_mc(orth=True, repl=500, signif=0.10, seed=1)
lo = ci[0][:, :, 0]; hi = ci[1][:, :, 0]

titles = {"logGPR": "AI-GPR (log)", "ip": "Industrial production (%)",
          "ret": "S&P 500 return (%)", "vol": "Stock volatility (ann. %)"}
fig, axes = plt.subplots(2, 2, figsize=(10, 6.5))
for k, name in enumerate(order):
    ax = axes.flat[k]
    ax.plot(resp[:, k], color="#b3202c", lw=1.6)
    ax.fill_between(range(H + 1), lo[:, k], hi[:, k], color="#b3202c", alpha=.18)
    ax.axhline(0, color="k", lw=.6)
    ax.set_title(titles[name]); ax.set_xlabel("months")
fig.suptitle("Figure A2 — Response to a 1 s.d. AI-GPR shock (recursive VAR, 90% bands)",
             y=1.02)
fig.tight_layout(); fig.savefig("analysis/figures/A2_us_irf.png",
                                bbox_inches="tight"); plt.close(fig)

# cumulative stock-price response (sum of return IRF) and peak vol response
cum_ret = resp[:, order.index("ret")].cumsum()
print(f"Cumulative S&P response @12m: {cum_ret[12]:+.2f}%   @24m: {cum_ret[24]:+.2f}%")
print(f"Peak volatility response: {resp[:, order.index('vol')].max():+.2f} ann.% "
      f"at month {resp[:, order.index('vol')].argmax()}")
print(f"Trough IP response: {resp[:, order.index('ip')].min():+.2f}% "
      f"at month {resp[:, order.index('ip')].argmin()}")

# save the IRF table
tab = pd.DataFrame(resp, columns=[f"resp_{c}" for c in order])
tab.index.name = "horizon_months"
tab.to_csv("analysis/output/us_irf_to_gpr_shock.csv")
print("saved figures A1, A2 and analysis/output/us_irf_to_gpr_shock.csv")
