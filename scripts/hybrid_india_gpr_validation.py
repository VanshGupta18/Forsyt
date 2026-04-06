"""
Hybrid GPR validation pipeline (GDELT Events, no NLP).

Design goals:
- Similar spirit to Caldara-Iacoviello (article-share style denominator)
- Light severity adjustment using GoldsteinScale
- Transparent, modular, prototype-friendly

Outputs:
- daily_<scope>_gpr.csv
- monthly_<scope>_gpr_index.csv
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple
import argparse
import re

import pandas as pd

REQUIRED_COLS = [
    "SQLDATE",
    "Actor1CountryCode",
    "Actor2CountryCode",
    "EventCode",
    "NumMentions",
    "GoldsteinScale",
]

# Official GDELT Events schema (for headerless daily exports)
OFFICIAL_GDELT_COLS = [
    "GLOBALEVENTID", "SQLDATE", "MonthYear", "Year", "FractionDate",
    "Actor1Code", "Actor1Name", "Actor1CountryCode", "Actor1KnownGroupCode",
    "Actor1EthnicCode", "Actor1Religion1Code", "Actor1Religion2Code",
    "Actor1Type1Code", "Actor1Type2Code", "Actor1Type3Code",
    "Actor2Code", "Actor2Name", "Actor2CountryCode", "Actor2KnownGroupCode",
    "Actor2EthnicCode", "Actor2Religion1Code", "Actor2Religion2Code",
    "Actor2Type1Code", "Actor2Type2Code", "Actor2Type3Code", "IsRootEvent",
    "EventCode", "EventBaseCode", "EventRootCode", "QuadClass",
    "GoldsteinScale", "NumMentions", "NumSources", "NumArticles", "AvgTone",
    "Actor1Geo_Type", "Actor1Geo_FullName", "Actor1Geo_CountryCode",
    "Actor1Geo_ADM1Code", "Actor1Geo_Lat", "Actor1Geo_Long", "Actor1Geo_FeatureID",
    "Actor2Geo_Type", "Actor2Geo_FullName", "Actor2Geo_CountryCode",
    "Actor2Geo_ADM1Code", "Actor2Geo_Lat", "Actor2Geo_Long", "Actor2Geo_FeatureID",
    "ActionGeo_Type", "ActionGeo_FullName", "ActionGeo_CountryCode",
    "ActionGeo_ADM1Code", "ActionGeo_Lat", "ActionGeo_Long", "ActionGeo_FeatureID",
    "DATEADDED", "SOURCEURL",
]


def _iter_input_files(input_path: Path, max_files: int | None = None) -> List[Path]:
    if input_path.is_file():
        return [input_path]

    if not input_path.is_dir():
        raise FileNotFoundError(f"Input path not found: {input_path}")

    # Prefer official GDELT daily export files to avoid accidentally reading
    # unrelated CSVs in the same folder.
    files = sorted(
        list(input_path.glob("*.export.CSV"))
        + list(input_path.glob("*.export.csv"))
    )

    # Fallback: if none found, use all csv files.
    if not files:
        files = sorted(list(input_path.glob("*.CSV")) + list(input_path.glob("*.csv")))

    # De-duplicate in case case-insensitive FS returns same file for both globs.
    unique = {}
    for f in files:
        unique[str(f.resolve()).lower()] = f
    files = sorted(unique.values(), key=lambda p: p.name)
    if max_files is not None:
        files = files[:max_files]

    if not files:
        raise FileNotFoundError(f"No CSV files found under directory: {input_path}")

    return files


def _read_single_file(path: Path) -> pd.DataFrame:
    """Read one GDELT events file using column names (not positions)."""
    # 1) Try regular CSV with existing header
    try:
        df = pd.read_csv(path, low_memory=False, dtype=str)
        if all(c in df.columns for c in REQUIRED_COLS):
            return df[REQUIRED_COLS].copy()
    except Exception:
        pass

    # 2) Fallback for official GDELT tab-separated headerless exports
    df = pd.read_csv(
        path,
        sep="\t",
        header=None,
        names=OFFICIAL_GDELT_COLS,
        usecols=REQUIRED_COLS,
        dtype=str,
        low_memory=False,
    )

    # For daily export files like 20230101.export.CSV, use filename date as
    # authoritative to avoid malformed in-file SQLDATE values in edge cases.
    m = re.match(r"^(\d{8})\.export\.csv$", path.name, flags=re.IGNORECASE)
    if m:
        df["SQLDATE"] = m.group(1)

    return df


def load_data(input_path: str, max_files: int | None = None) -> pd.DataFrame:
    """Load local GDELT events data (single CSV or folder of CSV files)."""
    p = Path(input_path)
    files = _iter_input_files(p, max_files=max_files)

    frames: List[pd.DataFrame] = []
    skipped: List[Path] = []
    total = len(files)
    for idx, f in enumerate(files, start=1):
        try:
            frames.append(_read_single_file(f))
        except KeyboardInterrupt:
            raise
        except Exception as e:
            skipped.append(f)
            print(f"[WARN] Skipped unreadable file ({idx}/{total}) {f.name}: {e}")

        if idx % 100 == 0 or idx == total:
            print(f"[LOAD] Progress: {idx}/{total} files")

    if not frames:
        raise RuntimeError(
            f"No readable files found under {input_path}. "
            f"Tried {len(files)} files, skipped {len(skipped)}."
        )

    df = pd.concat(frames, ignore_index=True)
    print(f"[LOAD] Loaded {len(frames)} file(s), rows={len(df):,}")
    if skipped:
        print(f"[LOAD] Skipped unreadable file(s): {len(skipped)}")
    print(f"[LOAD] Columns present: {list(df.columns)}")
    return df


def clean_data(
    df: pd.DataFrame,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Convert types and fill missing values as requested."""
    out = df.copy()
    out["SQLDATE"] = pd.to_datetime(out["SQLDATE"].astype(str), format="%Y%m%d", errors="coerce")

    out["NumMentions"] = pd.to_numeric(out["NumMentions"], errors="coerce").fillna(0)
    out["GoldsteinScale"] = pd.to_numeric(out["GoldsteinScale"], errors="coerce").fillna(0)

    # Keep rows with valid date after conversion
    out = out.dropna(subset=["SQLDATE"]).reset_index(drop=True)

    # Optional date window filter (recommended for multi-year local folders).
    if start_date is not None:
        start_ts = pd.to_datetime(start_date)
        out = out[out["SQLDATE"] >= start_ts]
    if end_date is not None:
        end_ts = pd.to_datetime(end_date)
        out = out[out["SQLDATE"] <= end_ts]

    out = out.reset_index(drop=True)
    return out


def filter_india(df: pd.DataFrame) -> pd.DataFrame:
    """Keep rows where either actor country is IND."""
    india = df[(df["Actor1CountryCode"] == "IND") | (df["Actor2CountryCode"] == "IND")].copy()
    return india


def filter_conflict(df: pd.DataFrame) -> pd.DataFrame:
    """Keep EventCode prefixes: 13 (threat), 17 (coercion), 19 (military)."""
    code = df["EventCode"].astype(str)
    conflict = df[code.str.startswith(("13", "17", "19"), na=False)].copy()
    return conflict


def compute_risk_score(df: pd.DataFrame) -> pd.DataFrame:
    """risk_score = max(0, -GoldsteinScale)/10, clipped to [0,1]."""
    out = df.copy()
    out["risk_score"] = (-out["GoldsteinScale"]).clip(lower=0) / 10.0
    out["risk_score"] = out["risk_score"].clip(lower=0, upper=1)

    # Assertions requested
    assert ((out["risk_score"] >= 0) & (out["risk_score"] <= 1)).all(), "risk_score out of [0,1]"

    return out


def compute_event_weight(df: pd.DataFrame, alpha: float = 0.4) -> pd.DataFrame:
    """EventWeight = NumMentions * (1 + alpha * risk_score)."""
    out = df.copy()
    out["EventWeight"] = out["NumMentions"] * (1 + alpha * out["risk_score"])

    return out


def _print_debug_samples(
    clean_df: pd.DataFrame,
    scoped_df: pd.DataFrame,
    conflict_df: pd.DataFrame,
    weighted_df: pd.DataFrame,
    scope_label: str,
) -> None:
    print(f"[DEBUG] After {scope_label} scope filter: rows={len(scoped_df):,}")
    print(scoped_df.head(5).to_string(index=False))

    print(f"[DEBUG] After conflict filter: rows={len(conflict_df):,}")
    print(conflict_df.head(5).to_string(index=False))

    print("[DEBUG] After risk_score:")
    print(weighted_df[["SQLDATE", "EventCode", "NumMentions", "GoldsteinScale", "risk_score"]].head(8).to_string(index=False))

    print("[DEBUG] After EventWeight:")
    print(weighted_df[["SQLDATE", "NumMentions", "risk_score", "EventWeight"]].head(8).to_string(index=False))


def run_streaming_pipeline(
    input_path: str,
    alpha: float,
    start_date: str,
    end_date: str,
    max_files: int | None,
    india_only: bool,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Run hybrid pipeline in streaming mode (file-by-file aggregation).

    This avoids loading all years into memory at once.
    """
    files = _iter_input_files(Path(input_path), max_files=max_files)
    print(f"[LOAD] Streaming mode on {len(files)} file(s)")

    # SQLDATE -> totals
    total_mentions: dict[pd.Timestamp, float] = {}
    risk_t: dict[pd.Timestamp, float] = {}

    printed_debug = False
    for idx, f in enumerate(files, start=1):
        try:
            raw = _read_single_file(f)
            clean = clean_data(raw, start_date=start_date, end_date=end_date)
            if clean.empty:
                continue

            # Denominator from full cleaned file
            d = clean.groupby("SQLDATE", as_index=False)["NumMentions"].sum()
            for row in d.itertuples(index=False):
                total_mentions[row.SQLDATE] = total_mentions.get(row.SQLDATE, 0.0) + float(row.NumMentions)

            # Numerator from scoped (global or India-only) conflict + weighted events
            scoped = filter_india(clean) if india_only else clean
            conflict = filter_conflict(scoped)
            if conflict.empty:
                continue

            scored = compute_risk_score(conflict)
            weighted = compute_event_weight(scored, alpha=alpha)

            n = weighted.groupby("SQLDATE", as_index=False)["EventWeight"].sum()
            for row in n.itertuples(index=False):
                risk_t[row.SQLDATE] = risk_t.get(row.SQLDATE, 0.0) + float(row.EventWeight)

            # Print debug once using the first non-empty processed file
            if not printed_debug:
                _print_debug_samples(
                    clean,
                    scoped,
                    conflict,
                    weighted,
                    "India-only" if india_only else "global",
                )
                printed_debug = True

        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"[WARN] Skipped file {f.name}: {e}")

        if idx % 100 == 0 or idx == len(files):
            print(f"[LOAD] Progress: {idx}/{len(files)} files")

    daily = pd.DataFrame(
        {
            "SQLDATE": list(total_mentions.keys()),
            "TotalMentions_t": list(total_mentions.values()),
        }
    )
    if daily.empty:
        return (
            pd.DataFrame(columns=["SQLDATE", "TotalMentions_t", "Risk_t", "GPR_t"]),
            pd.DataFrame(columns=["SQLDATE", "MonthlyGPR", "Index_t"]),
        )

    risk_df = pd.DataFrame(
        {
            "SQLDATE": list(risk_t.keys()),
            "Risk_t": list(risk_t.values()),
        }
    )

    daily = daily.merge(risk_df, on="SQLDATE", how="left")
    daily["Risk_t"] = daily["Risk_t"].fillna(0.0)
    daily["GPR_t"] = daily["Risk_t"] / daily["TotalMentions_t"].replace({0: pd.NA})
    daily["GPR_t"] = daily["GPR_t"].fillna(0.0)

    assert (~daily["GPR_t"].isin([float("inf"), float("-inf")])).all(), "division-by-zero produced inf"
    assert (daily["GPR_t"] >= 0).all(), "GPR_t has negative values"

    daily = daily.sort_values("SQLDATE").reset_index(drop=True)

    monthly = (
        daily.assign(SQLMONTH=daily["SQLDATE"].dt.to_period("M").dt.to_timestamp())
        .groupby("SQLMONTH", as_index=False)["GPR_t"]
        .mean()
        .rename(columns={"SQLMONTH": "SQLDATE", "GPR_t": "MonthlyGPR"})
        .sort_values("SQLDATE")
        .reset_index(drop=True)
    )

    mean_monthly = float(monthly["MonthlyGPR"].mean()) if not monthly.empty else 0.0
    monthly["Index_t"] = 0.0 if mean_monthly == 0 else (monthly["MonthlyGPR"] / mean_monthly) * 100.0

    return daily, monthly


def compute_gpr(full_df: pd.DataFrame, scoped_conflict_weighted_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Daily:
      TotalMentions_t = sum NumMentions over FULL dataset
    Risk_t = sum EventWeight over scoped (global or India-only) conflict subset
    GPR_t = Risk_t / TotalMentions_t

    Monthly:
    MonthlyGPR = mean(daily GPR)
      Index_t = (MonthlyGPR / mean(MonthlyGPR)) * 100
    """
    denom = (
        full_df.groupby("SQLDATE", as_index=False)["NumMentions"]
        .sum()
        .rename(columns={"NumMentions": "TotalMentions_t"})
    )

    numer = (
        scoped_conflict_weighted_df.groupby("SQLDATE", as_index=False)["EventWeight"]
        .sum()
        .rename(columns={"EventWeight": "Risk_t"})
    )

    daily = denom.merge(numer, on="SQLDATE", how="left")
    daily["Risk_t"] = daily["Risk_t"].fillna(0)

    daily["GPR_t"] = daily["Risk_t"] / daily["TotalMentions_t"].replace({0: pd.NA})
    daily["GPR_t"] = daily["GPR_t"].fillna(0)

    # Assertions requested
    assert (~daily["GPR_t"].isin([float("inf"), float("-inf")])).all(), "division-by-zero produced inf"
    assert (daily["GPR_t"] >= 0).all(), "GPR_t has negative values"

    monthly = (
        daily.assign(SQLMONTH=daily["SQLDATE"].dt.to_period("M").dt.to_timestamp())
        .groupby("SQLMONTH", as_index=False)["GPR_t"]
        .mean()
        .rename(columns={"SQLMONTH": "SQLDATE", "GPR_t": "MonthlyGPR"})
        .sort_values("SQLDATE")
        .reset_index(drop=True)
    )

    mean_monthly = float(monthly["MonthlyGPR"].mean()) if not monthly.empty else 0.0
    if mean_monthly == 0:
        monthly["Index_t"] = 0.0
    else:
        monthly["Index_t"] = (monthly["MonthlyGPR"] / mean_monthly) * 100.0

    return daily, monthly


def main() -> None:
    parser = argparse.ArgumentParser(description="Hybrid GPR validation pipeline (GDELT, no NLP)")
    parser.add_argument(
        "--input-path",
        default=r"D:\forsyt_gdelt\events_2023_2026",
        help="Path to local GDELT CSV file OR directory of GDELT CSV files",
    )
    parser.add_argument(
        "--output-dir",
        default=r"D:\forsyt_gdelt",
        help="Directory to save output CSVs",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Optional limit on number of files when input-path is a directory (for quick testing)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.4,
        help="Severity adjustment strength in EventWeight (default 0.4)",
    )
    parser.add_argument(
        "--start-date",
        default="2023-01-01",
        help="Inclusive start date filter after cleaning (default: 2023-01-01)",
    )
    parser.add_argument(
        "--end-date",
        default="2026-03-26",
        help="Inclusive end date filter after cleaning (default: 2026-03-26)",
    )
    parser.add_argument(
        "--india-only",
        action="store_true",
        help="If set, apply India actor filter before conflict filtering. Default is global scope.",
    )
    args = parser.parse_args()

    # Streaming run over file set for memory-safe full-history processing.
    daily_gpr, monthly_index = run_streaming_pipeline(
        input_path=args.input_path,
        alpha=args.alpha,
        start_date=args.start_date,
        end_date=args.end_date,
        max_files=args.max_files,
        india_only=args.india_only,
    )

    print("\n[RESULT] Daily GPR (head):")
    print(daily_gpr.head(10).to_string(index=False))

    print("\n[RESULT] Monthly Index (head):")
    print(monthly_index.head(10).to_string(index=False))

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scope = "india" if args.india_only else "global"
    daily_path = out_dir / f"daily_{scope}_gpr.csv"
    monthly_path = out_dir / f"monthly_{scope}_gpr_index.csv"

    daily_gpr.to_csv(daily_path, index=False)
    monthly_index.to_csv(monthly_path, index=False)

    print(f"\n[SAVE] {daily_path}")
    print(f"[SAVE] {monthly_path}")


if __name__ == "__main__":
    main()
