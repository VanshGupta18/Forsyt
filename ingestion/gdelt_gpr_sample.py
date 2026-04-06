"""Small-sample GDELT → GPR test pipeline.

This module provides a simple, pandas-based pipeline to:
- Load a GDELT Events CSV
- Filter conflict-related events
- Deduplicate events at a daily / dyad / event-code level
- Compute risk scores and event risk
- Optionally focus on India-related events
- Aggregate daily risk into a basic GPR measure

It is intentionally small and focused on correctness for experimentation,
not production-scale performance.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd

# GDELT column names we expect. We use names (not positions) for flexibility.
SQLDATE_COL = "SQLDATE"
ACTOR1_COUNTRY_COL = "Actor1CountryCode"
ACTOR2_COUNTRY_COL = "Actor2CountryCode"
ACTOR1_GEO_COUNTRY_COL = "Actor1Geo_CountryCode"
ACTOR2_GEO_COUNTRY_COL = "Actor2Geo_CountryCode"
ACTION_GEO_COUNTRY_COL = "ActionGeo_CountryCode"
EVENT_CODE_COL = "EventCode"
NUM_MENTIONS_COL = "NumMentions"
GOLDSTEIN_COL = "GoldsteinScale"

# Event codes starting with these prefixes are treated as conflict-related.
CONFLICT_EVENT_PREFIXES = ("13", "14", "15", "16", "17", "18", "19", "20")

# Country code variants we may see across actor and geo fields.
INDIA_CODES = {"IND", "IN"}

# Event-code prefix severity weights (higher = more severe geopolitical risk).
EVENT_PREFIX_WEIGHTS = {
    "13": 0.70,  # Threaten / posture
    "14": 0.80,  # Protest
    "15": 0.90,  # Exhibit force posture
    "16": 1.00,  # Reduce relations / coercive pressure
    "17": 1.10,  # Coerce
    "18": 1.20,  # Assault
    "19": 1.30,  # Fight
    "20": 1.40,  # Use unconventional mass violence
}


def load_gdelt_events(csv_path: str, nrows: Optional[int] = None) -> pd.DataFrame:
    """Load a GDELT Events CSV using column names (not positions).

    Parameters
    ----------
    csv_path : str
        Path to the GDELT events CSV file.
    nrows : Optional[int]
        Optionally limit number of rows read (for quick experiments).

    Returns
    -------
    pd.DataFrame
        Raw events dataframe.
    """
    # First, try to read as a regular CSV with a header row. This covers
    # small sample files like `gdelt_events_sample.csv` used for testing.
    try:
        df = pd.read_csv(csv_path, nrows=nrows, low_memory=False)
    except Exception:
        # Fallback for official GDELT daily event files, which are
        # tab-separated and do not include a header row.
        df = _load_official_gdelt_events(csv_path, nrows=nrows)

    # If the key columns like SQLDATE are still missing and the path looks
    # like an official GDELT export (".CSV"), fall back to the official
    # schema loader as well.
    if SQLDATE_COL not in df.columns and csv_path.upper().endswith(".CSV"):
        df = _load_official_gdelt_events(csv_path, nrows=nrows)

    return df


def _load_official_gdelt_events(csv_path: str, nrows: Optional[int] = None) -> pd.DataFrame:
    """Load a raw GDELT 2.0 daily Events export.

    These files are tab-separated with no header row. We apply the official
    column schema so that downstream code can use named columns like
    SQLDATE, Actor1CountryCode, Actor2CountryCode, EventCode, NumMentions,
    GoldsteinScale, etc.
    """
    colnames = [
        "GLOBALEVENTID",
        "SQLDATE",
        "MonthYear",
        "Year",
        "FractionDate",
        "Actor1Code",
        "Actor1Name",
        "Actor1CountryCode",
        "Actor1KnownGroupCode",
        "Actor1EthnicCode",
        "Actor1Religion1Code",
        "Actor1Religion2Code",
        "Actor1Type1Code",
        "Actor1Type2Code",
        "Actor1Type3Code",
        "Actor2Code",
        "Actor2Name",
        "Actor2CountryCode",
        "Actor2KnownGroupCode",
        "Actor2EthnicCode",
        "Actor2Religion1Code",
        "Actor2Religion2Code",
        "Actor2Type1Code",
        "Actor2Type2Code",
        "Actor2Type3Code",
        "IsRootEvent",
        "EventCode",
        "EventBaseCode",
        "EventRootCode",
        "QuadClass",
        "GoldsteinScale",
        "NumMentions",
        "NumSources",
        "NumArticles",
        "AvgTone",
        "Actor1Geo_Type",
        "Actor1Geo_FullName",
        "Actor1Geo_CountryCode",
        "Actor1Geo_ADM1Code",
        "Actor1Geo_Lat",
        "Actor1Geo_Long",
        "Actor1Geo_FeatureID",
        "Actor2Geo_Type",
        "Actor2Geo_FullName",
        "Actor2Geo_CountryCode",
        "Actor2Geo_ADM1Code",
        "Actor2Geo_Lat",
        "Actor2Geo_Long",
        "Actor2Geo_FeatureID",
        "ActionGeo_Type",
        "ActionGeo_FullName",
        "ActionGeo_CountryCode",
        "ActionGeo_ADM1Code",
        "ActionGeo_Lat",
        "ActionGeo_Long",
        "ActionGeo_FeatureID",
        "DATEADDED",
        "SOURCEURL",
    ]

    return pd.read_csv(
        csv_path,
        sep="\t",
        header=None,
        names=colnames,
        nrows=nrows,
        low_memory=False,
    )


def filter_conflict_events(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows where the event appears conflict-related.

    Specifically, we keep rows where EventCode starts with one of:
    13, 14, 15, 16, 17, 18, 19, 20.
    Missing or non-string EventCode values are safely handled by casting to str.
    """
    if EVENT_CODE_COL not in df.columns:
        # If EventCode is missing entirely, nothing to filter; return empty.
        return df.iloc[0:0].copy()

    codes = df[EVENT_CODE_COL].astype(str).fillna("")
    mask = codes.str.startswith(CONFLICT_EVENT_PREFIXES)
    return df.loc[mask].copy()


def deduplicate_events(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate events at a daily dyad-event level.

    Group by the combination of:
    - SQLDATE
    - Actor1CountryCode
    - Actor2CountryCode
    - EventCode

    and aggregate:
    - NumMentions → sum
    - GoldsteinScale → mean

    Any missing numeric values are coerced to 0 for NumMentions and 0.0 for
    GoldsteinScale before aggregation to avoid NaNs propagating unexpectedly.
    """
    group_cols = [SQLDATE_COL, ACTOR1_COUNTRY_COL, ACTOR2_COUNTRY_COL, EVENT_CODE_COL]

    # Ensure grouping columns exist; if not, add them as all-NaN so groupby still works.
    for col in group_cols:
        if col not in df.columns:
            df[col] = pd.NA

    # Ensure numeric columns exist.
    if NUM_MENTIONS_COL not in df.columns:
        df[NUM_MENTIONS_COL] = 0
    if GOLDSTEIN_COL not in df.columns:
        df[GOLDSTEIN_COL] = 0.0

    # Coerce to numeric and handle missing values safely.
    df[NUM_MENTIONS_COL] = (
        pd.to_numeric(df[NUM_MENTIONS_COL], errors="coerce").fillna(0).astype(float)
    )
    df[GOLDSTEIN_COL] = (
        pd.to_numeric(df[GOLDSTEIN_COL], errors="coerce").fillna(0.0).astype(float)
    )

    agg_df = (
        df.groupby(group_cols, dropna=False)
        .agg({NUM_MENTIONS_COL: "sum", GOLDSTEIN_COL: "mean"})
        .reset_index()
    )

    return agg_df


def compute_risk_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Compute risk_score and EventRisk for each deduplicated event.

    risk_score = (max(0, -GoldsteinScale) / 10) * event_severity_weight
    MentionWeight = log1p(NumMentions)
    EventRisk = risk_score * MentionWeight

    GoldsteinScale and NumMentions are assumed numeric; any remaining missing
    values are treated as 0.
    """
    # Make sure required columns exist and are numeric.
    if GOLDSTEIN_COL not in df.columns:
        df[GOLDSTEIN_COL] = 0.0
    if NUM_MENTIONS_COL not in df.columns:
        df[NUM_MENTIONS_COL] = 0

    df[GOLDSTEIN_COL] = (
        pd.to_numeric(df[GOLDSTEIN_COL], errors="coerce").fillna(0.0).astype(float)
    )
    df[NUM_MENTIONS_COL] = (
        pd.to_numeric(df[NUM_MENTIONS_COL], errors="coerce").fillna(0).astype(float)
    )

    event_prefix = df[EVENT_CODE_COL].astype(str).str.slice(0, 2)
    severity = event_prefix.map(EVENT_PREFIX_WEIGHTS).fillna(1.0).astype(float)

    # Base severity from Goldstein (negative side only), scaled and weighted by
    # conflict-event family severity.
    df["risk_score"] = ((-df[GOLDSTEIN_COL]).clip(lower=0) / 10.0) * severity

    # Mentions are heavy-tailed; log1p stabilizes extreme spikes from media bursts.
    df["MentionWeight"] = np.log1p(df[NUM_MENTIONS_COL].clip(lower=0))

    # Event risk contribution.
    df["EventRisk"] = df["risk_score"] * df["MentionWeight"]

    return df


def filter_india_events(df: pd.DataFrame) -> pd.DataFrame:
    """Optionally filter to events where either actor is India (IND).

    If actor country columns are missing, an empty dataframe is returned to
    avoid silently mixing non-India events.
    """
    candidate_cols = [
        ACTOR1_COUNTRY_COL,
        ACTOR2_COUNTRY_COL,
        ACTOR1_GEO_COUNTRY_COL,
        ACTOR2_GEO_COUNTRY_COL,
        ACTION_GEO_COUNTRY_COL,
    ]

    available = [c for c in candidate_cols if c in df.columns]
    if not available:
        return df.iloc[0:0].copy()

    mask = pd.Series(False, index=df.index)
    for col in available:
        vals = df[col].astype(str).str.upper().str.strip()
        mask = mask | vals.isin(INDIA_CODES)

    return df.loc[mask].copy()


def aggregate_daily_gpr(df: pd.DataFrame) -> pd.DataFrame:
    """Compute a basic daily aggregation plus simple moving averages.

    For each SQLDATE:
    - DailyRisk = sum(EventRisk)
    - TotalMentions = sum(NumMentions)
    - MentionWeight = sum(log1p(NumMentions))
    - GPR_RAW = DailyRisk / MentionWeight  (0 if MentionWeight == 0)

    Then we apply robust rolling normalization (median/MAD, 180-day window)
    and squash with a logistic transform to keep GPR bounded and comparable.

    We also compute rolling moving averages of GPR to mirror the behaviour of
    the published Caldara–Iacoviello DataGPR series:
    - GPR_MA7  ≈ 7-day moving average of GPR
    - GPR_MA30 ≈ 30-day moving average of GPR

    (On very short samples these are just partial-window averages, but on
    longer histories they give smoother "spike" behaviour closer to DataGPR.)
    """
    if SQLDATE_COL not in df.columns:
        # Without dates we cannot do a daily aggregation.
        return pd.DataFrame(columns=[SQLDATE_COL, "DailyRisk", "TotalMentions", "GPR"])

    if "EventRisk" not in df.columns:
        # If EventRisk is missing, compute with default assumptions.
        df = compute_risk_scores(df.copy())

    # Ensure numeric types and handle missing values.
    df["EventRisk"] = (
        pd.to_numeric(df["EventRisk"], errors="coerce").fillna(0.0).astype(float)
    )
    df[NUM_MENTIONS_COL] = (
        pd.to_numeric(df[NUM_MENTIONS_COL], errors="coerce").fillna(0).astype(float)
    )

    if "MentionWeight" not in df.columns:
        # Backward compatibility if caller provided precomputed EventRisk only.
        df["MentionWeight"] = np.log1p(df[NUM_MENTIONS_COL].clip(lower=0))

    daily = (
        df.groupby(SQLDATE_COL, dropna=False)
        .agg(
            DailyRisk=("EventRisk", "sum"),
            TotalMentions=(NUM_MENTIONS_COL, "sum"),
            MentionWeight=("MentionWeight", "sum"),
        )
        .reset_index()
    )

    # Avoid divide-by-zero; where MentionWeight == 0, set raw GPR to 0.
    daily["GPR_RAW"] = daily["DailyRisk"] / daily["MentionWeight"].replace({0: pd.NA})
    daily["GPR_RAW"] = daily["GPR_RAW"].fillna(0.0)

    # Clamp extreme outliers at p99 to reduce one-day media artifacts.
    p99 = float(daily["GPR_RAW"].quantile(0.99)) if not daily.empty else 0.0
    if p99 > 0:
        daily["GPR_RAW"] = daily["GPR_RAW"].clip(upper=p99)

    # Compute moving averages on GPR, sorted by date. SQLDATE is in YYYYMMDD
    # integer format in GDELT, so sorting by it is equivalent to sorting by
    # calendar date.
    daily = daily.sort_values(SQLDATE_COL).reset_index(drop=True)

    # Stable rolling normalization: smooth raw signal first, then compute
    # rolling z-score with an epsilon floor to avoid divide-by-zero collapse.
    raw_smooth = daily["GPR_RAW"].rolling(window=7, min_periods=3).mean()
    roll_mean = raw_smooth.rolling(window=180, min_periods=30).mean()
    roll_std = raw_smooth.rolling(window=180, min_periods=30).std(ddof=0)
    z = (raw_smooth - roll_mean) / (roll_std.fillna(0.0) + 1e-6)
    z = z.replace([np.inf, -np.inf], 0.0).fillna(0.0).clip(-4.0, 4.0)

    # Bounded index in (0,1), stable and interpretable for downstream.
    daily["GPR"] = 1.0 / (1.0 + np.exp(-z))

    # 7-day and 30-day simple moving averages.
    daily["GPR_MA7"] = daily["GPR"].rolling(window=7, min_periods=1).mean()
    daily["GPR_MA30"] = daily["GPR"].rolling(window=30, min_periods=1).mean()

    return daily


def run_sample_pipeline(
    csv_path: str,
    sample_size: int = 12,
    india_only: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Run the small-sample GPR pipeline on a GDELT Events CSV.

    Steps:
    1. Load data
    2. Filter conflict events
    3. Deduplicate
    4. Compute risk scores & EventRisk
    5. (Optionally) filter to India-related events
    6. Produce a small sample of the first N processed rows
    7. Compute a simple daily GPR aggregation

    Returns
    -------
    sample_df : pd.DataFrame
        The first `sample_size` processed rows, for quick inspection.
    daily_df : pd.DataFrame
        Daily aggregation with DailyRisk, TotalMentions, and GPR.
    """
    # 1. Load raw events
    raw_df = load_gdelt_events(csv_path)

    # 2. Filter conflict-related events
    conflict_df = filter_conflict_events(raw_df)

    # 3. Deduplicate at daily dyad / event level
    dedup_df = deduplicate_events(conflict_df)

    # 4. Compute risk scores and EventRisk
    scored_df = compute_risk_scores(dedup_df)

    # 5. Optional India filter
    if india_only:
        processed_df = filter_india_events(scored_df)
    else:
        processed_df = scored_df

    # 6. Small sample output (10–12 rows by default)
    sample_df = processed_df.head(sample_size).copy()

    # 7. Daily aggregation
    daily_df = aggregate_daily_gpr(processed_df)

    # Print clearly for quick testing
    if not sample_df.empty:
        print("Processed event sample (first {} rows):".format(len(sample_df)))
        # Use to_string for a readable, column-aligned printout.
        print(sample_df.to_string(index=False))
    else:
        print("No processed events available in the sample.")

    if not daily_df.empty:
        print("\nDaily GPR aggregation:")
        print(daily_df.to_string(index=False))
    else:
        print("\nNo daily GPR aggregation could be computed (missing dates or events).")

    return sample_df, daily_df


if __name__ == "__main__":
    # Example usage for quick manual testing. Replace with your local CSV path.
    example_path = "./gdelt_events_sample.csv"  # Update to point to a small test CSV.

    try:
        run_sample_pipeline(example_path, sample_size=12, india_only=False)
    except FileNotFoundError:
        print(f"Sample file not found: {example_path}. Please update the path and retry.")
