"""Build a daily GPR history directly from GDELT Events files.

This script downloads GDELT 2.0 daily Events CSVs from the public GDELT
server, runs the small-sample GPR pipeline from `ingestion.gdelt_gpr_sample`
for each day, and writes out a daily GPR history CSV.

It is intended for experimentation and backtesting, not production use.

Usage (example):

    python -m scripts.build_gdelt_gpr_history \
        --start-date 2026-03-01 \
        --end-date   2026-03-05 \
        --out-csv    data/gpr_daily_from_gdelt.csv \
        --india-only

For a full history (be careful: many GB of data):

    python -m scripts.build_gdelt_gpr_history \
        --start-date 2015-01-01 \
        --end-date   2026-03-26 \
        --out-csv    data/gpr_daily_from_gdelt.csv \
        --india-only

"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
import zipfile
import shutil

from ingestion.gdelt_gpr_sample import (
    SQLDATE_COL,
    load_gdelt_events,
    filter_conflict_events,
    deduplicate_events,
    compute_risk_scores,
    filter_india_events,
    aggregate_daily_gpr,
)


GDELT_EVENTS_BASE_URL = "http://data.gdeltproject.org/events"


@dataclass
class Config:
    start_date: date
    end_date: date
    out_csv: Path
    events_dir: Path
    india_only: bool = True


def download_gdelt_events_for_date(target_date: date, events_dir: Path) -> Optional[Path]:
    """Download and unpack the GDELT daily Events CSV for a given date.

    Returns the path to the unzipped CSV, or None if download fails.
    """
    events_dir.mkdir(parents=True, exist_ok=True)

    datestr = target_date.strftime("%Y%m%d")
    zip_url = f"{GDELT_EVENTS_BASE_URL}/{datestr}.export.CSV.zip"

    zip_path = events_dir / f"{datestr}.export.CSV.zip"
    csv_path = events_dir / f"{datestr}.export.CSV"

    # Reuse existing CSV if already downloaded and extracted
    if csv_path.exists():
        return csv_path

    try:
        if not zip_path.exists():
            print(f"[INFO] Downloading GDELT events for {datestr} ...")
            resp = requests.get(zip_url, timeout=120)
            if resp.status_code != 200:
                print(f"[WARN] Failed to download {zip_url} (status={resp.status_code})")
                return None
            zip_path.write_bytes(resp.content)

        # Extract the single CSV from the ZIP
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            if not names:
                print(f"[WARN] ZIP file for {datestr} is empty")
                return None
            inner_name = names[0]
            with zf.open(inner_name, "r") as src, open(csv_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

        return csv_path

    except Exception as e:
        print(f"[ERROR] Error downloading/extracting events for {datestr}: {e}")
        return None


def compute_daily_gpr_for_date(target_date: date, cfg: Config) -> Optional[pd.DataFrame]:
    """Run the GPR pipeline for a single calendar date.

    Returns a one-row DataFrame with daily metrics for that date, or
    an empty/None if no relevant events were found.
    """
    csv_path = download_gdelt_events_for_date(target_date, cfg.events_dir)
    if csv_path is None:
        return None

    # 1. Load full day's events
    raw_df = load_gdelt_events(str(csv_path))
    if raw_df.empty:
        return None

    # 2. Conflict filter
    conflict_df = filter_conflict_events(raw_df)
    if conflict_df.empty:
        return None

    # 3. Deduplicate and score
    dedup_df = deduplicate_events(conflict_df)
    scored_df = compute_risk_scores(dedup_df)

    # 4. Optional India filter
    if cfg.india_only:
        processed_df = filter_india_events(scored_df)
        if processed_df.empty:
            return None
    else:
        processed_df = scored_df

    # 5. Daily aggregation
    daily_df = aggregate_daily_gpr(processed_df)
    if daily_df.empty:
        return None

    # Keep only the row for this specific date (in case the file contains spill-over days)
    datestr = target_date.strftime("%Y%m%d")
    daily_df = daily_df[daily_df[SQLDATE_COL].astype(str) == datestr]

    if daily_df.empty:
        return None

    return daily_df.reset_index(drop=True)


def daterange(start: date, end: date):
    """Inclusive date range generator."""
    cur = start
    while cur <= end:
        yield cur
        cur = cur + timedelta(days=1)


def build_history(cfg: Config) -> None:
    """Build/extend the GPR history CSV over the configured date range."""
    cfg.out_csv.parent.mkdir(parents=True, exist_ok=True)

    # Track which SQLDATE values we already have, to make the script resumable.
    existing_sql_dates = set()
    if cfg.out_csv.exists():
        try:
            existing = pd.read_csv(cfg.out_csv, usecols=[SQLDATE_COL])
            existing_sql_dates = set(existing[SQLDATE_COL].astype(str).tolist())
        except Exception:
            # If the existing file is malformed, ignore and start appending.
            pass

    new_rows = []

    for d in daterange(cfg.start_date, cfg.end_date):
        datestr = d.strftime("%Y%m%d")
        if datestr in existing_sql_dates:
            print(f"[SKIP] {datestr} already present in {cfg.out_csv}")
            continue

        print(f"[RUN ] Computing GPR for {datestr} (india_only={cfg.india_only})")

        daily_df = compute_daily_gpr_for_date(d, cfg)
        if daily_df is None or daily_df.empty:
            print(f"[INFO] No relevant events for {datestr}")
            continue

        new_rows.append(daily_df)

    if not new_rows:
        print("[INFO] No new rows to write.")
        return

    all_new = pd.concat(new_rows, ignore_index=True)

    # Append to CSV; write header only if file does not exist yet.
    header = not cfg.out_csv.exists()
    all_new.to_csv(cfg.out_csv, mode="a", index=False, header=header)

    print(f"[DONE] Appended {len(all_new)} daily rows to {cfg.out_csv}")


def parse_args(argv=None) -> Config:
    parser = argparse.ArgumentParser(description="Build GPR history from GDELT Events")
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--out-csv", required=True, help="Output CSV path for daily GPR history")
    parser.add_argument(
        "--events-dir",
        default="data/gdelt_events",
        help="Directory to cache downloaded GDELT events files (default: data/gdelt_events)",
    )
    parser.add_argument(
        "--india-only",
        action="store_true",
        help="If set, restrict to events where either actor country is IND",
    )

    args = parser.parse_args(argv)

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    if end_date < start_date:
        raise SystemExit("end-date must be >= start-date")

    return Config(
        start_date=start_date,
        end_date=end_date,
        out_csv=Path(args.out_csv),
        events_dir=Path(args.events_dir),
        india_only=bool(args.india_only),
    )


def main(argv=None) -> None:
    cfg = parse_args(argv)
    build_history(cfg)


if __name__ == "__main__":
    main(sys.argv[1:])
