"""
MD section A -- "spikes in the GPR index systematically foreshadow declines in
aggregate corporate investment and national employment rates" (VAR + impulse
response functions).

Implements the Caldara & Iacoviello (2022) design: a recursive monthly VAR with
GPR ordered FIRST (so its reduced-form innovation is the structural shock -- the
standard assumption that geopolitical events are not caused within-month by US
investment or payrolls), then impulse responses to a one-s.d. GPR shock.

Investment proxy: FRED NEWORDER (new orders, nondefense capital goods ex
aircraft) -- the standard MONTHLY capex proxy. Actual gross private investment
(GPDI) is quarterly and cannot enter a monthly VAR without interpolation.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from statsmodels.tsa.api import VAR


def to_monthly(gf: pd.DataFrame) -> pd.Series:
    """Month-average the benchmark GPR (works for daily or already-monthly)."""
    s = gf["gpr"].resample("MS").mean()
    return np.log1p(s.dropna()).rename("logGPR")


def run_macro_var(gf: pd.DataFrame, macro: dict, lags: int | None = None,
                  horizon: int = 24, start: str = "1992-01-01", signif: float = 0.10,
                  repl: int = 400, seed: int = 1):
    """Recursive VAR of [logGPR, *macro] with GPR ordered first.

    `macro` maps display name -> monthly series ALREADY in the units you want
    plotted (e.g. growth rates in %). Returns (irf_df, lower, upper, results).
    """
    df = pd.concat([to_monthly(gf)] + [s.rename(k) for k, s in macro.items()],
                   axis=1).dropna()
    df = df.loc[start:]
    order = ["logGPR"] + list(macro)
    model = VAR(df[order])
    if lags is None:
        lags = int(max(2, min(model.select_order(12).selected_orders["aic"], 6)))
    res = model.fit(lags)

    irf = res.irf(horizon)
    resp = irf.orth_irfs[:, :, 0]                       # 1 s.d. shock to logGPR
    lo, hi = irf.errband_mc(orth=True, repl=repl, signif=signif, seed=seed)
    irf_df = pd.DataFrame(resp, columns=order)
    irf_df.index.name = "horizon_months"
    return (irf_df, pd.DataFrame(lo[:, :, 0], columns=order),
            pd.DataFrame(hi[:, :, 0], columns=order), res)


def summarize(irf_df: pd.DataFrame) -> pd.DataFrame:
    """Peak/trough response of each variable to the GPR shock."""
    rows = []
    for c in irf_df.columns:
        if c == "logGPR":
            continue
        v = irf_df[c]
        rows.append({"variable": c, "trough": v.min(), "trough_month": int(v.idxmin()),
                     "peak": v.max(), "peak_month": int(v.idxmax()),
                     "cumulative_24m": v.cumsum().iloc[-1]})
    return pd.DataFrame(rows).set_index("variable")
