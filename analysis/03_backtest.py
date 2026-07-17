"""
Part C -- HONEST OUT-OF-SAMPLE BACKTEST of NIFTY 50 volatility forecasts.

Figure B4 in 02_india_nifty.py was an IN-SAMPLE fit -- the model was estimated on
the whole sample, so it is not evidence of forecasting ability. This script does
a strict walk-forward (expanding-window) backtest:

  for each month t in the OOS period:
      estimate every model on data through t-1 ONLY
      form a 1-month-ahead forecast of NIFTY realized volatility in month t
      (all predictors dated t-1 or earlier; the high-vol threshold is also
       computed from training data only)

Models
  RW    : vol_t = vol_{t-1}                       (naive benchmark)
  AR1   : vol_t ~ vol_{t-1}
  HAR   : vol_t ~ vol_{t-1} + mean vol_{t-1..t-3} + mean vol_{t-1..t-12}
  AR1+GPRin  : AR1  + India-GPR_{t-1}
  HAR+GPRin  : HAR  + India-GPR_{t-1}
  HAR+GPRin+GPRgl : HAR + India-GPR_{t-1} + global-GPR_{t-1}

Metrics: RMSE, MAE, out-of-sample R2 vs RW and vs HAR, directional accuracy,
Diebold-Mariano tests, and high-vol "spike" classification accuracy.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

from common import (load_price, monthly_from_daily_price, load_country_monthly,
                    load_gpr_monthly)

plt.rcParams.update({"figure.dpi": 130, "font.size": 10})
MIN_TRAIN = 60          # months of history required before first forecast

# ---------------------------------------------------------------- build panel
cty = load_country_monthly()
nifty = monthly_from_daily_price(load_price("NIFTY"))
d = pd.DataFrame({
    "rvol": nifty["rvol"],
    "gpr_in": np.log(cty["India_all"]),
    "gpr_gl": np.log(load_gpr_monthly()["GPR_AI"]),
}).dropna().loc["2007-10":]

# predictors: strictly dated t-1 or earlier
d["vol_l1"] = d["rvol"].shift(1)
d["vol_3"] = d["rvol"].shift(1).rolling(3).mean()
d["vol_12"] = d["rvol"].shift(1).rolling(12).mean()
d["gpr_in_l1"] = d["gpr_in"].shift(1)
d["gpr_gl_l1"] = d["gpr_gl"].shift(1)
d = d.dropna()

MODELS = {
    "AR1":              ["vol_l1"],
    "HAR":              ["vol_l1", "vol_3", "vol_12"],
    "AR1+GPRin":        ["vol_l1", "gpr_in_l1"],
    "HAR+GPRin":        ["vol_l1", "vol_3", "vol_12", "gpr_in_l1"],
    "HAR+GPRin+GPRgl":  ["vol_l1", "vol_3", "vol_12", "gpr_in_l1", "gpr_gl_l1"],
}

def ols_fit_predict(train, cols, x_new):
    X = np.column_stack([np.ones(len(train))] + [train[c].values for c in cols])
    y = train["rvol"].values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(beta[0] + sum(b * x_new[c] for b, c in zip(beta[1:], cols)))

# ---------------------------------------------------------------- walk forward
rows = []
for i in range(MIN_TRAIN, len(d)):
    train = d.iloc[:i]            # data through t-1 only
    cur = d.iloc[i]               # month t (predictors already lagged)
    rec = {"Date": d.index[i], "actual": cur["rvol"], "vol_l1": cur["vol_l1"]}
    rec["RW"] = cur["vol_l1"]
    for name, cols in MODELS.items():
        rec[name] = ols_fit_predict(train, cols, cur)
    # high-vol threshold from TRAINING data only (no look-ahead)
    rec["thresh"] = train["rvol"].quantile(0.75)
    rows.append(rec)

bt = pd.DataFrame(rows).set_index("Date")
names = ["RW"] + list(MODELS)
print(f"OOS backtest window: {bt.index.min():%Y-%m} to {bt.index.max():%Y-%m} "
      f"({len(bt)} monthly forecasts; expanding window, min train {MIN_TRAIN}m)\n")

# ---------------------------------------------------------------- metrics
def dm_test(e1, e2, h=1):
    """Diebold-Mariano on squared errors; HAC(h-1) variance. >0 => model1 worse."""
    dl = e1 ** 2 - e2 ** 2
    dbar = dl.mean(); T = len(dl)
    g0 = np.var(dl, ddof=0)
    var = g0
    for k in range(1, h):
        gk = np.cov(dl[k:], dl[:-k])[0, 1]
        var += 2 * (1 - k / h) * gk
    se = np.sqrt(var / T)
    stat = dbar / se
    return stat, 2 * (1 - stats.norm.cdf(abs(stat)))

res = []
err = {n: (bt["actual"] - bt[n]).values for n in names}
sse_rw = (err["RW"] ** 2).sum()
sse_har = (err["HAR"] ** 2).sum()
for n in names:
    e = err[n]
    rmse = np.sqrt((e ** 2).mean()); mae = np.abs(e).mean()
    r2_rw = 1 - (e ** 2).sum() / sse_rw
    r2_har = 1 - (e ** 2).sum() / sse_har
    # directional accuracy: does the model call vol up vs down correctly?
    pred_dir = np.sign(bt[n].values - bt["vol_l1"].values)
    act_dir = np.sign(bt["actual"].values - bt["vol_l1"].values)
    # RW predicts no change, so its "direction" is undefined, not 0% correct
    hit = np.nan if n == "RW" else (pred_dir == act_dir).mean() * 100
    # spike classification (top-quartile vol month, training threshold)
    pred_hi = bt[n].values > bt["thresh"].values
    act_hi = bt["actual"].values > bt["thresh"].values
    acc = (pred_hi == act_hi).mean() * 100
    tp = (pred_hi & act_hi).sum()
    prec = 100 * tp / max(pred_hi.sum(), 1)
    rec_ = 100 * tp / max(act_hi.sum(), 1)
    res.append({"model": n, "RMSE": rmse, "MAE": mae, "R2_vs_RW": r2_rw,
                "R2_vs_HAR": r2_har, "DirAcc%": hit, "SpikeAcc%": acc,
                "SpikePrec%": prec, "SpikeRecall%": rec_})
tab = pd.DataFrame(res).set_index("model")
print("=== Out-of-sample accuracy (1-month-ahead NIFTY realized vol, ann.%) ===")
print(tab.round(3).to_string())

# class-imbalance baseline: "spike accuracy" looks high only because spikes are rare
base_rate = (bt["actual"].values > bt["thresh"].values).mean()
print(f"\n[!] Spike base rate = {base_rate*100:.1f}% of OOS months are high-vol, so a "
      f"trivial 'never predict a spike' rule\n    already scores "
      f"{(1-base_rate)*100:.1f}% SpikeAcc. Read SpikePrec/SpikeRecall, not SpikeAcc.")
print("[!] DirAcc for RW is undefined (it always predicts no change).")

print("\n=== Diebold-Mariano tests (squared errors) ===")
for a, b in [("HAR", "HAR+GPRin"), ("AR1", "AR1+GPRin"),
             ("HAR", "HAR+GPRin+GPRgl"), ("RW", "HAR")]:
    s, p = dm_test(err[a], err[b])
    verdict = ("no sig. difference" if p > .10 else
               (f"{b} better" if s > 0 else f"{a} better"))
    print(f"  {a:16s} vs {b:16s}: DM={s:+.2f}  p={p:.3f}   -> {verdict}")

# naive scale reference
print(f"\nMean actual OOS vol = {bt['actual'].mean():.2f}%, "
      f"sd = {bt['actual'].std():.2f}%  (RMSE below this = some skill)")

# ---------------------------------------------------------------- figure
fig, ax = plt.subplots(figsize=(11, 4.2))
ax.plot(bt.index, bt["actual"], color="#333", lw=1.2, label="Actual NIFTY vol")
ax.plot(bt.index, bt["HAR"], color="#1f6f3d", lw=1.0, ls="--", label="HAR (OOS)")
ax.plot(bt.index, bt["HAR+GPRin"], color="#c1121f", lw=1.0, ls="--",
        label="HAR + India-GPR (OOS)")
ax.legend(); ax.set_ylabel("ann. %")
ax.set_title("Figure C1 — TRUE out-of-sample walk-forward NIFTY vol forecasts")
fig.tight_layout(); fig.savefig("analysis/figures/C1_backtest.png"); plt.close(fig)

tab.to_csv("analysis/output/backtest_metrics.csv")
bt.to_csv("analysis/output/backtest_predictions.csv")
print("\nsaved figures/C1_backtest.png, output/backtest_metrics.csv, "
      "output/backtest_predictions.csv")
