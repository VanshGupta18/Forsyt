"""Split-era normalization when GDELT warmup precedes India news scoring."""

from __future__ import annotations

from datetime import date

import pandas as pd

from .paths import INDIA_GPR_INDEX_START


def product_start_date() -> date:
    return INDIA_GPR_INDEX_START


def should_split_era(daily_df: pd.DataFrame, baseline_start: str) -> bool:
    """Use separate scales for warmup (GKG) vs product (India news) eras."""
    del baseline_start  # split when both eras exist in the batch being normalized
    dates = pd.to_datetime(daily_df["date"])
    has_warmup = (dates < pd.Timestamp(INDIA_GPR_INDEX_START)).any()
    has_product = (dates >= pd.Timestamp(INDIA_GPR_INDEX_START)).any()
    return bool(has_warmup and has_product)


def rolling_product_era(
    df: pd.DataFrame,
    value_col: str,
    window: int,
    *,
    product_start: str = INDIA_GPR_INDEX_START,
) -> pd.Series:
    """Rolling mean computed only over rows on/after product_start."""
    product_start_ts = pd.Timestamp(product_start)
    out = pd.Series(index=df.index, dtype=float)
    product = df[df["date"] >= product_start_ts].sort_values("date")
    if product.empty:
        return out
    rolled = product[value_col].rolling(window, min_periods=1).mean()
    out.loc[rolled.index] = rolled.values
    return out


def rolling_product_era_grouped(
    df: pd.DataFrame,
    group_col: str,
    value_col: str,
    window: int,
    *,
    product_start: str = INDIA_GPR_INDEX_START,
) -> pd.Series:
    """Per-group rolling mean over the product era only."""
    out = pd.Series(index=df.index, dtype=float)
    for _, group in df.groupby(group_col, sort=False):
        sorted_group = group.sort_values("date")
        rolled = rolling_product_era(
            sorted_group, value_col, window, product_start=product_start
        )
        out.loc[sorted_group.index] = rolled.values
    return out
