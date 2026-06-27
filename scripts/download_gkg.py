"""Download raw GDELT GKG 15-minute slot files.

Downloads all 96 fifteen-minute GKG files per day from the GDELT v2 server
into data/gkg_raw/ as YYYYMMDDHHMMSS.gkg.csv files.

Skips files already on disk — safe to re-run after interruption.

Usage:
  python -m scripts.download_gkg \\
    --start-date 2025-01-01 \\
    --end-date   2025-12-31 \\
    --raw-dir    data/gkg_raw \\
    --delay-seconds 0.3
"""

from __future__ import annotations

import argparse
import datetime as dt
import time
import zipfile
from pathlib import Path
from typing import Iterable, List, Tuple

import requests


BASE_URL = "http://data.gdeltproject.org/gdeltv2"
ALL_TIME_SLOTS = tuple(
    f"{hour:02d}{minute:02d}"
    for hour in range(24)
    for minute in (0, 15, 30, 45)
)


def generate_dates(start_date: str, end_date: str) -> Iterable[dt.date]:
    """Yield every date in the inclusive range."""
    start = dt.datetime.strptime(start_date, "%Y-%m-%d").date()
    end   = dt.datetime.strptime(end_date,   "%Y-%m-%d").date()
    if end < start:
        raise ValueError("end_date must be >= start_date")
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)


def _build_url(day: dt.date, hhmm: str) -> str:
    return f"{BASE_URL}/{day.strftime('%Y%m%d')}{hhmm}00.gkg.csv.zip"


def _raw_csv_path(raw_dir: Path, day: dt.date, hhmm: str) -> Path:
    return raw_dir / f"{day.strftime('%Y%m%d')}{hhmm}00.gkg.csv"


def _download_file(url: str, zip_path: Path, timeout: int = 120) -> bool:
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code != 200:
            return False
        zip_path.write_bytes(resp.content)
        return True
    except Exception:
        return False


def _extract_zip(zip_path: Path, raw_dir: Path, delete_zip: bool = True) -> bool:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            if not names:
                return False
            zf.extract(names[0], path=raw_dir)
    except Exception:
        return False
    finally:
        if delete_zip and zip_path.exists():
            zip_path.unlink(missing_ok=True)
    return True


def download_slot(
    day: dt.date,
    hhmm: str,
    raw_dir: Path,
    delay_seconds: float,
    keep_zip: bool = False,
) -> Tuple[bool, bool]:
    """Download one 15-minute slot if not already on disk.

    Returns (downloaded, available):
      (True,  True)  → newly downloaded
      (False, True)  → already existed, skipped
      (False, False) → not available on GDELT server
    """
    csv_path = _raw_csv_path(raw_dir, day, hhmm)
    if csv_path.exists():
        return False, True

    url      = _build_url(day, hhmm)
    zip_path = raw_dir / f"{day.strftime('%Y%m%d')}{hhmm}00.gkg.csv.zip"

    ok = _download_file(url, zip_path)
    if not ok:
        zip_path.unlink(missing_ok=True)
        time.sleep(delay_seconds)
        return False, False

    extracted = _extract_zip(zip_path, raw_dir, delete_zip=not keep_zip)
    time.sleep(delay_seconds)
    return (True, True) if extracted else (False, False)


def run(
    start_date: str,
    end_date: str,
    raw_dir: Path,
    delay_seconds: float,
    keep_zip: bool,
) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    total_downloaded = 0
    total_missing    = 0

    for day in generate_dates(start_date, end_date):
        ymd = day.strftime("%Y%m%d")
        day_downloaded = 0
        day_missing    = 0

        for hhmm in ALL_TIME_SLOTS:
            downloaded, available = download_slot(day, hhmm, raw_dir, delay_seconds, keep_zip)
            if downloaded:
                day_downloaded += 1
                total_downloaded += 1
            elif not available:
                day_missing    += 1
                total_missing  += 1

        raw_count = len(list(raw_dir.glob(f"{ymd}*.gkg.csv")))
        print(f"[{ymd}] +{day_downloaded} new  {raw_count}/96 present  {day_missing} missing")

    print(f"\n=== SUMMARY ===")
    print(f"total downloaded : {total_downloaded}")
    print(f"total missing    : {total_missing} (not available on GDELT)")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download raw GDELT GKG slot files")
    p.add_argument("--start-date",     default="2025-01-01", help="YYYY-MM-DD")
    p.add_argument("--end-date",       default="2025-12-31", help="YYYY-MM-DD")
    p.add_argument("--raw-dir",        default="data/gkg_raw", help="Output directory for raw CSVs")
    p.add_argument("--delay-seconds",  type=float, default=0.3, help="Delay between HTTP requests")
    p.add_argument("--keep-zip",       action="store_true", help="Keep ZIP files after extraction")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run(
        start_date=args.start_date,
        end_date=args.end_date,
        raw_dir=Path(args.raw_dir),
        delay_seconds=args.delay_seconds,
        keep_zip=args.keep_zip,
    )


if __name__ == "__main__":
    main()
