"""Build daily geopolitical-risk indices for India-relevant trade corridors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .corridors import CORRIDORS, tag_corridors
from .gkg_gpr_pipeline import (
    CHECKPOINT_INTERVAL,
    GPR_POSITIVE_THRESHOLD,
    _apply_index_transform,
    list_processed_files,
    score_articles,
)
from .paths import GKG_PROCESSED_DIR, OUTPUT_DIR

HIT_COLUMNS = ["date", "corridor", "gpr_score", "event_category", "gpr_type"]
CHECKPOINT_DIR = "_corridor_checkpoint"


def corridor_article_hits(scored: pd.DataFrame, date_val: pd.Timestamp) -> pd.DataFrame:
    """Return one slim row per positive article/corridor match."""
    positive = scored.loc[
        scored["gpr_score"] > GPR_POSITIVE_THRESHOLD,
        ["V2Locations", "gpr_score", "event_category", "gpr_type"],
    ].copy()
    if positive.empty:
        return pd.DataFrame(columns=HIT_COLUMNS)

    # Series.map + explode keeps the DataFrame path vectorized and avoids
    # Python-level row iteration while preserving the shared pure tagger.
    locations = positive["V2Locations"].fillna("").astype(str)
    valid = locations.str.contains("#", regex=False)
    positive["corridor"] = pd.Series(
        [[] for _ in range(len(positive))], index=positive.index, dtype=object
    )
    positive.loc[valid, "corridor"] = locations.loc[valid].map(tag_corridors)
    hits = positive.explode("corridor").dropna(subset=["corridor"])
    if hits.empty:
        return pd.DataFrame(columns=HIT_COLUMNS)
    hits.insert(0, "date", pd.to_datetime(date_val))
    return hits[HIT_COLUMNS].reset_index(drop=True)


def aggregate_corridor_day(
    scored: pd.DataFrame,
    date_val: pd.Timestamp,
    total_articles: int | None = None,
) -> pd.DataFrame:
    """Aggregate one scored day, retaining the parent index denominator."""
    total = len(scored) if total_articles is None else int(total_articles)
    positive_count = int((scored["gpr_score"] > GPR_POSITIVE_THRESHOLD).sum())
    hits = corridor_article_hits(scored, date_val)
    matched_count = 0
    if positive_count:
        matched_count = int(
            scored.loc[scored["gpr_score"] > GPR_POSITIVE_THRESHOLD, "V2Locations"]
            .fillna("")
            .astype(str)
            .map(tag_corridors)
            .map(bool)
            .sum()
        )
    return _aggregate_hits_day(
        hits,
        pd.to_datetime(date_val),
        total,
        positive_count,
        matched_count,
    )


def _aggregate_hits_day(
    hits: pd.DataFrame,
    date_val: pd.Timestamp,
    total_articles: int,
    positive_articles: int,
    matched_positive_articles: int,
) -> pd.DataFrame:
    grouped = (
        hits.groupby("corridor", as_index=False)
        .agg(gpr_sum=("gpr_score", "sum"), corridor_hit_count=("gpr_score", "size"))
        if not hits.empty
        else pd.DataFrame(columns=["corridor", "gpr_sum", "corridor_hit_count"])
    )
    base = pd.DataFrame({"corridor": list(CORRIDORS)})
    out = base.merge(grouped, on="corridor", how="left").fillna(
        {"gpr_sum": 0.0, "corridor_hit_count": 0}
    )
    out.insert(0, "date", date_val)
    out["corridor_hit_count"] = out["corridor_hit_count"].astype(int)
    out["total_articles"] = int(total_articles)
    out["positive_articles"] = int(positive_articles)
    out["matched_positive_articles"] = int(matched_positive_articles)
    out["raw_ratio"] = (
        out["gpr_sum"] / total_articles if total_articles > 0 else 0.0
    )
    return out


def aggregate_corridor_hits(
    hits: pd.DataFrame,
    daily_totals: pd.DataFrame,
) -> pd.DataFrame:
    """Re-aggregate saved slim hits without rescanning source Parquet files."""
    frames = []
    grouped_hits = {
        pd.Timestamp(day): frame
        for day, frame in hits.assign(date=pd.to_datetime(hits["date"])).groupby("date")
    }
    for row in daily_totals.itertuples(index=False):
        day = pd.Timestamp(row.date)
        frames.append(
            _aggregate_hits_day(
                grouped_hits.get(day, pd.DataFrame(columns=HIT_COLUMNS)),
                day,
                int(row.total_articles),
                int(row.positive_articles),
                int(row.matched_positive_articles),
            )
        )
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def normalize_corridor_index(
    corridor_df: pd.DataFrame,
    baseline_start: str,
    baseline_end: str,
) -> pd.DataFrame:
    """Normalize each threat series and apply separate exposure channels."""
    out = corridor_df.copy()
    out["date"] = pd.to_datetime(out["date"])
    start, end = pd.to_datetime(baseline_start), pd.to_datetime(baseline_end)

    def normalize(group: pd.DataFrame) -> pd.DataFrame:
        group = group.sort_values("date").copy()
        baseline = group.loc[
            group["date"].between(start, end), "raw_ratio"
        ]
        scale = float(baseline.mean()) if not baseline.empty else float(group["raw_ratio"].mean())
        if scale > 0:
            group["threat_index"] = _apply_index_transform(group["raw_ratio"] / scale)
        else:
            group["threat_index"] = 0.0
        return group

    parts: list[pd.DataFrame] = []
    for corridor, group in out.groupby("corridor", sort=False):
        normalized = normalize(group)
        normalized["corridor"] = corridor
        parts.append(normalized)
    out = pd.concat(parts, ignore_index=True) if parts else out
    out["corridor_name"] = out["corridor"].map(lambda value: CORRIDORS[value]["name"])
    out["energy_exposure"] = out["corridor"].map(
        lambda value: CORRIDORS[value]["energy_exposure"]
    )
    out["goods_exposure"] = out["corridor"].map(
        lambda value: CORRIDORS[value]["goods_exposure"]
    )
    out["energy_risk"] = (out["threat_index"] * out["energy_exposure"]).clip(0, 100)
    out["goods_risk"] = (out["threat_index"] * out["goods_exposure"]).clip(0, 100)
    out["corridor_risk"] = out[["energy_risk", "goods_risk"]].max(axis=1)
    return out.sort_values(["date", "corridor"]).reset_index(drop=True)


def reaggregate_saved_hits(
    output_dir: Path,
    baseline_start: str,
    baseline_end: str,
) -> pd.DataFrame:
    """Rebuild the daily output from saved hits and denominator metadata."""
    hits_path = output_dir / "corridor_article_hits.parquet"
    daily_path = output_dir / "gpr_corridor_daily.csv"
    if not hits_path.exists() or not daily_path.exists():
        raise FileNotFoundError(
            "corridor_article_hits.parquet and gpr_corridor_daily.csv are required"
        )
    hits = pd.read_parquet(hits_path)
    prior = pd.read_csv(daily_path, parse_dates=["date"])
    totals = (
        prior.groupby("date", as_index=False)
        [["total_articles", "positive_articles", "matched_positive_articles"]]
        .first()
    )
    daily = normalize_corridor_index(
        aggregate_corridor_hits(hits, totals), baseline_start, baseline_end
    )
    daily.to_csv(daily_path, index=False)
    return daily


def _checkpoint_dir(output_dir: Path) -> Path:
    return output_dir / CHECKPOINT_DIR


def _save_checkpoint(
    output_dir: Path,
    last_idx: int,
    pending_hits: list[pd.DataFrame],
    daily_totals: list[dict],
) -> None:
    checkpoint = _checkpoint_dir(output_dir)
    checkpoint.mkdir(parents=True, exist_ok=True)
    if pending_hits:
        pd.concat(pending_hits, ignore_index=True).to_parquet(
            checkpoint / f"hits_{last_idx:04d}.parquet",
            index=False,
            compression="snappy",
        )
    pd.DataFrame(daily_totals).to_parquet(checkpoint / "daily_totals.parquet", index=False)
    (checkpoint / "state.json").write_text(json.dumps({"last_idx": last_idx}))


def _load_checkpoint(output_dir: Path) -> tuple[int, list[dict]]:
    checkpoint = _checkpoint_dir(output_dir)
    state_path = checkpoint / "state.json"
    totals_path = checkpoint / "daily_totals.parquet"
    if not state_path.exists() or not totals_path.exists():
        return -1, []
    state = json.loads(state_path.read_text())
    return int(state["last_idx"]), pd.read_parquet(totals_path).to_dict("records")


def _clear_checkpoint(output_dir: Path) -> None:
    checkpoint = _checkpoint_dir(output_dir)
    if checkpoint.exists():
        for path in checkpoint.iterdir():
            path.unlink(missing_ok=True)
        checkpoint.rmdir()


def run(
    processed_dir: Path,
    output_dir: Path,
    start_date: str,
    end_date: str,
    baseline_start: str = "",
    baseline_end: str = "",
    resume: bool = False,
    dates: list[str] | None = None,
) -> None:
    """Score source Parquets once, saving slim hits and the daily index."""
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_start = baseline_start or start_date
    baseline_end = baseline_end or end_date
    files = list_processed_files(processed_dir, start_date, end_date)
    if dates:
        selected_dates = {pd.Timestamp(value).normalize() for value in dates}
        files = [(date, path) for date, path in files if date.normalize() in selected_dates]
    if not files:
        raise FileNotFoundError(
            f"No Parquet files in {processed_dir} for {start_date}..{end_date}"
        )
    if not resume:
        _clear_checkpoint(output_dir)

    start_idx = 0
    daily_totals: list[dict] = []
    if resume:
        last_idx, daily_totals = _load_checkpoint(output_dir)
        start_idx = last_idx + 1
        print(f"[CORRIDOR] RESUME from day {start_idx + 1}/{len(files)}")

    pending_hits: list[pd.DataFrame] = []
    for idx in range(start_idx, len(files)):
        date_val, path = files[idx]
        try:
            source = pd.read_parquet(path)
        except Exception as exc:
            print(f"[{date_val:%Y%m%d}] FAIL ({exc})", flush=True)
            continue
        if source.empty:
            print(f"[{date_val:%Y%m%d}] SKIP (empty)", flush=True)
            continue
        scored = score_articles(source)
        hits = corridor_article_hits(scored, date_val)
        positive = scored["gpr_score"] > GPR_POSITIVE_THRESHOLD
        matched = (
            scored.loc[positive, "V2Locations"]
            .fillna("")
            .astype(str)
            .map(tag_corridors)
            .astype(bool)
        )
        matched_count = int(matched.sum()) if len(matched) else 0
        daily_totals.append(
            {
                "date": date_val,
                "total_articles": len(scored),
                "positive_articles": int(positive.sum()),
                "matched_positive_articles": matched_count,
            }
        )
        if not hits.empty:
            pending_hits.append(hits)

        print(
            f"[{date_val:%Y%m%d}] total={len(scored):,} "
            f"positive={int(positive.sum()):,} matched={matched_count:,} "
            f"hits={len(hits):,}",
            flush=True,
        )

        if (idx + 1) % CHECKPOINT_INTERVAL == 0 or idx == len(files) - 1:
            _save_checkpoint(output_dir, idx, pending_hits, daily_totals)
            pending_hits = []
            print(f"[CORRIDOR] {idx + 1}/{len(files)} (checkpoint saved)")

    checkpoint_hits = sorted(_checkpoint_dir(output_dir).glob("hits_*.parquet"))
    hits = (
        pd.concat((pd.read_parquet(path) for path in checkpoint_hits), ignore_index=True)
        if checkpoint_hits
        else pd.DataFrame(columns=HIT_COLUMNS)
    )
    totals = pd.DataFrame(daily_totals)
    daily = aggregate_corridor_hits(hits, totals)
    daily = normalize_corridor_index(daily, baseline_start, baseline_end)
    hits.to_parquet(
        output_dir / "corridor_article_hits.parquet",
        index=False,
        compression="snappy",
    )
    daily.to_csv(output_dir / "gpr_corridor_daily.csv", index=False)
    _clear_checkpoint(output_dir)
    print(f"[CORRIDOR] Saved {len(hits):,} hits and {len(daily):,} daily rows")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", default=str(GKG_PROCESSED_DIR))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--start-date", default="2025-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--baseline-start", default=None)
    parser.add_argument("--baseline-end", default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--dates",
        nargs="+",
        help="Optional specific YYYY-MM-DD days inside the start/end range",
    )
    parser.add_argument(
        "--from-hits",
        action="store_true",
        help="Rebuild the daily CSV from saved slim hits without rescoring source data",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.from_hits:
        reaggregate_saved_hits(
            Path(args.output_dir),
            args.baseline_start or args.start_date,
            args.baseline_end or args.end_date,
        )
        return
    run(
        processed_dir=Path(args.processed_dir),
        output_dir=Path(args.output_dir),
        start_date=args.start_date,
        end_date=args.end_date,
        baseline_start=args.baseline_start or args.start_date,
        baseline_end=args.baseline_end or args.end_date,
        resume=args.resume,
        dates=args.dates,
    )


if __name__ == "__main__":
    main()
