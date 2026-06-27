"""Fill calendar gaps in daily GPR index output.

When GDELT GKG data is unavailable for certain dates (e.g. Jun 15–Jul 1 2025),
gkg_gpr_pipeline.py simply skips those days, producing a sparse 348-row CSV
instead of a 365-row calendar-complete series.

This module post-processes the observed outputs to produce:
  gpr_daily_index_continuous.csv   — 365 rows, imputed days flagged
  gpr_monthly_index_continuous.csv — 12 rows, correct June weighting

Imputation methods:
  caldara (default) — scale Caldara GPRD through the gap from last observed day
  forward           — carry last observed index forward through the gap
  linear            — linearly interpolate between boundary days

The observed gpr_daily_index.csv is never modified.

Usage:
  python -m scripts.fill_gpr_gaps \\
    --output-dir  outputs \\
    --start-date  2025-01-01 \\
    --end-date    2025-12-31 \\
    --fill-method caldara
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Literal

import pandas as pd

FILL_METHODS = ("forward", "linear", "caldara")

CALDARA_DAILY_CANDIDATES = [
    Path("data/caldara_gpr_daily.xls"),
    Path("data/data_gpr_daily_recent.xls"),
]

INDEX_COLS = ["gpr_index", "gpr_acts_index", "gpr_threats_index"]
ARTICLE_COLS = [
    "total_articles", "candidate_count", "gpr_positive_count",
    "positive_share", "mean_score", "gpr_sum",
]


def _load_caldara_daily() -> pd.DataFrame | None:
    for p in CALDARA_DAILY_CANDIDATES:
        if p.exists():
            cal = pd.read_excel(p)
            date_col = next((c for c in cal.columns if "date" in c.lower()), None)
            if date_col and "GPRD" in cal.columns:
                cal = cal.copy()
                cal["date"] = pd.to_datetime(cal[date_col]).dt.normalize()
                return cal.set_index("date")
    return None


def detect_missing_dates(
    daily_df: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> List[pd.Timestamp]:
    full_range = pd.date_range(start=start_date, end=end_date, freq="D")
    observed = set(pd.to_datetime(daily_df["date"]).dt.normalize())
    return [d for d in full_range if d not in observed]


def fill_daily_gaps(
    daily_df: pd.DataFrame,
    start_date: str,
    end_date: str,
    method: Literal["forward", "linear", "caldara"] = "caldara",
) -> pd.DataFrame:
    df = daily_df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["is_imputed"] = False
    df["impute_method"] = "none"
    for col in ARTICLE_COLS:
        if col not in df.columns:
            df[col] = 0.0

    missing = detect_missing_dates(df, start_date, end_date)

    if not missing:
        df = df.sort_values("date").reset_index(drop=True)
        return _recompute_moving_averages(df)

    gap_rows = pd.DataFrame({"date": missing})
    gap_rows["is_imputed"] = True
    gap_rows["impute_method"] = method
    for col in ARTICLE_COLS:
        gap_rows[col] = 0.0
    for col in INDEX_COLS:
        gap_rows[col] = float("nan")

    combined = (
        pd.concat([df, gap_rows], ignore_index=True)
        .sort_values("date")
        .reset_index(drop=True)
    )

    if method == "forward":
        for col in INDEX_COLS:
            combined[col] = combined[col].ffill()
    elif method == "linear":
        for col in INDEX_COLS:
            combined[col] = combined[col].interpolate(method="linear")
    elif method == "caldara":
        cal = _load_caldara_daily()
        if cal is None:
            print("[GAPS] WARN: Caldara daily file not found — falling back to linear")
            for col in INDEX_COLS:
                combined[col] = combined[col].interpolate(method="linear")
        else:
            obs_sorted = df.sort_values("date").reset_index(drop=True)
            for col in INDEX_COLS:
                combined[col] = combined[col].ffill()
            imputed = combined[combined["is_imputed"]].sort_values("date")
            if not imputed.empty:
                first_gap = pd.Timestamp(imputed.iloc[0]["date"]).normalize()
                prior = obs_sorted[obs_sorted["date"] < first_gap]
                if prior.empty:
                    prior = obs_sorted
                anchor = prior.iloc[-1]
                anchor_date = pd.Timestamp(anchor["date"]).normalize()
                if anchor_date in cal.index:
                    scale = float(anchor["gpr_index"]) / float(cal.loc[anchor_date, "GPRD"])
                    for i, row in imputed.iterrows():
                        d = pd.Timestamp(row["date"]).normalize()
                        if d in cal.index:
                            combined.at[i, "gpr_index"] = float(cal.loc[d, "GPRD"]) * scale
            for col in ("gpr_acts_index", "gpr_threats_index"):
                combined[col] = combined[col].interpolate(method="linear")

    combined = _recompute_moving_averages(combined)
    scale = 100.0 / combined["gpr_index"].mean() if combined["gpr_index"].mean() > 0 else 1.0
    for col in INDEX_COLS:
        combined[col] = combined[col] * scale
    combined = _recompute_moving_averages(combined)
    return combined


def _recompute_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("date").reset_index(drop=True)
    df["gpr_7ma"]  = df["gpr_index"].rolling(7,  min_periods=1).mean()
    df["gpr_30ma"] = df["gpr_index"].rolling(30, min_periods=1).mean()
    return df


def build_monthly(daily_df: pd.DataFrame) -> pd.DataFrame:
    df = daily_df.copy()
    df["year_month"] = pd.to_datetime(df["date"]).dt.to_period("M")
    return (
        df.groupby("year_month", as_index=False)
        .agg(
            gpr_index=("gpr_index", "mean"),
            gpr_acts_index=("gpr_acts_index", "mean"),
            gpr_threats_index=("gpr_threats_index", "mean"),
            imputed_days=("is_imputed", "sum"),
            total_days=("date", "count"),
        )
    )


def run(
    output_dir: Path,
    start_date: str,
    end_date: str,
    method: str = "caldara",
) -> None:
    if method not in FILL_METHODS:
        raise ValueError(f"--fill-method must be one of {FILL_METHODS}")

    daily_path = output_dir / "gpr_daily_index.csv"
    if not daily_path.exists():
        raise FileNotFoundError(
            f"gpr_daily_index.csv not found in {output_dir} — run main.py gpr first"
        )

    daily_df = pd.read_csv(daily_path, parse_dates=["date"])
    missing = detect_missing_dates(daily_df, start_date, end_date)

    if not missing:
        print("[GAPS] No missing calendar dates — nothing to fill.")
        return

    print(f"[GAPS] {len(missing)} missing calendar day(s):")
    for d in missing:
        print(f"  {d.date()}")
    print(f"[GAPS] Fill method: {method}")

    continuous = fill_daily_gaps(daily_df, start_date, end_date, method)
    monthly    = build_monthly(continuous)

    save_cols = [
        "date", "total_articles", "candidate_count", "gpr_positive_count",
        "positive_share", "mean_score", "gpr_sum",
        "gpr_index", "gpr_acts_index", "gpr_threats_index",
        "gpr_7ma", "gpr_30ma",
        "is_imputed", "impute_method",
    ]
    out_daily   = output_dir / "gpr_daily_index_continuous.csv"
    out_monthly = output_dir / "gpr_monthly_index_continuous.csv"
    out_report  = output_dir / "validation" / "gap_imputation_report.csv"
    out_report.parent.mkdir(parents=True, exist_ok=True)

    continuous[[c for c in save_cols if c in continuous.columns]].to_csv(out_daily, index=False)
    monthly.to_csv(out_monthly, index=False)

    report = continuous[continuous["is_imputed"]].copy()
    report_cols = ["date", "gpr_index", "gpr_acts_index", "gpr_threats_index", "impute_method"]
    report[[c for c in report_cols if c in report.columns]].to_csv(out_report, index=False)

    n_total = len(continuous)
    n_obs   = n_total - len(missing)
    print(f"\n[GAPS] Done.")
    print(f"  Observed days  : {n_obs}")
    print(f"  Imputed days   : {len(missing)}")
    print(f"  Total calendar : {n_total}")
    print(f"  Outputs:")
    print(f"    {out_daily}")
    print(f"    {out_monthly}")
    print(f"    {out_report}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fill calendar gaps in GPR daily index output")
    p.add_argument("--output-dir",   default="outputs")
    p.add_argument("--start-date",   default="2025-01-01")
    p.add_argument("--end-date",     default="2025-12-31")
    p.add_argument("--fill-method",  default="caldara", choices=list(FILL_METHODS))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run(
        output_dir=Path(args.output_dir),
        start_date=args.start_date,
        end_date=args.end_date,
        method=args.fill_method,
    )


if __name__ == "__main__":
    main()
