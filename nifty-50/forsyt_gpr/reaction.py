"""How markets REACT to geopolitical-risk spikes (explanation, not forecasting).

vol_model.py asks "does GPR improve next-week vol forecasts?" -- it doesn't,
because VIX/oil/INR price the news the same day. This module answers the
project's actual question, "how do markets respond when GPR jumps?", with the
two standard tools:

  event_path()          event study: average cumulative move of each asset from
                        5 days before to 20 days after the largest GPR spikes
                        (relative to the close the day before the spike).
  impulse_responses()   local projections (Jorda 2005): regress the t..t+h move
                        on today's GPR shock, controlling for recent NIFTY
                        returns, realized vol and VIX, with HAC errors. Split
                        into all days vs days when GPR is already elevated.

GPR shock = log GPR minus its own 30-day mean, z-scored: "how unusual is
today's reading vs the last month". Uses the long-history global AI-GPR; the
India index plugs in through the same GPR-frame contract once it has enough
spikes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

# column -> (label, unit). VIX in index points, everything else in % moves.
ASSETS: dict[str, tuple[str, str]] = {
    "NIFTY": ("NIFTY 50", "%"),
    "SP500": ("S&P 500", "%"),
    "BRENT": ("Brent crude", "%"),
    "USDINR": ("USD/INR (up = weaker rupee)", "%"),
    "INDIAVIX": ("India VIX", "pts"),
}
WINDOW = range(-5, 21)
HORIZONS = (1, 5, 20)


def gpr_shock(gpr: pd.Series, window: int = 30) -> pd.Series:
    g = np.log(gpr.where(gpr > 0))
    s = g - g.rolling(window).mean()
    return (s - s.mean()) / s.std()


def spike_days(shock: pd.Series, q: float = 0.99, gap_days: int = 20) -> list[pd.Timestamp]:
    """Top-(1-q) shock days, keeping only the first day of each cluster."""
    hits = shock[shock > shock.quantile(q)].index
    out: list[pd.Timestamp] = []
    for d in hits:
        if not out or (d - out[-1]).days > gap_days:
            out.append(d)
    return out


def _move(prices: pd.DataFrame, col: str, ahead: int, base: int) -> pd.Series:
    """Change from `base` to `ahead` trading days relative to each row."""
    p = prices[col]
    if ASSETS[col][1] == "pts":
        return p.shift(-ahead) - p.shift(-base)
    lp = np.log(p)
    return (lp.shift(-ahead) - lp.shift(-base)) * 100


def event_path(prices: pd.DataFrame, events: list[pd.Timestamp]) -> dict:
    """Mean and interquartile band of each asset's path around the spikes."""
    ev = [d for d in events if d in prices.index]
    series = {}
    for col in prices.columns:
        mean, p25, p75 = [], [], []
        for k in WINDOW:
            v = _move(prices, col, k, -1).reindex(ev).dropna()
            mean.append(round(float(v.mean()), 3) if len(v) else None)
            p25.append(round(float(v.quantile(0.25)), 3) if len(v) else None)
            p75.append(round(float(v.quantile(0.75)), 3) if len(v) else None)
        label, unit = ASSETS[col]
        series[col] = {"label": label, "unit": unit, "mean": mean, "p25": p25, "p75": p75}
    return {"days": list(WINDOW), "series": series}


def impulse_responses(prices: pd.DataFrame, shock: pd.Series, gpr: pd.Series) -> list[dict]:
    nifty_lr = np.log(prices["NIFTY"]).diff()
    ctrl = pd.DataFrame({
        "ret5_lag": nifty_lr.shift(1).rolling(5).sum(),
        "rv22": nifty_lr.rolling(22).std(),
    })
    if "INDIAVIX" in prices:
        ctrl["vix"] = prices["INDIAVIX"]
    elevated = gpr > gpr.rolling(252).quantile(0.8)
    rows = []
    for col in prices.columns:
        for h in HORIZONS:
            y = _move(prices, col, h, 0)
            d = pd.concat([y.rename("y"), shock.rename("shock"), ctrl], axis=1).dropna()
            for regime, keep in (("all", None), ("elevated", elevated)):
                dd = d if keep is None else d[keep.reindex(d.index).fillna(False).astype(bool)]
                if len(dd) < 100:
                    continue
                m = sm.OLS(dd["y"], sm.add_constant(dd.drop(columns="y"))).fit(
                    cov_type="HAC", cov_kwds={"maxlags": h + 5})
                lo, hi = m.conf_int(alpha=0.10).loc["shock"]
                label, unit = ASSETS[col]
                rows.append({
                    "asset": col, "label": label, "unit": unit, "h": h, "regime": regime,
                    "effect": round(float(m.params["shock"]), 3),
                    "ci_low": round(float(lo), 3), "ci_high": round(float(hi), 3),
                    "t": round(float(m.tvalues["shock"]), 2),
                    "significant": bool(lo > 0 or hi < 0), "n": int(len(dd)),
                })
    return rows


def reaction_study(gpr: pd.Series, prices: pd.DataFrame, q: float = 0.99) -> dict:
    """Full payload: spikes, event paths and impulse responses.

    `prices` is indexed by trading day (NIFTY calendar) with columns from ASSETS.
    """
    prices = prices[[c for c in ASSETS if c in prices]]
    g = gpr.reindex(prices.index, method="ffill")
    shock = gpr_shock(g)
    events = spike_days(shock, q)
    return {
        "gpr_as_of": gpr.index.max().strftime("%Y-%m-%d"),
        "threshold_z": round(float(shock.quantile(q)), 2),
        "events": [{"date": d.strftime("%Y-%m-%d"), "shock_z": round(float(shock[d]), 2)} for d in events],
        "path": event_path(prices, events),
        "irf": impulse_responses(prices, shock, g),
    }


def demo() -> None:
    """Self-check on synthetic data: an asset that jumps +2% the day after
    every GPR spike must show that in both the event path and the IRF."""
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2010-01-01", periods=3000)
    gpr = pd.Series(100 * np.exp(rng.normal(0, 0.05, len(idx))), index=idx)
    spikes = idx[300::120]
    gpr[spikes] *= 3.0
    lr = pd.Series(rng.normal(0, 0.005, len(idx)), index=idx)
    after = idx[idx.get_indexer(spikes) + 1]
    lr[after] += 0.02
    nifty = 100 * np.exp(lr.cumsum())
    prices = pd.DataFrame({"NIFTY": nifty, "BRENT": 50 * np.exp(rng.normal(0, 0.01, len(idx)).cumsum())})
    out = reaction_study(gpr, prices, q=0.99)
    assert len(out["events"]) >= 20, out["events"]
    path = out["path"]["series"]["NIFTY"]["mean"]
    day = out["path"]["days"]
    assert abs(path[day.index(-1)]) < 1e-9 and path[day.index(1)] > 1.5, path
    irf = {(r["asset"], r["h"], r["regime"]): r for r in out["irf"]}
    assert irf[("NIFTY", 5, "all")]["significant"] and irf[("NIFTY", 5, "all")]["effect"] > 0
    assert not irf[("BRENT", 5, "all")]["significant"] or abs(irf[("BRENT", 5, "all")]["t"]) < 3
    print("reaction self-check OK")


if __name__ == "__main__":
    demo()
