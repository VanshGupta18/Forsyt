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

BEGINNER NOTE -- "features" and why the split matters
-------------------------------------------------------
A "feature" is just a number that describes the situation on a given day,
which a machine-learning model is allowed to look at when making a
prediction. This file's whole job is to turn two raw time series (a GPR risk
index, and a stock price) into a table of such numbers, one row per trading
day.

Why not just throw ALL the numbers (GPR-related AND market-related) at the
model together and see what ROC-AUC comes out? Because stock market
volatility is famously "sticky" -- a turbulent week is usually followed by
another turbulent week, entirely on its own, with no geopolitics required.
A model given both blocks together will happily use that stickiness to score
well, and a tool like SHAP will still credit some of that success to the GPR
features (because they move up and down together with the turbulence, even
if they're not causing it) -- see the SHAP warning in vol_model.py. The only
way to find out whether GPR is actually adding anything is to build the
"market alone" model and the "market + GPR" model on the exact same rows and
compare their out-of-sample scores. That comparison is impossible unless the
two feature blocks are kept as two separate tables, which is exactly what
`gpr_features()` and `market_features()` return.
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

    Plain-language summary of what gets built, per available column
    (`gpr` = the benchmark index itself, plus `gpr_threats`/`gpr_acts`/
    `gpr_oil` when present):

      * `log_<name>`       -- the risk level itself, log-transformed (see
                              log1p note below). This is "how risky is today,
                              on its own".
      * `<name>_ma{5,22,66}` -- moving averages: the AVERAGE risk level over
                              the last 5 / 22 / 66 trading days (roughly one
                              week / one month / one quarter). These smooth
                              out day-to-day noise to show the underlying
                              trend.
      * `<name>_spike`     -- how far ABOVE (positive) or BELOW (negative)
                              its own one-month average today's level is.
                              A large positive value means "risk just spiked
                              relative to what's been normal recently" --
                              this is the closest thing to a literal
                              "crosses a threshold" alarm, but relative to
                              the series' own recent history rather than a
                              fixed number.
      * `<name>_chg1`, `<name>_chg5` -- how much the (logged) risk level
                              changed over the last 1 day / 5 days. Answers
                              "is it moving right now, and how fast".
      * `threats_minus_acts` -- only built if both GPRT (anticipated
                              conflict -- risk that HASN'T happened yet, just
                              threatened) and GPRA (realized/acted-upon
                              conflict) are available. A positive value means
                              the news flow is currently more about threats
                              than about things that already happened --
                              i.e. "risk is being anticipated, not yet
                              realized".
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

    Plain-language summary of each column:

      * `rv{5,22,66}`   -- trailing realized volatility (see
                          `data.realized_vol`) over the last week / month /
                          quarter. "HAR" (Heterogeneous AutoRegressive) is
                          just the name for this common trick of using
                          several different rolling-volatility windows
                          together, because market turbulence has memory at
                          more than one timescale at once.
      * `ret{5,22,66}`  -- the total percentage price return over the same
                          three windows: not how JUMPY the market was, but
                          which DIRECTION it moved and how far.
      * `rv_ratio`      -- short-term vol divided by longer-term vol. Above 1
                          means "things have gotten choppier recently than
                          they were on average this quarter" (turbulence
                          building); below 1 means calming down.
      * `drawdown`      -- how far (in %) the price currently sits below its
                          own highest close in the last 252 trading days
                          (roughly one year). A large negative number means
                          "already well off its highs" -- i.e. already in a
                          downtrend, the condition the module docstring
                          refers to.
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

    Why this needs its own function: GPR data and price data don't
    necessarily share the same calendar (e.g. a monthly GPR release vs.
    daily NIFTY closes, or simply missing days on one side). "Forward-fill"
    (`method="ffill"`) means: on any trading day that doesn't have a fresh
    GPR reading, just reuse the most recent one that IS known -- this is
    always safe (never uses future information) and turns a monthly series
    into a "step function" that stays flat between releases. `.dropna()` at
    the end then throws away any row where either block, or the target,
    still has a gap (e.g. the very first `66` days of history, before the
    longest moving average has enough data to compute) -- so every row
    returned is guaranteed complete and comparable across `X_market` and
    `X_gpr`.
    """
    Xg = gpr_features(gf).reindex(price.index, method="ffill")
    Xm = market_features(price)
    df = pd.concat([Xm, Xg, target.rename("y")], axis=1).dropna()
    return df[Xm.columns], df[Xg.columns], df["y"]
