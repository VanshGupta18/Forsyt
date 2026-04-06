"""Download and preprocess daily-sampled GDELT GKG for GPR pipeline use.

Rules implemented:
- Date range: configurable (default 2023-01-01 to 2026-03-24)
- Try one snapshot per day, first successful among 0000/0015/0030/0045
- Save raw files under data/gkg_raw/
- Save processed day-level files under data/gkg_processed/
"""

from __future__ import annotations

import argparse
import datetime as dt
import time
import zipfile
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import pandas as pd
import requests


BASE_URL = "http://data.gdeltproject.org/gdeltv2"
TIME_CANDIDATES = ("0000", "0015", "0030", "0045")


def generate_dates(start_date: str, end_date: str) -> Iterable[dt.date]:
    """Yield inclusive date range."""
    start = dt.datetime.strptime(start_date, "%Y-%m-%d").date()
    end = dt.datetime.strptime(end_date, "%Y-%m-%d").date()
    if end < start:
        raise ValueError("end_date must be >= start_date")

    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)


def build_url(day: dt.date, hhmm: str) -> str:
    """Build GKG zip URL for a date and HHMM candidate."""
    ymd = day.strftime("%Y%m%d")
    return f"{BASE_URL}/{ymd}{hhmm}00.gkg.csv.zip"


def download_file(url: str, zip_path: Path, timeout: int = 60) -> bool:
    """Download URL to zip_path. Return True on success."""
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code != 200:
            return False
        zip_path.write_bytes(resp.content)
        return True
    except Exception:
        return False


def extract_file(zip_path: Path, raw_dir: Path, delete_zip: bool = True) -> Optional[Path]:
    """Extract ZIP into raw_dir and return extracted CSV path."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            if not names:
                return None
            inner_name = names[0]
            zf.extract(inner_name, path=raw_dir)
            extracted_path = raw_dir / inner_name
    except Exception:
        return None

    if delete_zip and zip_path.exists():
        zip_path.unlink(missing_ok=True)

    return extracted_path


def prepare_text(themes: str, url: str = "") -> str:
    """Create pipeline-ready proxy text from themes and optional URL signal."""
    themes_text = "" if pd.isna(themes) else str(themes)
    themes_text = themes_text.replace(";", " ").replace(",", " ")
    themes_text = " ".join(themes_text.split())

    proxy_text = themes_text if themes_text else str(url or "")
    words = proxy_text.split()
    return " ".join(words[:400])


def process_gkg(csv_path: Path, processed_dir: Path) -> Optional[Path]:
    """Load one raw GKG CSV, keep required fields, clean, and save processed CSV."""
    if not csv_path.exists():
        return None

    # GKG 2.1 selected fields by index:
    # 1=DATE, 4=DocumentIdentifier, 8=V2Themes, 15=V2Tone
    usecols = [1, 4, 8, 15]
    names = ["SQLDATE", "DocumentIdentifier", "V2Themes", "V2Tone"]

    df: Optional[pd.DataFrame] = None
    read_errors: List[str] = []
    for enc in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(
                csv_path,
                sep="\t",
                header=None,
                usecols=usecols,
                names=names,
                dtype=str,
                on_bad_lines="skip",
                engine="python",
                encoding=enc,
            )
            break
        except Exception as exc:
            read_errors.append(f"{enc}: {exc}")

    if df is None:
        print(f"[WARN] process failed for {csv_path.name}: {' | '.join(read_errors)}")
        return None

    df["SQLDATE"] = pd.to_datetime(df["SQLDATE"], format="%Y%m%d%H%M%S", errors="coerce")
    df["V2Tone"] = pd.to_numeric(df["V2Tone"], errors="coerce")

    df["DocumentIdentifier"] = df["DocumentIdentifier"].fillna("").astype(str)
    df["V2Themes"] = df["V2Themes"].fillna("").astype(str)
    df["V2Tone"] = df["V2Tone"].fillna(0.0)

    # Keep only valid datetime rows.
    df = df.dropna(subset=["SQLDATE"]).reset_index(drop=True)
    if df.empty:
        return None

    df["processed_text"] = df.apply(
        lambda x: prepare_text(x.get("V2Themes", ""), x.get("DocumentIdentifier", "")),
        axis=1,
    )

    processed_dir.mkdir(parents=True, exist_ok=True)
    day_str = df["SQLDATE"].dt.strftime("%Y%m%d").iloc[0]
    out_path = processed_dir / f"gkg_processed_{day_str}.csv"
    df.to_csv(out_path, index=False)
    return out_path


def _find_existing_raw_csv_for_day(raw_dir: Path, day: dt.date) -> Optional[Path]:
    ymd = day.strftime("%Y%m%d")
    matches = sorted(raw_dir.glob(f"{ymd}*.gkg.csv"))
    return matches[0] if matches else None


def run(
    start_date: str,
    end_date: str,
    raw_dir: Path,
    processed_dir: Path,
    delay_seconds: float,
    delete_zip: bool,
) -> Tuple[int, int, List[str]]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    total_downloaded = 0
    total_processed = 0
    failed_dates: List[str] = []

    for day in generate_dates(start_date, end_date):
        ymd = day.strftime("%Y%m%d")
        out_processed = processed_dir / f"gkg_processed_{ymd}.csv"

        print(f"[DATE] {ymd}")

        if out_processed.exists():
            print(f"  [SKIP] already processed: {out_processed.name}")
            continue

        existing_csv = _find_existing_raw_csv_for_day(raw_dir, day)
        extracted_csv: Optional[Path] = existing_csv

        if extracted_csv is None:
            found = False
            for hhmm in TIME_CANDIDATES:
                url = build_url(day, hhmm)
                zip_name = f"{ymd}{hhmm}00.gkg.csv.zip"
                zip_path = raw_dir / zip_name

                ok = download_file(url=url, zip_path=zip_path)
                if not ok:
                    print(f"  [TRY] fail {hhmm}")
                    time.sleep(delay_seconds)
                    continue

                extracted_csv = extract_file(zip_path=zip_path, raw_dir=raw_dir, delete_zip=delete_zip)
                if extracted_csv is None:
                    print(f"  [TRY] bad zip {hhmm}")
                    time.sleep(delay_seconds)
                    continue

                print(f"  [OK ] downloaded using {hhmm} -> {extracted_csv.name}")
                total_downloaded += 1
                found = True
                break

            if not found:
                print("  [FAIL] no snapshot available")
                failed_dates.append(ymd)
                continue
        else:
            print(f"  [SKIP] raw exists: {extracted_csv.name}")

        processed_path = process_gkg(csv_path=extracted_csv, processed_dir=processed_dir)
        if processed_path is None:
            print("  [FAIL] processing failed")
            failed_dates.append(ymd)
            continue

        print(f"  [OK ] processed -> {processed_path.name}")
        total_processed += 1
        time.sleep(delay_seconds)

    return total_downloaded, total_processed, failed_dates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download and preprocess daily-sampled GDELT GKG")
    parser.add_argument("--start-date", default="2023-01-01", help="YYYY-MM-DD")
    parser.add_argument("--end-date", default="2026-03-24", help="YYYY-MM-DD")
    parser.add_argument("--raw-dir", default="data/gkg_raw", help="Raw ZIP/CSV directory")
    parser.add_argument("--processed-dir", default="data/gkg_processed", help="Processed CSV directory")
    parser.add_argument("--delay-seconds", type=float, default=0.25, help="Delay between requests")
    parser.add_argument(
        "--keep-zip",
        action="store_true",
        help="Keep downloaded ZIP files (default deletes after extraction)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    downloaded, processed, failed = run(
        start_date=args.start_date,
        end_date=args.end_date,
        raw_dir=Path(args.raw_dir),
        processed_dir=Path(args.processed_dir),
        delay_seconds=args.delay_seconds,
        delete_zip=not args.keep_zip,
    )

    print("\n=== SUMMARY ===")
    print(f"total files downloaded: {downloaded}")
    print(f"total processed files: {processed}")
    print(f"failed dates count: {len(failed)}")
    if failed:
        print("failed dates:", ", ".join(failed))


if __name__ == "__main__":
    main()
