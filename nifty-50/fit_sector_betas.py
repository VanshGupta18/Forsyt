"""Estimate sector geopolitical-risk betas from long price history.

WHY: `news_dataset/api/portfolio_service.py` maps each holding's GICS sector to
loadings on risk channels. Those loadings were hand-set priors. This script
replaces them with **fitted, significance-tested coefficients** and writes them
to `output/sector_factors.json`, which the service loads at runtime.

METHOD (per the "benchmark now, India index plugs in later" pattern):
  * Sector return series = equal-weight weekly log returns of a basket of liquid
    large caps, keyed by the SAME GICS sectors the portfolio uses (baskets below
    mirror portfolio_service._SECTOR_SEED). Constituents have decades of history;
    Yahoo's NSE sector *indices* mostly don't.
  * Regressors (weekly shocks): broad geopolitical risk = Caldara global GPR
    (GPR_AI), oil = Brent return, fx = USD/INR return. India-native gpr_oil is
    too short to train on, so we train on Brent (India imports ~85% of crude —
    directly relevant) and feed the native gpr_oil in only at inference.
  * For each sector: OLS with Newey-West/HAC standard errors (statsmodels).
  * risk loading = -beta (a sector hurt by an adverse channel move has a negative
    return-beta -> a positive risk loading), scaled to a comparable range.
    Insignificant coefficients (p > 0.10) are set to 0 — honest "no evidence",
    not a hardcoded guess. Expect several to be insignificant (the repo's own
    finding is GPR adds little to Indian market vol).

Run:  python nifty-50/fit_sector_betas.py
Out:  output/tables/sector_betas.csv  (full stats)
      output/sector_factors.json      (loadings the service consumes)
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import statsmodels.api as sm
import yfinance as yf

HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "data")
CALDARA_CSV = os.path.join(DATA_DIR, "ai_gpr_data_daily.csv")
BRENT_CSV = os.path.join(DATA_DIR, "BRENT.csv")
USDINR_CSV = os.path.join(DATA_DIR, "USDINR.csv")
OUT_TABLE = os.path.join(HERE, "output", "tables", "sector_betas.csv")
OUT_JSON = os.path.join(HERE, "output", "sector_factors.json")

# GICS sector -> liquid constituents (yahoo .NS). Mirrors portfolio_service._SECTOR_SEED.
BASKETS: dict[str, list[str]] = {
    "Energy": ["RELIANCE.NS", "ONGC.NS", "BPCL.NS", "IOC.NS"],
    "Technology": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS"],
    "Financial Services": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS"],
    "Consumer Cyclical": ["MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "TITAN.NS"],
    "Consumer Defensive": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS"],
    "Healthcare": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS"],
    "Basic Materials": ["TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS"],
    "Utilities": ["NTPC.NS", "POWERGRID.NS"],
    "Industrials": ["LT.NS"],
    "Communication Services": ["BHARTIARTL.NS"],
}
# regression regressor -> portfolio_service channel name
CHANNELS = {"gpr_shock": "broad", "oil_shock": "energy", "fx_shock": "fx"}
SIG_P = 0.10  # significance threshold; above this -> loading 0


def _weekly_logret(price: pd.Series) -> pd.Series:
    w = price.resample("W-FRI").last()
    return np.log(w).diff()


def _basket_weekly_return(tickers: list[str]) -> pd.Series:
    frames = []
    for t in tickers:
        try:
            h = yf.Ticker(t).history(period="max", auto_adjust=True)
        except Exception as exc:
            print(f"    [skip] {t}: {exc}")
            continue
        if h.empty or "Close" not in h:
            print(f"    [skip] {t}: no data")
            continue
        s = h["Close"].copy()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        frames.append(_weekly_logret(s).rename(t))
    if not frames:
        return pd.Series(dtype=float)
    return pd.concat(frames, axis=1).mean(axis=1)  # equal-weight basket


def _load_regressors() -> pd.DataFrame:
    cal = pd.read_csv(CALDARA_CSV, usecols=["Date", "GPR_AI"])
    cal["date"] = pd.to_datetime(cal["Date"], errors="coerce")
    cal = cal.dropna(subset=["date"]).set_index("date")["GPR_AI"]
    gpr_shock = np.log1p(cal).resample("W-FRI").last().diff().rename("gpr_shock")

    def _price_ret(path, name):
        raw = pd.read_csv(path)
        s = pd.Series(
            pd.to_numeric(raw.iloc[:, 1], errors="coerce").values,
            index=pd.to_datetime(raw.iloc[:, 0], errors="coerce"),
        ).dropna()
        return _weekly_logret(s).rename(name)

    oil_shock = _price_ret(BRENT_CSV, "oil_shock")
    fx_shock = _price_ret(USDINR_CSV, "fx_shock")
    return pd.concat([gpr_shock, oil_shock, fx_shock], axis=1).dropna()


def fit() -> tuple[pd.DataFrame, dict]:
    X = _load_regressors()
    stats_rows: list[dict] = []
    factors: dict[str, dict] = {}
    raw_loadings: dict[tuple[str, str], float] = {}

    for sector, tickers in BASKETS.items():
        print(f"[fit] {sector}")
        y = _basket_weekly_return(tickers)
        if y.empty:
            continue
        df = pd.concat([y.rename("ret"), X], axis=1).dropna()
        if len(df) < 60:
            print(f"    too few weeks ({len(df)}) — skipped")
            continue
        # Standardize regressors (z-score) so betas are "response per 1 SD shock"
        # and are comparable across channels (fx moves are far larger in raw
        # log-units than GPR moves; without this the scaling below would crush
        # the smaller-variance channels to ~0).
        Z = (df[list(CHANNELS)] - df[list(CHANNELS)].mean()) / df[list(CHANNELS)].std()
        Xm = sm.add_constant(Z)
        model = sm.OLS(df["ret"], Xm).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
        for reg, channel in CHANNELS.items():
            beta, t, p = model.params[reg], model.tvalues[reg], model.pvalues[reg]
            stats_rows.append({
                "sector": sector, "channel": channel, "beta": round(beta, 5),
                "t_stat": round(t, 2), "p_value": round(p, 4),
                "r2": round(model.rsquared, 4), "n_weeks": len(df),
                "significant": bool(p < SIG_P),
            })
            # risk loading = -beta (hurt by adverse move => positive risk); 0 if insignificant
            raw_loadings[(sector, channel)] = (-beta) if p < SIG_P else 0.0

    # scale loadings to a comparable range (max |loading| -> 1.0), preserve sign
    peak = max((abs(v) for v in raw_loadings.values()), default=0.0)
    scale = (1.0 / peak) if peak > 0 else 0.0
    for (sector, channel), v in raw_loadings.items():
        factors.setdefault(sector, {})[channel] = round(v * scale, 4)

    return pd.DataFrame(stats_rows), factors


def main() -> None:
    table, factors = fit()
    os.makedirs(os.path.dirname(OUT_TABLE), exist_ok=True)
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    table.to_csv(OUT_TABLE, index=False)
    with open(OUT_JSON, "w") as f:
        json.dump(factors, f, indent=2)
    print(f"\n[done] {OUT_TABLE}\n[done] {OUT_JSON}")
    if not table.empty:
        sig = table[table["significant"]]
        print(f"\nSignificant channels ({len(sig)}/{len(table)}):")
        print(sig.to_string(index=False) if not sig.empty else "  (none)")


if __name__ == "__main__":
    main()
