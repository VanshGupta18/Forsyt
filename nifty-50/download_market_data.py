"""Download the price series the sector-beta fit needs into nifty-50/data/.

WHAT: NIFTY sector indices (IT, Bank, Energy, Auto, Pharma, FMCG, Metal, Realty,
Financial Services, Infra), Brent crude, and USD/INR — daily closes, max history.

WHY: `fit_sector_betas.py` regresses each sector's returns on oil-price and
geopolitical-risk shocks; those sector/Brent/INR histories don't ship in the
repo (only headline NIFTY.csv does). This is the sibling of `download_data.py`
(which fetches the Caldara GPR benchmark) — re-run it to refresh `data/`.

CAVEAT: Yahoo's NSE sector-index history is uneven — some indices start years
after 2007, and a symbol may occasionally return nothing. Whatever resolves is
written; the fit script simply uses the sectors it finds.
"""
from __future__ import annotations

import os

import pandas as pd
import yfinance as yf

# outfile key (data/<key>.csv) -> Yahoo symbol
TICKERS: dict[str, str] = {
    "sector_IT": "^CNXIT",
    "sector_BANK": "^NSEBANK",
    "sector_ENERGY": "^CNXENERGY",
    "sector_AUTO": "^CNXAUTO",
    "sector_PHARMA": "^CNXPHARMA",
    "sector_FMCG": "^CNXFMCG",
    "sector_METAL": "^CNXMETAL",
    "sector_REALTY": "^CNXREALTY",
    "sector_FIN": "^CNXFIN",
    "sector_INFRA": "^CNXINFRA",
    "BRENT": "BZ=F",
    "USDINR": "INR=X",
}
ALT = {"BRENT": "CL=F"}

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _history(symbol: str) -> pd.DataFrame:
    return yf.Ticker(symbol).history(period="max", auto_adjust=False)


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    ok, missing = [], []
    for key, symbol in TICKERS.items():
        try:
            hist = _history(symbol)
            if hist.empty and key in ALT:
                symbol = ALT[key]
                hist = _history(symbol)
            if hist.empty or "Close" not in hist:
                missing.append(key)
                print(f"[SKIP] {key} ({symbol}) — no data")
                continue
            out = pd.DataFrame({
                "Date": pd.to_datetime(hist.index).tz_localize(None).strftime("%Y-%m-%d"),
                "Close": hist["Close"].round(4).values,
            }).dropna()
            path = os.path.join(DATA_DIR, f"{key}.csv")
            out.to_csv(path, index=False)
            ok.append(key)
            print(f"[OK]   {key} ({symbol}) — {len(out):,} rows, {out['Date'].iloc[0]}..{out['Date'].iloc[-1]}")
        except Exception as exc:
            missing.append(key)
            print(f"[FAIL] {key} ({symbol}) — {exc}")
    print(f"\nDone. {len(ok)} written, {len(missing)} missing: {missing}")


if __name__ == "__main__":
    main()
