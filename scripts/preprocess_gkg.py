"""Merge raw GKG 15-minute slot files into one Parquet file per day.

Reads from data/gkg_raw/ (YYYYMMDDHHMMSS.gkg.csv files).
Writes to data/gkg_processed/ as gkg_processed_YYYYMMDD.parquet.

Per day: concatenates all 96 slot CSVs, deduplicates by DocumentIdentifier
(keeping the latest slot occurrence), parses all 7 GKG fields, and saves
as Snappy-compressed Parquet for fast columnar reads downstream.

GKG 2.0 columns extracted (0-indexed):
  1  DATE           YYYYMMDDHHMMSS → parsed to datetime
  3  SourceCommonName
  4  DocumentIdentifier  (dedup key)
  8  V2Themes       semicolon-separated theme codes (offsets stripped)
 10  V2Locations    semicolon-separated structured location entries
 15  V2Tone_raw     comma-sep: overall,pos,neg,polarity,actref,selfref
 17  GCAM           key:value conflict dimension scores

Parsed output columns:
  SQLDATE, SourceCommonName, DocumentIdentifier, V2Themes,
  V2Locations, GCAM, tone_overall, tone_neg, tone_polarity

Usage:
  python -m scripts.preprocess_gkg \\
    --start-date  2025-01-01 \\
    --end-date    2025-12-31 \\
    --raw-dir     data/gkg_raw \\
    --processed-dir data/gkg_processed
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd


GKG_USECOLS = [1, 3, 4, 8, 10, 15, 17]
GKG_NAMES = [
    "SQLDATE", "SourceCommonName", "DocumentIdentifier",
    "V2Themes", "V2Locations", "V2Tone_raw", "GCAM",
]


def generate_dates(start_date: str, end_date: str) -> Iterable[dt.date]:
    start = dt.datetime.strptime(start_date, "%Y-%m-%d").date()
    end   = dt.datetime.strptime(end_date,   "%Y-%m-%d").date()
    if end < start:
        raise ValueError("end_date must be >= start_date")
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)


def normalize_gkg_dataframe(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Clean raw GKG columns into the standard processed schema."""
    if df.empty:
        return None

    df = df.copy()
    df["SQLDATE"] = pd.to_datetime(
        df["SQLDATE"].astype(str), format="%Y%m%d%H%M%S", errors="coerce"
    )
    df = df.dropna(subset=["SQLDATE"]).reset_index(drop=True)
    if df.empty:
        return None

    df["DocumentIdentifier"] = df["DocumentIdentifier"].fillna("").astype(str)
    df = df[df["DocumentIdentifier"].str.len() > 0].reset_index(drop=True)
    if df.empty:
        return None

    df["SourceCommonName"] = df["SourceCommonName"].fillna("").astype(str)
    df["V2Themes"] = (
        df["V2Themes"].fillna("").astype(str)
        .str.replace(r",\d+", "", regex=True)
    )
    df["V2Locations"] = df["V2Locations"].fillna("").astype(str)

    tone = df["V2Tone_raw"].fillna("").astype(str).str.split(",", expand=False)
    df["tone_overall"]  = pd.to_numeric(tone.str[0], errors="coerce").fillna(0.0)
    df["tone_neg"]      = pd.to_numeric(tone.str[2], errors="coerce").fillna(0.0).abs()
    df["tone_polarity"] = pd.to_numeric(tone.str[3], errors="coerce").fillna(0.0).abs()
    df.drop(columns=["V2Tone_raw"], inplace=True)
    df["GCAM"] = df["GCAM"].fillna("").astype(str)
    return df


def load_slot_csv(csv_path: Path) -> Optional[pd.DataFrame]:
    """Parse one raw GKG CSV slot into a cleaned DataFrame."""
    df: Optional[pd.DataFrame] = None
    for enc in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(
                csv_path,
                sep="\t",
                header=None,
                usecols=GKG_USECOLS,
                names=GKG_NAMES,
                dtype=str,
                on_bad_lines="skip",
                engine="python",
                encoding=enc,
            )
            break
        except Exception:
            pass

    if df is None:
        print(f"  [WARN] could not read {csv_path.name}")
        return None

    return normalize_gkg_dataframe(df)


def merge_day(day: dt.date, raw_dir: Path, processed_dir: Path) -> Optional[Path]:
    """Merge all slot CSVs for one day, dedupe, and write Parquet."""
    ymd   = day.strftime("%Y%m%d")
    slots = sorted(raw_dir.glob(f"{ymd}*.gkg.csv"))
    if not slots:
        return None

    frames: List[pd.DataFrame] = []
    for slot in slots:
        df = load_slot_csv(slot)
        if df is not None:
            frames.append(df)

    if not frames:
        return None

    merged = pd.concat(frames, ignore_index=True)
    # Latest slot wins per URL (most complete GCAM/tone)
    merged = (
        merged
        .sort_values("SQLDATE")
        .drop_duplicates(subset=["DocumentIdentifier"], keep="last")
        .reset_index(drop=True)
    )

    processed_dir.mkdir(parents=True, exist_ok=True)
    out_path = processed_dir / f"gkg_processed_{ymd}.parquet"
    merged.to_parquet(out_path, index=False, compression="snappy")
    return out_path


def run(
    start_date: str,
    end_date: str,
    raw_dir: Path,
    processed_dir: Path,
) -> None:
    processed_dir.mkdir(parents=True, exist_ok=True)
    total_ok     = 0
    total_skip   = 0
    failed_dates: List[str] = []

    for day in generate_dates(start_date, end_date):
        ymd      = day.strftime("%Y%m%d")
        out_path = processed_dir / f"gkg_processed_{ymd}.parquet"

        if out_path.exists():
            print(f"[{ymd}] SKIP (already exists)")
            total_skip += 1
            continue

        print(f"[{ymd}] merging ...", end=" ", flush=True)
        result = merge_day(day, raw_dir, processed_dir)
        if result is None:
            print("FAIL (no raw files or all empty)")
            failed_dates.append(ymd)
        else:
            # Quick stats
            try:
                n = len(pd.read_parquet(result, columns=["DocumentIdentifier"]))
            except Exception:
                n = -1
            print(f"OK  →  {result.name}  ({n:,} articles)")
            total_ok += 1

    print(f"\n=== SUMMARY ===")
    print(f"processed : {total_ok}")
    print(f"skipped   : {total_skip}")
    print(f"failed    : {len(failed_dates)}")
    if failed_dates:
        print("failed dates:", ", ".join(failed_dates))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Merge raw GKG slots into daily Parquet files")
    p.add_argument("--start-date",     default="2025-01-01",        help="YYYY-MM-DD")
    p.add_argument("--end-date",       default="2025-12-31",        help="YYYY-MM-DD")
    p.add_argument("--raw-dir",        default="data/gkg_raw",      help="Raw slot CSV directory")
    p.add_argument("--processed-dir",  default="data/gkg_processed",help="Output Parquet directory")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run(
        start_date=args.start_date,
        end_date=args.end_date,
        raw_dir=Path(args.raw_dir),
        processed_dir=Path(args.processed_dir),
    )


if __name__ == "__main__":
    main()
