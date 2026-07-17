"""
Runner for application.md -- exercises the three modules on real data.

  Module 2 (MD 2)  : XGBoost forward-vol model, NIFTY + S&P, purged walk-forward
  Module A1 (MD A) : VAR -> corporate investment & employment IRFs
  Module A2 (MD A) : quantile regression -> downside/disaster risk

Everything runs off the canonical GPR frame, so swapping in Forsyt's India index
is a one-line change (see the FORSYT note at the bottom).
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from forsyt_gpr import data, vol_model, macro_var, downside

plt.rcParams.update({"figure.dpi": 130, "font.size": 9})
pd.set_option("display.width", 130)

gf = data.load_aigpr_daily()
nifty = data.load_price("NIFTY")
spx = data.load_price("SP500")

# ===================================================================== MD 2
print("=" * 78)
print("MODULE 2 (MD sec.2) -- XGBoost forward realized volatility")
print("=" * 78)
for label, px in [("NIFTY 50", nifty), ("S&P 500", spx)]:
    print(f"\n--- {label} ---")
    reg, clf, _ = vol_model.run_vol_experiment(gf, px, horizon=5, min_train=750,
                                               refit_every=21)
    print("Regression (target: realized vol over next 5 trading days)")
    print(reg.round(3).to_string())
    print("\nClassification (HIGH_VOL = top 25% of forward vol)")
    print(clf.round(3).to_string())
    inc = (reg.loc["XGB[market+gpr]", "R2_vs_persistence"]
           - reg.loc["XGB[market_only]", "R2_vs_persistence"])
    inc_auc = (clf.loc["XGB[market+gpr]", "ROC_AUC"]
               - clf.loc["XGB[market_only]", "ROC_AUC"]) if len(clf) == 3 else float("nan")
    print(f"\n>>> INCREMENTAL value of GPR features: dR2={inc:+.4f}  dROC_AUC={inc_auc:+.4f}")
    print("    (market+gpr minus market_only -- this, not the headline score,")
    print("     is what tests the geopolitical thesis)")

print("\n--- SHAP (full-sample fit, NIFTY; explanation only, not validation) ---")
imp, gpr_cols = vol_model.shap_importance(gf, nifty, horizon=5, top=12)
for k, v in imp.items():
    tag = "  <- GPR" if k in gpr_cols else ""
    print(f"   {k:22s} {v:7.4f}{tag}")
share = imp[[c for c in imp.index if c in gpr_cols]].sum() / imp.sum() * 100
print(f"   GPR share of top-12 mean|SHAP|: {share:.1f}%")

# ==================================================================== MD A1
print("\n" + "=" * 78)
print("MODULE A1 (MD sec.A) -- VAR: investment & employment response to GPR shock")
print("=" * 78)
neworder = data.load_fred("NEWORDER")
payems = data.load_fred("PAYEMS")
macro = {
    "investment": (np.log(neworder).diff() * 100).resample("MS").last(),   # capex proxy
    "employment": (np.log(payems).diff() * 100).resample("MS").last(),
    "stock_ret":  (np.log(spx).diff().resample("MS").sum() * 100),
}
irf, lo, hi, res = macro_var.run_macro_var(gf, macro, horizon=24, start="1992-02-01")
print(f"VAR lags={res.k_ar}  n={res.nobs}")
print("\nPeak/trough response to a 1 s.d. GPR shock (%):")
print(macro_var.summarize(irf).round(3).to_string())

fig, axes = plt.subplots(1, 4, figsize=(13, 3))
for ax, c in zip(axes, irf.columns):
    ax.plot(irf[c], color="#b3202c", lw=1.5)
    ax.fill_between(irf.index, lo[c], hi[c], color="#b3202c", alpha=.18)
    ax.axhline(0, color="k", lw=.6); ax.set_title(c); ax.set_xlabel("months")
fig.suptitle("Module A1 — response to a 1 s.d. GPR shock (recursive VAR, 90% bands)", y=1.04)
fig.tight_layout(); fig.savefig("analysis/figures/D1_macro_var.png", bbox_inches="tight")
plt.close(fig)

# ==================================================================== MD A2
print("\n" + "=" * 78)
print("MODULE A2 (MD sec.A) -- downside risk: quantile regression")
print("=" * 78)
print("Claim under test (MD sec.A): higher GPR => LARGER DOWNSIDE risk.")
print("That predicts beta(0.05) strongly NEGATIVE and below beta(0.50).\n")
for label, px in [("NIFTY 50", nifty), ("S&P 500", spx)]:
    for spec in ("shock", "level"):
        curve = downside.quantile_curve(gf, px, horizon=21, spec=spec)
        a = downside.tail_asymmetry(curve)
        note = "CORRECT spec" if spec == "shock" else "confounded, diagnostic only"
        print(f"--- {label}  spec={spec} ({note})  n={curve.attrs['n']} ---")
        if spec == "shock":
            print(curve.round(3).to_string())
        print(f"  left-tail beta {a['left_tail_beta']:+.2f} vs median "
              f"{a['median_beta']:+.2f} -> gap {a['left_minus_median']:+.2f}"
              f"{'   <-- WRONG SIGN vs the claim' if a['left_minus_median'] > 0 else ''}\n")

fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
for ax, (label, px) in zip(axes, [("NIFTY 50", nifty), ("S&P 500", spx)]):
    c = downside.quantile_curve(gf, px, horizon=21)
    ax.plot(c.index, c["beta_gpr"], "o-", color="#1f6f3d")
    ax.fill_between(c.index, c["beta_gpr"] - 1.645 * c["se"],
                    c["beta_gpr"] + 1.645 * c["se"], color="#1f6f3d", alpha=.18)
    ax.axhline(0, color="k", lw=.6)
    ax.set_title(f"{label}: effect of GPR by return quantile")
    ax.set_xlabel("quantile of forward 21d return"); ax.set_ylabel("beta on GPR shock")
fig.suptitle("Module A2 — if GPR is a tail risk, the left side sits below the right", y=1.05)
fig.tight_layout(); fig.savefig("analysis/figures/D2_downside.png", bbox_inches="tight")
plt.close(fig)

print("\nsaved analysis/figures/D1_macro_var.png, D2_downside.png")
print("""
FORSYT PLUG-IN
--------------
    from forsyt_gpr.data import as_gpr_frame
    raw = pd.read_sql("select day, india_gpr, threats, acts from gpr_index", con)
    gf  = as_gpr_frame(raw.set_index("day"), gpr="india_gpr",
                       threats="threats", acts="acts")
    reg, clf, _ = vol_model.run_vol_experiment(gf, nifty, horizon=5)
Every module above then runs unchanged on Forsyt's own index.
""")
