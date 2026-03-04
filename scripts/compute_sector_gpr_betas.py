"""
Compute OLS GPR β per sector index and persist to sector_gpr_betas.

Beta interpretation: a 1 unit increase in normalised GPR index is associated
with a `gpr_beta` change in the sector's weekly return.

Usage:
    python scripts/compute_sector_gpr_betas.py
Run quarterly via APScheduler (see gpr_index/scheduler.py).
"""

import os
import logging
import psycopg2
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import linregress
from datetime import date

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

PG_DSN = os.getenv("PG_DSN", "postgresql://india_ai:secret@localhost:5432/india_ai_gpr")

# NSE sectoral indices (Yahoo Finance tickers)
SECTOR_INDICES = {
    "Banking":        "^NSEBANK",
    "IT":             "^CNXIT",
    "Pharma":         "^CNXPHARMA",
    "Energy":         "^CNXENERGY",
    "Metal":          "^CNXMETAL",
    "Infrastructure": "^CNXINFRA",
    "Auto":           "^CNXAUTO",
    "FMCG":           "^CNXFMCG",
}


def fetch_gpr_weekly(conn) -> pd.Series:
    """Load weekly mean GPR from DB."""
    df = pd.read_sql("""
        SELECT date_trunc('week', index_date::timestamp) AS week,
               AVG(normalized_gpr) AS gpr
        FROM gpr_index
        WHERE normalized_gpr IS NOT NULL
        GROUP BY 1
        ORDER BY 1
    """, conn)
    df["week"] = pd.to_datetime(df["week"])
    return df.set_index("week")["gpr"]


def fetch_sector_returns(ticker: str, start: str = "2010-01-01") -> pd.Series:
    df = yf.download(ticker, start=start, auto_adjust=True, progress=False)
    if df.empty:
        return pd.Series(dtype=float)
    weekly = df["Close"].resample("W").last()
    return weekly.pct_change().dropna()


def compute_beta(gpr: pd.Series, returns: pd.Series):
    """OLS regression of returns ~ GPR. Returns (beta, r_squared, n_obs)."""
    common = gpr.index.intersection(returns.index)
    if len(common) < 52:
        return None, None, 0
    x = gpr.loc[common].values
    y = returns.loc[common].values
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]
    if len(x) < 52:
        return None, None, 0
    slope, intercept, r, p, se = linregress(x, y)
    return float(slope), float(r ** 2), len(x)


def run():
    conn = psycopg2.connect(PG_DSN)
    gpr  = fetch_gpr_weekly(conn)
    today = date.today()

    with conn.cursor() as cur:
        for sector, ticker in SECTOR_INDICES.items():
            logger.info(f"Computing beta for {sector} ({ticker})")
            returns = fetch_sector_returns(ticker)
            beta, r2, n = compute_beta(gpr, returns)
            if beta is None:
                logger.warning(f"  Insufficient data for {sector} (n={n})")
                continue
            logger.info(f"  β={beta:.4f}  R²={r2:.4f}  n={n}")
            cur.execute("""
                INSERT INTO sector_gpr_betas
                    (sector, gpr_beta, r_squared, n_obs, computed_date)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (sector, computed_date)
                DO UPDATE SET gpr_beta=EXCLUDED.gpr_beta,
                              r_squared=EXCLUDED.r_squared,
                              n_obs=EXCLUDED.n_obs
            """, (sector, beta, r2, n, today))
    conn.commit()
    conn.close()
    logger.info("Sector GPR betas computed and saved.")


if __name__ == "__main__":
    run()
