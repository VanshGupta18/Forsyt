"""
MD section 1 -- GPR sub-index features, and the market controls they must beat.

Two separate feature blocks, kept separate ON PURPOSE:

  gpr_features()     -- GPRT / GPRA / benchmark GPR, moving averages, spikes
  market_features()  -- trailing realized vol + return momentum (the BASELINE)

They are separate because the only honest test of whether geopolitical risk adds
anything is: does {market + gpr} beat {market alone} out of sample? A model fed
both blocks at once, reporting a single ROC-AUC, cannot answer that -- volatility
clustering alone will carry it. See vol_model.py.

No look-ahead: every feature at date t uses information dated t or earlier. The
target (forward_realized_vol) uses t+1.. only.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from .data import validate_gpr_frame, realized_vol

MA_WINDOWS = (5, 22, 66)          # ~1 week, ~1 month, ~1 quarter of trading days


def gpr_features(gf: pd.DataFrame, ma_windows=MA_WINDOWS) -> pd.DataFrame:
    """Feature matrix from a canonical GPR frame (see data.as_gpr_frame).

    Works with whatever sub-indices are present: if `gpr_threats`/`gpr_acts` are
    missing (as with a bare index), only benchmark features are produced.
    """
    validate_gpr_frame(gf)
    X = pd.DataFrame(index=gf.index)
    present = [c for c in ["gpr", "gpr_threats", "gpr_acts", "gpr_oil"] if c in gf.columns]

    for col in present:
        s = np.log1p(gf[col].astype(float))   # log1p: sub-indices hit exact 0
        short = col.replace("gpr_", "").replace("gpr", "bench")
        X[f"log_{short}"] = s
        for w in ma_windows:
            X[f"{short}_ma{w}"] = s.rolling(w).mean()
        # "crosses a certain threshold": today vs its own recent norm
        X[f"{short}_spike"] = s - s.rolling(ma_windows[1]).mean()
        X[f"{short}_chg1"] = s.diff()
        X[f"{short}_chg5"] = s.diff(5)

    # Threats-vs-Acts balance: is risk anticipated or already realized?
    # (MD section 1 -- GPRT is forward-looking, GPRA is contemporaneous.)
    if {"gpr_threats", "gpr_acts"} <= set(gf.columns):
        X["threats_minus_acts"] = (np.log1p(gf["gpr_threats"].astype(float))
                                   - np.log1p(gf["gpr_acts"].astype(float)))
    return X


def market_features(price: pd.Series, windows=MA_WINDOWS) -> pd.DataFrame:
    """Baseline block: trailing realized vol (HAR components) + return momentum.

    This is what GPR has to beat. `ret_*` exists so the model can learn the MD's
    example -- 'GPRT spikes WHILE the market is already in a downtrend'.
    """
    X = pd.DataFrame(index=price.index)
    lr = np.log(price).diff()
    for w in windows:
        X[f"rv{w}"] = realized_vol(price, w)
        X[f"ret{w}"] = lr.rolling(w).sum() * 100
    # vol momentum: is turbulence building or fading?
    X["rv_ratio"] = X[f"rv{windows[0]}"] / X[f"rv{windows[1]}"]
    # drawdown from 1y high -- 'already in a downtrend'
    X["drawdown"] = (price / price.rolling(252).max() - 1) * 100
    return X


def assemble(gf: pd.DataFrame, price: pd.Series, target: pd.Series):
    """Align GPR features, market features and the target on trading days.

    Returns (X_market, X_gpr, y) so callers can fit market-only vs market+gpr.
    GPR is forward-filled onto trading days -- this is what makes a MONTHLY
    country index usable against daily prices (it becomes a step function), and
    is a no-op for a daily index like Forsyt's.
    """
    Xg = gpr_features(gf).reindex(price.index, method="ffill")
    Xm = market_features(price)
    df = pd.concat([Xm, Xg, target.rename("y")], axis=1).dropna()
    return df[Xm.columns], df[Xg.columns], df["y"]
