"""Split-era normalization when GDELT warmup precedes India news scoring.

WHY THIS FILE EXISTS (read this before touching normalize_index/normalize_corridor_index):
The GPR index is always rescaled so its baseline period averages to 100 (see
gkg_gpr_pipeline.py's normalize_index()). That rescaling needs a "baseline
mean" (S-bar) to divide by. The problem: this project scores two very
different news sources on the same 0-100 scale.
  - GDELT warmup era:  ~15,000-30,000 articles/day (all global news)
  - India product era: ~200-400 articles/day (one country's news only)
A day with 30,000 articles will naturally have a much bigger raw score sum
than a day with 300 articles, even if both days are equally "risky" in
relative terms. If both eras were averaged into ONE shared baseline, that
baseline would be dominated by the high-volume GDELT days, and every India-era
day would then divide out to a tiny number (roughly 1-2) instead of the
intended ~100. should_split_era() detects when a batch spans both eras so the
pipeline can compute a separate baseline for each one instead.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from .paths import INDIA_GPR_INDEX_START


def product_start_date() -> date:
    return INDIA_GPR_INDEX_START


def should_split_era(daily_df: pd.DataFrame, baseline_start: str) -> bool:
    """Use separate scales for warmup (GKG) vs product (India news) eras."""
    del baseline_start  # split when both eras exist in the batch being normalized
    # "Is there at least one row before the cutover AND at least one on/after it?"
    # If the batch is entirely one era or the other, a single shared baseline is
    # fine and no splitting is needed.
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
    """Rolling mean computed only over rows on/after product_start.

    Used for the 7-day/30-day moving averages (gpr_7ma, gpr_30ma). Without
    this restriction, the very first India-era days would average themselves
    together with the last few (much bigger-scale) warmup days, producing a
    misleading spike or dip right at the Aug-8/Aug-9 boundary.
    """
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
