"""Fill missing daily GKG Parquet files from Google BigQuery.

Use when GDELT's public zip server returns 404 for specific dates (e.g. the
2025-06-15..2025-07-01 gap). Queries the partitioned GKG table and writes
gkg_processed_YYYYMMDD.parquet files in the same schema as preprocess_gkg.py.

Requires Google Cloud credentials with BigQuery access:
  gcloud auth application-default login
  # or set GOOGLE_APPLICATION_CREDENTIALS to a service-account JSON key

Install optional deps:
  uv sync --extra bigquery

Usage:
  python -m scripts.fill_gkg_bigquery \\
    --start-date 2025-06-15 \\
    --end-date   2025-07-01 \\
    --processed-dir data/gkg_processed
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import List, Optional

import pandas as pd

from scripts.preprocess_gkg import generate_dates, normalize_gkg_dataframe

BQ_TABLE = "gdelt-bq.gdeltv2.gkg_partitioned"
BQ_QUERY = """
SELECT
  CAST(DATE AS STRING) AS SQLDATE,
  SourceCommonName,
  DocumentIdentifier,
  V2Themes,
  V2Locations,
  V2Tone AS V2Tone_raw,
  GCAM
FROM `{table}`
WHERE _PARTITIONTIME >= TIMESTAMP(@day_start)
  AND _PARTITIONTIME <  TIMESTAMP(@day_end)
  AND DATE >= @date_lo
  AND DATE <  @date_hi
"""


def _require_bigquery():
    try:
        from google.cloud import bigquery
    except ImportError as exc:
        raise SystemExit(
            "google-cloud-bigquery is not installed.\n"
            "Run: uv sync --extra bigquery"
        ) from exc
    return bigquery


def _day_bounds(day: dt.date) -> tuple[str, str, int, int]:
    ymd = day.strftime("%Y%m%d")
    next_day = day + dt.timedelta(days=1)
    return (
        day.isoformat(),
        next_day.isoformat(),
        int(f"{ymd}000000"),
        int(f"{next_day.strftime('%Y%m%d')}000000"),
    )


def _make_client(project: Optional[str]):
    bigquery = _require_bigquery()
    try:
        return bigquery.Client(project=project) if project else bigquery.Client()
    except Exception as exc:
        if "DefaultCredentialsError" in type(exc).__name__ or "credentials" in str(exc).lower():
            raise SystemExit(
                "Google Cloud credentials not found.\n"
                "One-time setup:\n"
                "  1. Create a GCP project and enable BigQuery API\n"
                "  2. Run: gcloud auth application-default login\n"
                "     (or set GOOGLE_APPLICATION_CREDENTIALS to a service-account JSON key)\n"
                "  3. Re-run: python main.py fill-bq --start-date 2025-06-15 --end-date 2025-07-01"
            ) from exc
        raise


def fetch_day_from_bigquery(client, day: dt.date) -> Optional[pd.DataFrame]:
    """Download and normalize one day of GKG rows from BigQuery."""
    bigquery = _require_bigquery()
    day_start, day_end, date_lo, date_hi = _day_bounds(day)
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("day_start", "STRING", day_start),
            bigquery.ScalarQueryParameter("day_end", "STRING", day_end),
            bigquery.ScalarQueryParameter("date_lo", "INT64", date_lo),
            bigquery.ScalarQueryParameter("date_hi", "INT64", date_hi),
        ]
    )
    query = BQ_QUERY.format(table=BQ_TABLE)
    df = client.query(query, job_config=job_config).to_dataframe(
        create_bqstorage_client=False
    )
    if df.empty:
        return None

    normalized = normalize_gkg_dataframe(df)
    if normalized is None or normalized.empty:
        return None

    return (
        normalized
        .sort_values("SQLDATE")
        .drop_duplicates(subset=["DocumentIdentifier"], keep="last")
        .reset_index(drop=True)
    )


def write_day_parquet(df: pd.DataFrame, processed_dir: Path, day: dt.date) -> Path:
    processed_dir.mkdir(parents=True, exist_ok=True)
    out_path = processed_dir / f"gkg_processed_{day.strftime('%Y%m%d')}.parquet"
    df.to_parquet(out_path, index=False, compression="snappy")
    return out_path


def run(
    start_date: str,
    end_date: str,
    processed_dir: Path,
    project: Optional[str],
    dry_run: bool,
) -> None:
    client = _make_client(project)

    total_ok = 0
    total_skip = 0
    failed_dates: List[str] = []

    for day in generate_dates(start_date, end_date):
        ymd = day.strftime("%Y%m%d")
        out_path = processed_dir / f"gkg_processed_{ymd}.parquet"

        if out_path.exists():
            print(f"[{ymd}] SKIP (already exists)")
            total_skip += 1
            continue

        print(f"[{ymd}] bigquery ...", end=" ", flush=True)
        if dry_run:
            bigquery = _require_bigquery()
            day_start, day_end, date_lo, date_hi = _day_bounds(day)
            count_query = f"""
            SELECT COUNT(*) AS n
            FROM `{BQ_TABLE}`
            WHERE _PARTITIONTIME >= TIMESTAMP(@day_start)
              AND _PARTITIONTIME <  TIMESTAMP(@day_end)
              AND DATE >= @date_lo
              AND DATE <  @date_hi
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("day_start", "STRING", day_start),
                    bigquery.ScalarQueryParameter("day_end", "STRING", day_end),
                    bigquery.ScalarQueryParameter("date_lo", "INT64", date_lo),
                    bigquery.ScalarQueryParameter("date_hi", "INT64", date_hi),
                ]
            )
            n = int(client.query(count_query, job_config=job_config).to_dataframe().iloc[0, 0])
            print(f"DRY-RUN  {n:,} rows available")
            total_ok += 1 if n > 0 else 0
            if n == 0:
                failed_dates.append(ymd)
            continue

        try:
            df = fetch_day_from_bigquery(client, day)
        except Exception as exc:
            print(f"FAIL ({exc})")
            failed_dates.append(ymd)
            continue

        if df is None:
            print("FAIL (no rows in BigQuery)")
            failed_dates.append(ymd)
            continue

        out_path = write_day_parquet(df, processed_dir, day)
        print(f"OK  →  {out_path.name}  ({len(df):,} articles)")
        total_ok += 1

    print(f"\n=== SUMMARY ===")
    print(f"filled    : {total_ok}")
    print(f"skipped   : {total_skip}")
    print(f"failed    : {len(failed_dates)}")
    if failed_dates:
        print("failed dates:", ", ".join(failed_dates))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fill missing daily GKG Parquet files from Google BigQuery"
    )
    p.add_argument("--start-date",    default="2025-06-15", help="YYYY-MM-DD")
    p.add_argument("--end-date",      default="2025-07-01", help="YYYY-MM-DD")
    p.add_argument("--processed-dir", default="data/gkg_processed", help="Output Parquet directory")
    p.add_argument("--project",       default=None, help="GCP project ID (optional)")
    p.add_argument("--dry-run",       action="store_true", help="Count rows only; do not write Parquet")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run(
        start_date=args.start_date,
        end_date=args.end_date,
        processed_dir=Path(args.processed_dir),
        project=args.project,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
