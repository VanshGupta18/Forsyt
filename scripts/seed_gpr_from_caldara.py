"""
Seed historical GPR index from Caldara & Iacoviello (2022) dataset.
Downloads the official Excel file, extracts the India GPR column,
normalises to match our Z-score format, and inserts into gpr_index.

Usage:
    python scripts/seed_gpr_from_caldara.py
"""

import os
import io
import logging
import requests
import pandas as pd
import psycopg2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

PG_DSN = os.getenv("PG_DSN", "postgresql://india_ai:secret@localhost:5432/india_ai_gpr")

# Official Caldara & Iacoviello dataset (country-level monthly GPR)
CALDARA_URL = (
    "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls"
)


def download_caldara() -> pd.DataFrame:
    logger.info(f"Downloading Caldara dataset from {CALDARA_URL}")
    resp = requests.get(CALDARA_URL, timeout=60)
    resp.raise_for_status()
    df = pd.read_excel(io.BytesIO(resp.content))
    logger.info(f"Downloaded: {df.shape[0]} rows, columns: {list(df.columns[:10])} ...")
    return df


def extract_india_column(df: pd.DataFrame) -> pd.Series:
    """
    The country GPR file has a 'IGPR' or 'GPR_India' column.
    Try multiple name variants for robustness.
    """
    candidates = ["IGPR", "GPR_India", "India", "INDIAgpr", "india_gpr"]
    for col in candidates:
        if col in df.columns:
            logger.info(f"Using column: {col}")
            return df[col].copy()
    raise KeyError(
        f"India GPR column not found. Available: {list(df.columns)}"
    )


def normalize_series(series: pd.Series, window: int = 252) -> pd.Series:
    """Apply rolling Z-score normalisation (same formula as our live pipeline)."""
    mean = series.rolling(window, min_periods=126).mean()
    std  = series.rolling(window, min_periods=126).std()
    return (series - mean) / std.replace(0, np.nan)


def insert_seeded_data(daily_series: pd.Series, conn):
    inserted = 0
    with conn.cursor() as cur:
        for dt, val in daily_series.items():
            if pd.isna(val):
                continue
            cur.execute("""
                INSERT INTO gpr_index
                    (index_date, raw_gpr, smoothed_gpr, normalized_gpr,
                     event_count, data_quality_flag, created_at)
                VALUES (%s, %s, %s, %s, 0, 'SEEDED_CALDARA', NOW())
                ON CONFLICT (index_date) DO NOTHING
            """, (dt.date(), float(val), float(val), float(val)))
            inserted += cur.rowcount
    conn.commit()
    logger.info(f"Inserted {inserted} historical GPR rows")


def main():
    df = download_caldara()

    # Find the date column
    date_col = next((c for c in df.columns
                     if any(k in str(c).lower() for k in ["date", "month", "year"])), None)
    if date_col is None:
        date_col = df.columns[0]
    logger.info(f"Date column: {date_col}")

    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col)

    india_raw = extract_india_column(df)

    # Normalise monthly → expand to daily (forward-fill within each month)
    monthly = india_raw.dropna()
    monthly.index = pd.to_datetime(monthly.index)
    norm = normalize_series(monthly)

    # Forward-fill to daily frequency
    daily_idx = pd.date_range(norm.index.min(), norm.index.max(), freq="D")
    daily = norm.reindex(daily_idx).ffill()

    conn = psycopg2.connect(PG_DSN)
    insert_seeded_data(daily, conn)
    conn.close()
    logger.info("Caldara seeding complete.")


if __name__ == "__main__":
    main()
