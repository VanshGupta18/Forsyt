"""
Point-in-time safe feature engineering for the ML volatility model.

All features at date t use only data available before market open on day t.
"""

import pandas as pd
import numpy as np
import psycopg2
import logging
from datetime import date

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "india_ai_gpr_t1", "india_ai_gpr_t3", "india_ai_gpr_t7",
    "gpr_shock_flag", "gpr_rolling_mean_7",
    "inr_usd_return", "crude_oil_return",
    "nifty_return_t1", "nifty_return_t5", "nifty_vol_lag1",
]


def load_gpr_series(conn: psycopg2.extensions.connection,
                    start_date: str = "2010-01-01") -> pd.Series:
    """Load daily GPR index from PostgreSQL."""
    df = pd.read_sql(
        "SELECT index_date, normalized_gpr FROM gpr_index "
        "WHERE index_date >= %s AND normalized_gpr IS NOT NULL ORDER BY index_date",
        conn, params=(start_date,)
    )
    df["index_date"] = pd.to_datetime(df["index_date"])
    return df.set_index("index_date")["normalized_gpr"]


def build_feature_matrix(gpr_series: pd.Series,
                          market_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build 10-feature matrix aligned on trading dates.
    Every feature at t uses only data from t-1 or earlier.
    """
    returns = _compute_returns(market_df)
    all_dates = sorted(gpr_series.index.intersection(returns.index))
    features = pd.DataFrame(index=all_dates)

    # GPR features - all shifted by 1 to use t-1 data at prediction time
    features["india_ai_gpr_t1"]     = gpr_series.reindex(features.index).shift(1)
    features["india_ai_gpr_t3"]     = gpr_series.reindex(features.index).shift(3)
    features["india_ai_gpr_t7"]     = gpr_series.reindex(features.index).shift(7)
    features["gpr_rolling_mean_7"]  = (
        gpr_series.rolling(7).mean().reindex(features.index).shift(1)
    )

    # GPR shock flag: 1 if GPR[t-1] > rolling_mean + 2σ
    gpr_mean = gpr_series.rolling(252).mean()
    gpr_std  = gpr_series.rolling(252).std()
    features["gpr_shock_flag"] = (
        (gpr_series >= gpr_mean + 2 * gpr_std)
        .astype(int).reindex(features.index).shift(1)
    )

    # Market features
    features["inr_usd_return"]   = returns["inrusd_return"].reindex(features.index).shift(1)
    features["crude_oil_return"] = returns["crude_return"].reindex(features.index).shift(1)
    features["nifty_return_t1"]  = returns["nifty_return"].reindex(features.index).shift(1)
    features["nifty_return_t5"]  = returns["nifty_return"].reindex(features.index).shift(5)

    # Realized volatility: std of returns over t-11 to t-1 (10 days, shifted to avoid lookahead)
    features["nifty_vol_lag1"] = (
        returns["nifty_return"]
        .reindex(features.index)
        .shift(1)
        .rolling(10)
        .std()
    )

    logger.info(
        f"Feature matrix: {len(features)} rows × {len(features.columns)} features | "
        f"{features.index[0].date() if len(features) else 'N/A'} to "
        f"{features.index[-1].date() if len(features) else 'N/A'}"
    )
    return features


def build_target_variable(market_df: pd.DataFrame,
                           train_end_date: str = "2022-12-31"):
    """
    Binary label: HIGH_VOL (1) if 10-day realized vol > 75th percentile of train set.
    Threshold computed on training set ONLY (no data leakage).
    """
    returns = _compute_returns(market_df)
    rolling_vol = returns["nifty_return"].rolling(10).std()

    train_mask = rolling_vol.index <= pd.Timestamp(train_end_date)
    threshold  = float(np.percentile(rolling_vol[train_mask].dropna(), 75))

    labels = (rolling_vol > threshold).astype(int)
    labels.name = "label"

    logger.info(
        f"Target variable: threshold={threshold:.6f} "
        f"(75th pct of train) | class balance={labels.mean():.1%} HIGH_VOL"
    )
    return labels, threshold


def _compute_returns(market_df: pd.DataFrame) -> pd.DataFrame:
    returns = pd.DataFrame(index=market_df.index)
    for col in market_df.columns:
        returns[f"{col}_return"] = market_df[col].pct_change()
    return returns.dropna()
