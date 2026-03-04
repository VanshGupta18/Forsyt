"""
Market data fetcher using yfinance.
Pulls Nifty 50, INR/USD, and WTI Crude Oil prices.
"""

import yfinance as yf
import pandas as pd
import logging
import datetime
from typing import Optional

logger = logging.getLogger(__name__)

TICKERS = {
    "nifty":  "^NSEI",
    "inrusd": "USDINR=X",
    "crude":  "CL=F",
}

NSE_HOLIDAYS_2025 = [
    datetime.date(2025, 1, 14), datetime.date(2025, 2, 19),
    datetime.date(2025, 3, 14), datetime.date(2025, 3, 31),
    datetime.date(2025, 4, 10), datetime.date(2025, 4, 14),
    datetime.date(2025, 4, 18), datetime.date(2025, 5, 12),
    datetime.date(2025, 6, 7),  datetime.date(2025, 8, 15),
    datetime.date(2025, 8, 27), datetime.date(2025, 10, 2),
    datetime.date(2025, 10, 2), datetime.date(2025, 10, 21),
    datetime.date(2025, 10, 22),datetime.date(2025, 11, 5),
    datetime.date(2025, 12, 25),
]


def fetch_market_data(start_date: str = "2010-01-01",
                      end_date: Optional[str] = None) -> pd.DataFrame:
    """
    Download price data for Nifty, INR/USD, and Crude Oil.
    Returns DataFrame with one row per date (trading days only).
    """
    if end_date is None:
        end_date = datetime.date.today().isoformat()

    logger.info(f"Fetching market data: {start_date} to {end_date}")

    dfs = {}
    for name, ticker in TICKERS.items():
        df = yf.download(ticker, start=start_date, end=end_date,
                         auto_adjust=True, progress=False)
        if df.empty:
            raise ValueError(f"No data returned for {ticker}")
        dfs[name] = df["Close"].rename(name)

    combined = pd.concat(dfs.values(), axis=1)
    combined.index = pd.to_datetime(combined.index).normalize()
    combined.index.name = "date"

    # Forward-fill gaps (holidays, weekends) — max 1 day
    combined = combined.ffill(limit=1).dropna()

    logger.info(f"Market data: {len(combined)} trading days")
    return combined
