"""Sync GPR and corridor CSV outputs into PostgreSQL."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from gpr_index.scripts.paths import OUTPUT_DIR

from news_dataset import db


def _parse_day(value):
    return pd.to_datetime(value).date()


def sync_gpr_csv(csv_path: Path | None = None) -> int:
    path = Path(csv_path or OUTPUT_DIR / "gpr_daily_index.csv")
    if not path.exists():
        raise FileNotFoundError(f"GPR daily index not found: {path}")
    frame = pd.read_csv(path, parse_dates=["date"])
    rows = []
    for _, row in frame.iterrows():
        if pd.isna(row.get("gpr_index")):
            continue
        rows.append(
            (
                _parse_day(row["date"]),
                float(row["gpr_index"]),
                float(row["gpr_7ma"]) if pd.notna(row.get("gpr_7ma")) else None,
                float(row["gpr_30ma"]) if pd.notna(row.get("gpr_30ma")) else None,
                float(row["gpr_acts_index"]) if pd.notna(row.get("gpr_acts_index")) else None,
                float(row["gpr_threats_index"]) if pd.notna(row.get("gpr_threats_index")) else None,
                int(row["total_articles"]) if pd.notna(row.get("total_articles")) else None,
                float(row["positive_share"]) if pd.notna(row.get("positive_share")) else None,
                datetime.now(timezone.utc),
            )
        )
    return db.upsert_gpr_daily(rows)


def sync_corridor_csv(csv_path: Path | None = None) -> int:
    path = Path(csv_path or OUTPUT_DIR / "gpr_corridor_daily.csv")
    if not path.exists():
        raise FileNotFoundError(f"Corridor daily index not found: {path}")
    frame = pd.read_csv(path, parse_dates=["date"])
    rows = []
    for _, row in frame.iterrows():
        rows.append(
            (
                _parse_day(row["date"]),
                str(row["corridor"]),
                str(row.get("corridor_name") or row["corridor"]),
                float(row["corridor_risk"]) if pd.notna(row.get("corridor_risk")) else None,
                float(row["threat_index"]) if pd.notna(row.get("threat_index")) else None,
                float(row["energy_risk"]) if pd.notna(row.get("energy_risk")) else None,
                float(row["goods_risk"]) if pd.notna(row.get("goods_risk")) else None,
                float(row["raw_ratio"]) if pd.notna(row.get("raw_ratio")) else None,
                datetime.now(timezone.utc),
            )
        )
    return db.upsert_corridor_daily(rows)


def sync_all(gpr_csv: Path | None = None, corridor_csv: Path | None = None) -> dict[str, int]:
    gpr_count = sync_gpr_csv(gpr_csv)
    corridor_count = sync_corridor_csv(corridor_csv)
    return {"gpr_rows": gpr_count, "corridor_rows": corridor_count}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpr-csv", type=Path, default=OUTPUT_DIR / "gpr_daily_index.csv")
    parser.add_argument("--corridor-csv", type=Path, default=OUTPUT_DIR / "gpr_corridor_daily.csv")
    args = parser.parse_args()
    counts = sync_all(args.gpr_csv, args.corridor_csv)
    print(f"[to_db] upserted gpr={counts['gpr_rows']:,} corridor={counts['corridor_rows']:,}")
    db.log_pipeline_run("to_db", "ok", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
