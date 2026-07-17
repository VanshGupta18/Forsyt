"""
MD section 2 -- "GPR features in predictive algorithms (Random Forest, XGBoost,
Neural Networks)" to model FUTURE realized volatility of Nifty 50 / S&P 500.

  Target Y : realized volatility over the NEXT `horizon` trading days
  Features X: GPRT score, GPRA score, moving averages of GPR  (MD section 2)
              + market controls (trailing vol, momentum) -- the BASELINE

DESIGN DECISIONS THAT MAKE THE RESULT TRUSTWORTHY
-------------------------------------------------
1. INCREMENTAL VALUE, not headline accuracy. We fit `market` and `market+gpr`
   on identical folds. GPR's contribution is the DIFFERENCE. A single ROC-AUC
   from a model fed both blocks proves nothing -- volatility clustering alone
   scores well, and SHAP will still hand importance to GPR features that ride
   along with the vol regime.

2. PURGED walk-forward. The target at t spans t+1..t+horizon, so consecutive
   targets OVERLAP. Training right up to the test date leaks future returns
   backwards. We embargo `horizon` days between train and test.

3. Thresholds and scalers are fit on TRAINING data only, inside each fold.

4. Class imbalance is reported explicitly -- PR-AUC and the base rate, because
   'accuracy' on a rare HIGH_VOL label is just the base rate in disguise.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score
from xgboost import XGBRegressor, XGBClassifier

from .features import assemble


def _xgb_reg(seed=0):
    return XGBRegressor(n_estimators=300, max_depth=3, learning_rate=0.05,
                        subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0,
                        min_child_weight=10, random_state=seed, n_jobs=4,
                        tree_method="hist")


def _xgb_clf(seed=0):
    return XGBClassifier(n_estimators=300, max_depth=3, learning_rate=0.05,
                         subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0,
                         min_child_weight=10, random_state=seed, n_jobs=4,
                         eval_metric="logloss", tree_method="hist")


# ------------------------------------------------------------------ engine
def purged_walk_forward(X: pd.DataFrame, y: pd.Series, make_model, horizon: int,
                        min_train: int = 750, refit_every: int = 21,
                        classify: bool = False, threshold_q: float = 0.75):
    """Expanding-window walk-forward with a `horizon`-day purge.

    For a test block starting at position i, training uses positions
    [0, i-horizon-1] only: the last usable training target ends at i-1, so no
    training label peeks into the test block. Returns predictions aligned to y.
    """
    n = len(X)
    out = pd.Series(np.nan, index=y.index, dtype=float)
    thr_used = pd.Series(np.nan, index=y.index, dtype=float)
    Xv, yv = X.values, y.values

    for start in range(min_train, n, refit_every):
        stop = min(start + refit_every, n)
        tr_end = start - horizon                     # <-- the purge
        if tr_end < min_train // 2:
            continue
        Xtr, ytr = Xv[:tr_end], yv[:tr_end]
        if classify:
            thr = np.quantile(ytr, threshold_q)      # threshold from TRAIN only
            m = make_model()
            m.fit(Xtr, (ytr > thr).astype(int))
            out.iloc[start:stop] = m.predict_proba(Xv[start:stop])[:, 1]
            thr_used.iloc[start:stop] = thr
        else:
            m = make_model()
            m.fit(Xtr, ytr)
            out.iloc[start:stop] = m.predict(Xv[start:stop])
    return (out, thr_used) if classify else out


# ------------------------------------------------------------------ runner
def run_vol_experiment(gf: pd.DataFrame, price: pd.Series, horizon: int = 5,
                       min_train: int = 750, refit_every: int = 21,
                       threshold_q: float = 0.75, verbose: bool = True):
    """Full MD-section-2 experiment. Returns (regression_table, classification_table, detail).

    `gf` is any canonical GPR frame -- AI-GPR today, Forsyt's India index later.
    """
    from .data import forward_realized_vol
    y = forward_realized_vol(price, horizon)
    Xm, Xg, y = assemble(gf, price, y)
    Xmg = pd.concat([Xm, Xg], axis=1)

    # Fail loudly: a silent feature-alignment collapse must never look like a
    # weak result. (log(0) in a sub-index once shrank this sample to n=8.)
    if len(y) <= min_train:
        raise ValueError(
            f"only {len(y)} aligned rows after feature construction, but "
            f"min_train={min_train}. Check for all-NaN feature columns "
            f"(gpr_features().notna().sum()) before trusting any output.")

    blocks = {"market_only": Xm, "gpr_only": Xg, "market+gpr": Xmg}
    if verbose:
        print(f"sample {y.index.min():%Y-%m-%d} -> {y.index.max():%Y-%m-%d}  "
              f"n={len(y)}  horizon={horizon}d")
        print(f"features: market={Xm.shape[1]}  gpr={Xg.shape[1]}\n")

    # ---- naive benchmark: forward vol == trailing vol over same window
    persistence = Xm[f"rv{horizon}"] if f"rv{horizon}" in Xm else Xm["rv5"]

    # ---- regression
    reg_pred = {"persistence": persistence}
    for name, X in blocks.items():
        reg_pred[f"XGB[{name}]"] = purged_walk_forward(
            X, y, _xgb_reg, horizon, min_train, refit_every)

    mask = reg_pred["XGB[market_only]"].notna()
    yt = y[mask]
    base_sse = ((yt - reg_pred["persistence"][mask]) ** 2).sum()
    rows = []
    for name, p in reg_pred.items():
        e = yt - p[mask]
        rows.append({"model": name, "RMSE": float(np.sqrt((e ** 2).mean())),
                     "MAE": float(np.abs(e).mean()),
                     "R2_vs_persistence": float(1 - (e ** 2).sum() / base_sse)})
    reg_tab = pd.DataFrame(rows).set_index("model")

    # ---- classification (HIGH_VOL vs NORMAL, Forsyt's stated target)
    rows = []
    proba = {}
    for name, X in blocks.items():
        p, thr = purged_walk_forward(X, y, _xgb_clf, horizon, min_train,
                                     refit_every, classify=True,
                                     threshold_q=threshold_q)
        proba[name] = p
        m2 = p.notna()
        lab = (y[m2] > thr[m2]).astype(int)
        if lab.nunique() < 2:
            continue
        rows.append({"model": f"XGB[{name}]",     # match reg_tab's naming
                     "ROC_AUC": roc_auc_score(lab, p[m2]),
                     "PR_AUC": average_precision_score(lab, p[m2]),
                     "F1@0.5": f1_score(lab, (p[m2] > 0.5).astype(int), zero_division=0),
                     "base_rate": float(lab.mean())})
    cols = ["model", "ROC_AUC", "PR_AUC", "F1@0.5", "base_rate"]
    clf_tab = (pd.DataFrame(rows, columns=cols).set_index("model") if rows
               else pd.DataFrame(columns=cols[1:]))

    detail = {"y": y, "reg_pred": reg_pred, "proba": proba,
              "X": blocks, "horizon": horizon}
    return reg_tab, clf_tab, detail


def latest_forecast(gf: pd.DataFrame, price: pd.Series, horizon: int = 5,
                    threshold_q: float = 0.75, block: str = "market+gpr") -> dict:
    """PRODUCTION path: fit on all resolved history, predict the newest day.

    Unlike run_vol_experiment (which back-tests), this is what a daily job calls:
    train on every row whose forward target is already known, then score the most
    recent row whose features exist but whose target is still in the future.

    Returns a JSON-friendly record: the point vol forecast, the HIGH_VOL
    probability, the (train-derived) high-vol threshold, and -- crucially -- the
    market_only counterpart, so the dashboard can always show what GPR added.
    """
    from .data import forward_realized_vol
    from .features import gpr_features, market_features
    y = forward_realized_vol(price, horizon)
    Xm_all = market_features(price)
    Xg_all = gpr_features(gf).reindex(price.index, method="ffill")
    full = pd.concat([Xm_all, Xg_all], axis=1)
    feat = full.dropna()                              # rows with complete features
    if feat.empty:
        raise ValueError("no rows with complete features; check the GPR frame")
    mcols, gcols = list(Xm_all.columns), list(Xg_all.columns)
    blocks = {"market_only": mcols, "gpr_only": gcols, "market+gpr": mcols + gcols}
    if block not in blocks:
        raise ValueError(f"block must be one of {list(blocks)}")

    train = feat.join(y.rename("y")).dropna()          # target resolved => trainable
    asof = feat.index[-1]                              # newest day we can score
    if len(train) < 250:
        raise ValueError(f"only {len(train)} resolved training rows")
    thr = np.quantile(train["y"], threshold_q)

    out = {"as_of": asof.strftime("%Y-%m-%d"), "horizon_days": horizon,
           "target": f"annualized realized vol, next {horizon} trading days (%)",
           "high_vol_threshold": round(float(thr), 2),
           "target_resolves_on": price.index[price.index.get_loc(asof) + horizon].strftime("%Y-%m-%d")
           if price.index.get_loc(asof) + horizon < len(price) else None}
    for name, cols in blocks.items():
        reg = _xgb_reg().fit(train[cols].values, train["y"].values)
        clf = _xgb_clf().fit(train[cols].values, (train["y"].values > thr).astype(int))
        xrow = feat[cols].iloc[[-1]].values
        out[name] = {"vol_forecast": round(float(reg.predict(xrow)[0]), 2),
                     "high_vol_prob": round(float(clf.predict_proba(xrow)[0, 1]), 3)}
    out["headline"] = out[block]
    out["gpr_added_vol"] = round(out["market+gpr"]["vol_forecast"]
                                 - out["market_only"]["vol_forecast"], 2)
    return out


def shap_importance(gf, price, horizon=5, top=15):
    """SHAP on a single full-sample fit -- for EXPLANATION ONLY.

    NB: this is in-sample and says what the model *used*, never whether the
    model is any good. Judge that from run_vol_experiment's walk-forward tables.
    """
    import shap
    from .data import forward_realized_vol
    y = forward_realized_vol(price, horizon)
    Xm, Xg, y = assemble(gf, price, y)
    X = pd.concat([Xm, Xg], axis=1)
    m = _xgb_reg().fit(X.values, y.values)
    sv = shap.TreeExplainer(m).shap_values(X.values)
    imp = pd.Series(np.abs(sv).mean(0), index=X.columns).sort_values(ascending=False)
    return imp.head(top), set(Xg.columns)
