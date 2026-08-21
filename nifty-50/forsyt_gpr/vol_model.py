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

BEGINNER GLOSSARY -- no statistics background assumed
--------------------------------------------------------
This file is the most conceptually dense one in the package. If terms like
"walk-forward", "ROC-AUC", or "leakage" are new to you, read this block
first; the functions below refer back to it instead of re-explaining
themselves every time.

- **Regression vs. classification.** Two different questions we ask of the
  same data. "Regression" predicts a NUMBER (e.g. "volatility will be
  18.3% over the next 5 days"). "Classification" predicts a CATEGORY (e.g.
  "will next-5-day volatility be HIGH or not?", yes/no). This file does
  both, on the same features, because a number and a yes/no answer serve
  different purposes on a dashboard.

- **Why we can't just train once and check the answer on the same data.**
  A model can always get very good scores on data it was trained on --
  it can effectively "memorize" the answers, the way a student who saw the
  exact exam questions in advance would ace the exam without having
  learned anything transferable. To find out if a model actually learned
  something useful, you must test it on data it never saw during training.
  That's why every score in this file comes from "out-of-sample" (OOS)
  predictions only -- rows the model was never trained on.

- **"Leakage" / "look-ahead bias".** The single easiest way to accidentally
  produce a model that looks great in testing but is useless in the real
  world: letting information from the future sneak into training, even by
  accident. Example: if you trained on rows dated up to and including test
  day t, but the target for day t-2 secretly depends on what happened on
  day t (because it's a "next 5 days" average -- see
  `data.forward_realized_vol`), then the model partially "saw the future"
  during training. This file goes out of its way to prevent that -- see
  "purged walk-forward" below.

- **Walk-forward validation, in plain terms.** Instead of picking one random
  train/test split, we replay history in order: train on everything up to
  some date, test on the next chunk, then slide forward, retrain on
  everything up to the NEW date (which now includes the previous test
  chunk), test on the next chunk after that, and so on to the end of the
  data. This mimics how the model would actually be used in production --
  it is always trained only on the past relative to whatever it's
  currently predicting.

- **The "purge" / embargo, and why it's needed.** Because each target value
  (e.g. "volatility over the next 5 days") is computed from `horizon` days
  of FUTURE returns, a target dated 3 days before the test block still
  reaches forward into days that overlap the test block itself. Training
  right up to the test date would leak those overlapping days backward into
  the model. The fix: stop training `horizon` days BEFORE the test block
  starts (an "embargo" or "purge" of that many days), so no training target
  ever overlaps a testing target. See `purged_walk_forward()` below for the
  actual mechanics.

- **The metrics, one line each:**
    * RMSE (Root Mean Squared Error) -- the typical size of the model's
      prediction error, in the same units as the target (% volatility
      here). Smaller is better. Big mistakes are penalized extra hard
      (because the errors are squared before averaging).
    * MAE (Mean Absolute Error) -- also a typical error size, but treats
      every mistake equally regardless of how big it is. Easier to read as
      "on average, the forecast was off by this many percentage points."
    * R² vs. persistence -- not the textbook R², but "how much better (or
      worse) is this model than the dumbest possible forecast: just
      guessing that tomorrow's volatility will equal today's ('persistence')?
      1.0 = perfect, 0.0 = no better than that naive guess, negative = WORSE
      than just guessing today's value again.
    * ROC-AUC (Receiver Operating Characteristic -- Area Under Curve) -- for
      the yes/no HIGH_VOL prediction: if you grabbed one truly-high-vol day
      and one truly-normal day at random, ROC-AUC is the probability the
      model correctly scored the high-vol day as riskier. 0.5 = pure
      coin-flip (no skill), 1.0 = perfect separation.
    * PR-AUC (Precision-Recall AUC) -- like ROC-AUC, but more honest when
      the "yes" category is rare (here, HIGH_VOL days are only ~12% of
      days by construction -- see `threshold_q`). A model that just always
      predicts "not high vol" would still get a deceptively decent-looking
      ROC-AUC; PR-AUC is much harder to fake that way.
    * base_rate -- literally, what fraction of days in the test set actually
      were HIGH_VOL. Reported so nobody mistakes "88% accuracy" for skill
      when the trivial "never predict a spike" rule would already score
      ~88% (because spikes are rare).

- **Why three model "blocks" (`market_only`, `gpr_only`, `market+gpr`)?**
  See features.py's beginner note. In short: comparing `market+gpr` against
  `market_only` (both evaluated the exact same way) is the only way to
  isolate what GPR itself contributed, because market-only volatility
  clustering can make a model look skillful on its own.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score
from xgboost import XGBRegressor, XGBClassifier

from .features import assemble


def _xgb_reg(seed=0):
    # XGBoost = "gradient-boosted decision trees": it builds many small,
    # simple decision trees one after another, where each new tree focuses
    # on correcting the mistakes of the trees built so far. The settings
    # below (shallow trees `max_depth=3`, a slow `learning_rate`, and only
    # using 80% of rows/columns per tree via `subsample`/`colsample_bytree`)
    # are all standard ways to stop the model from just memorizing the
    # training data ("overfitting") -- important here because financial
    # history is short and noisy compared to, say, image datasets.
    return XGBRegressor(n_estimators=300, max_depth=3, learning_rate=0.05,
                        subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0,
                        min_child_weight=10, random_state=seed, n_jobs=4,
                        tree_method="hist")


def _xgb_clf(seed=0):
    # Same idea as _xgb_reg, but this one predicts a yes/no probability
    # (HIGH_VOL or not) instead of a number.
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

    Walking through the loop in plain language:
      - We start once we have `min_train` rows of history (750 trading days,
        roughly 3 years) -- not enough history yet to trust a model before
        that.
      - Each pass through the loop trains ONE model on everything known so
        far, then uses it to predict the next `refit_every` days (21 trading
        days, about a month) -- that's the "expanding window, refit
        periodically" part: the training set keeps growing as we walk
        forward through history, but we don't bother retraining every single
        day (too slow, and one day rarely changes the model much).
      - `tr_end = start - horizon` is the purge described in the module
        docstring: it chops `horizon` days off the END of the training set
        so that no training target's forward-looking window overlaps the
        upcoming test block.
      - For classification, `thr` (the cutoff that defines "HIGH_VOL") is
        computed ONLY from the training labels seen so far, then reused to
        label that block's test rows. This matters because if the cutoff
        were computed using the full dataset (including future test rows),
        that would itself be a subtle form of leakage.
      - Every prediction is written into `out` at the same date it is
        predicting for, so the returned Series lines up one-to-one with `y`
        and can be compared to it directly.
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

    THIS IS THE RESEARCH ENTRY POINT (as opposed to `latest_market_forecast()`
    below, which is what the live product actually calls). Run this when you
    want the honest, walk-forward-backtested answer to "does GPR help predict
    NIFTY volatility, and by how much?" -- it is slower and needs a full GPR
    history, which is why it isn't called on every dashboard page load.
    It builds and scores all three feature blocks (`market_only`, `gpr_only`,
    `market+gpr`) side by side, on identical folds, and returns two small
    tables: one scoring the plain numeric volatility forecast (RMSE/MAE/R²),
    one scoring the HIGH_VOL yes/no classification (ROC-AUC/PR-AUC/F1/base
    rate) -- see the glossary at the top of this file for what each metric
    means.
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
    # "Persistence" = the dumbest possible forecast: just assume tomorrow's
    # (well, next `horizon` days') volatility will look like the recent
    # trailing volatility. Any model worth using should beat this baseline;
    # it's what "R2_vs_persistence" below is measured against.
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
    # Same three feature blocks, but now scored as a yes/no prediction
    # ("will the next `horizon` days be unusually volatile?") instead of a
    # plain number -- see the ROC-AUC/PR-AUC/base_rate glossary above.
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


def latest_market_forecast(price: pd.Series, horizon: int = 5,
                           threshold_q: float = 0.75) -> dict:
    """Production forecast using market features only (no GPR required).

    Use this for the live product while Forsyt GPR history is still short.

    WHY THIS FUNCTION EXISTS SEPARATELY FROM `run_vol_experiment()` /
    `latest_forecast()`: this is the version the live dashboard actually
    calls (via `dual_signal.nifty_vol_signal()`), and it is deliberately
    kept as simple and low-risk as possible:

      - It only needs a price series -- no GPR data at all, and therefore
        cannot fail just because the GPR frame is missing, malformed, or too
        short (a real risk while Forsyt's own India index is still young).
      - It fits ONE model, ONE time, on all available resolved history, then
        scores the single most recent day. There is no walk-forward loop
        here -- that machinery exists purely to produce a trustworthy
        RESEARCH SCORE (how good is this model, honestly?), not to produce
        today's forecast. Once you trust the approach (from
        `run_vol_experiment()`'s backtest), the production forecast can
        just use ALL the data, because there's no more "held-out test set"
        to protect -- there IS no ground truth yet for a forecast about the
        future.
      - Fewer moving parts means fewer ways this can silently break when run
        unattended every day by a scheduled job -- see the scheduling table
        in `nifty-50/docs/INTEGRATION.md`. `dual_signal.py` still keeps an
        even-simpler trailing-volatility fallback for the rare case this
        itself raises (too little history).

    In short: `run_vol_experiment()` answers "should we trust this idea at
    all?" (research, slow, needs a full GPR history); this function answers
    "given that we trust it, what's today's number?" (production, fast,
    market-data-only).
    """
    from .data import forward_realized_vol
    from .features import market_features

    y = forward_realized_vol(price, horizon)
    Xm_all = market_features(price)
    feat = Xm_all.dropna()
    if feat.empty:
        raise ValueError("no rows with complete market features")
    mcols = list(Xm_all.columns)
    train = feat.join(y.rename("y")).dropna()
    asof = feat.index[-1]
    if len(train) < 250:
        raise ValueError(f"only {len(train)} resolved training rows (need 250+)")
    thr = np.quantile(train["y"], threshold_q)

    out = {
        "as_of": asof.strftime("%Y-%m-%d"),
        "horizon_days": horizon,
        "high_vol_threshold": round(float(thr), 2),
        "target_resolves_on": (
            price.index[price.index.get_loc(asof) + horizon].strftime("%Y-%m-%d")
            if price.index.get_loc(asof) + horizon < len(price) else None
        ),
    }
    reg = _xgb_reg().fit(train[mcols].values, train["y"].values)
    clf = _xgb_clf().fit(train[mcols].values, (train["y"].values > thr).astype(int))
    xrow = feat[mcols].iloc[[-1]].values
    market = {
        "vol_forecast": round(float(reg.predict(xrow)[0]), 2),
        "high_vol_prob": round(float(clf.predict_proba(xrow)[0, 1]), 3),
    }
    out["market_only"] = market
    out["headline"] = market
    return out


def latest_forecast(gf: pd.DataFrame, price: pd.Series, horizon: int = 5,
                    threshold_q: float = 0.75, block: str = "market+gpr") -> dict:
    """PRODUCTION path: fit on all resolved history, predict the newest day.

    Unlike run_vol_experiment (which back-tests), this is what a daily job calls:
    train on every row whose forward target is already known, then score the most
    recent row whose features exist but whose target is still in the future.

    Returns a JSON-friendly record: the point vol forecast, the HIGH_VOL
    probability, the (train-derived) high-vol threshold, and -- crucially -- the
    market_only counterpart, so the dashboard can always show what GPR added.

    HOW THIS DIFFERS FROM `latest_market_forecast()` ABOVE: this version
    needs a valid, sufficiently long GPR frame (it builds and requires
    `gpr_features()` to succeed), fits THREE models instead of one
    (`market_only`, `gpr_only`, `market+gpr`), and reports `gpr_added_vol` --
    the difference between the `market+gpr` and `market_only` point
    forecasts, so a reader can see exactly how much (if anything) GPR moved
    the number for today specifically. It is more informative but has more
    ways to fail (a short or messy GPR history breaks it), which is exactly
    why the live product defaults to the simpler `latest_market_forecast()`
    instead and only falls back to trailing volatility, never to this
    function, if that fails -- see `dual_signal.nifty_vol_signal()`.
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

    What SHAP actually is, briefly: it's a technique that takes an already-
    trained model and, for each feature, estimates how much that feature
    pushed a given prediction up or down. It answers "what did the model pay
    attention to?" -- a question about the model's internal behaviour. It
    does NOT answer "is the model actually good at predicting the future?" --
    that is a completely different question, answered only by the
    out-of-sample walk-forward tables from `run_vol_experiment()`. A model
    can rely heavily on GPR features (high SHAP importance) purely because
    they happen to move together with market volatility clustering, without
    GPR having any genuine out-of-sample predictive value at all -- which is
    exactly the trap this whole module is built to avoid falling into.
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
