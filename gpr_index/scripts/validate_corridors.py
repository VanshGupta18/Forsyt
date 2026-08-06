"""Validate corridor specificity, coverage, sampling, parity, and daily summary."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .corridors import CORRIDORS, tag_corridors
from .paths import GKG_PROCESSED_DIR, OUTPUT_DIR

KNOWN_CORRIDOR_EVENTS = [
    ("2025-05-07", "india_pakistan_attari", "Operation Sindoor"),
    ("2025-01-15", "red_sea_suez", "Red Sea / Houthi escalation"),
    ("2026-02-28", "strait_of_hormuz", "Hormuz closure"),
    ("2026-04-26", "instc_chabahar", "Chabahar waiver expiry"),
]


def _event_z_score(
    series: pd.Series,
    event_date: pd.Timestamp,
    window_days: int = 3,
    baseline_days: int = 30,
) -> float:
    window = series.loc[
        event_date - pd.Timedelta(days=window_days):
        event_date + pd.Timedelta(days=window_days)
    ]
    baseline = series.loc[
        event_date - pd.Timedelta(days=baseline_days):
        event_date - pd.Timedelta(days=window_days + 1)
    ]
    if window.empty or len(baseline) < 2 or baseline.std() == 0:
        return float("nan")
    return float((window.mean() - baseline.mean()) / baseline.std())


def check_event_response(
    corridor_df: pd.DataFrame,
    events: list[tuple[str, str, str]] | None = None,
) -> pd.DataFrame:
    """Measure each event corridor's response against its recent baseline."""
    data = corridor_df.copy()
    data["date"] = pd.to_datetime(data["date"])
    events = events or KNOWN_CORRIDOR_EVENTS
    rows = []
    for date_text, corridor, label in events:
        series = (
            data.loc[data["corridor"] == corridor]
            .set_index("date")["threat_index"]
            .sort_index()
        )
        z_score = _event_z_score(series, pd.Timestamp(date_text))
        rows.append(
            {
                "date": date_text,
                "event": label,
                "corridor": corridor,
                "z_score": z_score,
                "pass": "N/A" if np.isnan(z_score) else ("YES" if z_score > 1 else "NO"),
            }
        )
    return pd.DataFrame(rows)


def check_cross_corridor_discrimination(
    corridor_df: pd.DataFrame,
    events: list[tuple[str, str, str]] | None = None,
) -> pd.DataFrame:
    """Require an event's intended corridor to outrun unrelated corridors."""
    data = corridor_df.copy()
    data["date"] = pd.to_datetime(data["date"])
    events = events or KNOWN_CORRIDOR_EVENTS
    rows = []
    for date_text, target, label in events:
        event_date = pd.Timestamp(date_text)
        z_scores = {}
        for corridor, group in data.groupby("corridor"):
            series = group.set_index("date")["threat_index"].sort_index()
            z_scores[corridor] = _event_z_score(series, event_date)
        target_z = z_scores.get(target, float("nan"))
        others = [value for key, value in z_scores.items() if key != target and not np.isnan(value)]
        strongest_other = max(others) if others else float("nan")
        differential = target_z - strongest_other
        rows.append(
            {
                "date": date_text,
                "event": label,
                "target_corridor": target,
                "target_z": target_z,
                "strongest_other_z": strongest_other,
                "z_differential": differential,
                "pass": "N/A" if np.isnan(differential) else ("YES" if differential > 0 else "NO"),
            }
        )
    return pd.DataFrame(rows)


def check_parent_leakage(
    corridor_df: pd.DataFrame,
    parent_df: pd.DataFrame,
    threshold: float = 0.95,
) -> pd.DataFrame:
    """Flag corridor series that are effectively copies of the parent GPR."""
    corridors = corridor_df.copy()
    parent = parent_df.copy()
    corridors["date"] = pd.to_datetime(corridors["date"])
    parent["date"] = pd.to_datetime(parent["date"])
    rows = []
    for corridor, group in corridors.groupby("corridor"):
        merged = group[["date", "threat_index"]].merge(
            parent[["date", "gpr_index"]], on="date", how="inner"
        )
        correlation = float(merged["threat_index"].corr(merged["gpr_index"]))
        rows.append(
            {
                "corridor": corridor,
                "parent_correlation": correlation,
                "threshold": threshold,
                "pass": "NO" if correlation > threshold else "YES",
            }
        )
    return pd.DataFrame(rows)


def check_match_coverage(corridor_df: pd.DataFrame) -> pd.DataFrame:
    """Report the share of GPR-positive articles matching any corridor."""
    daily = (
        corridor_df.sort_values("date")
        .groupby("date", as_index=False)
        [["positive_articles", "matched_positive_articles"]]
        .first()
    )
    positive = int(daily["positive_articles"].sum())
    matched = int(daily["matched_positive_articles"].sum())
    coverage = matched / positive if positive else float("nan")
    return pd.DataFrame(
        [{
            "positive_articles": positive,
            "matched_positive_articles": matched,
            "coverage": coverage,
            "pass": "N/A" if np.isnan(coverage) else ("YES" if 0.01 <= coverage <= 0.80 else "NO"),
        }]
    )


def check_slot_sampling(
    full_df: pd.DataFrame,
    sampled_df: pd.DataFrame,
    max_relative_bias: float = 0.10,
) -> pd.DataFrame:
    """Compare daily raw ratios from full-slot and fixed-slot samples."""
    full = full_df.copy()
    sampled = sampled_df.copy()
    full["date"] = pd.to_datetime(full["date"])
    sampled["date"] = pd.to_datetime(sampled["date"])
    merged = full[["date", "corridor", "raw_ratio"]].merge(
        sampled[["date", "corridor", "raw_ratio"]],
        on=["date", "corridor"],
        suffixes=("_full", "_sampled"),
    )
    rows = []
    for corridor, group in merged.groupby("corridor"):
        full_mean = float(group["raw_ratio_full"].mean())
        sampled_mean = float(group["raw_ratio_sampled"].mean())
        relative_bias = (
            (sampled_mean - full_mean) / full_mean if full_mean > 0 else float("nan")
        )
        correlation = float(group["raw_ratio_full"].corr(group["raw_ratio_sampled"]))
        rows.append(
            {
                "corridor": corridor,
                "days": len(group),
                "full_mean_ratio": full_mean,
                "sampled_mean_ratio": sampled_mean,
                "relative_bias": relative_bias,
                "daily_correlation": correlation,
                "pass": (
                    "N/A"
                    if np.isnan(relative_bias)
                    else ("YES" if abs(relative_bias) <= max_relative_bias else "NO")
                ),
            }
        )
    return pd.DataFrame(rows)


def _read_locations(path: Path, sample_size: int | None = None) -> pd.Series:
    files = sorted(path.glob("*_processed_*.parquet")) if path.is_dir() else [path]
    parts = []
    remaining = sample_size
    for file_path in files:
        if file_path.suffix == ".csv":
            frame = pd.read_csv(file_path, usecols=["V2Locations"])
        else:
            frame = pd.read_parquet(file_path, columns=["V2Locations"])
        if remaining is not None:
            frame = frame.iloc[:remaining]
            remaining -= len(frame)
        parts.append(frame["V2Locations"].fillna("").astype(str))
        if remaining is not None and remaining <= 0:
            break
    if not parts:
        raise FileNotFoundError(f"No processed Parquet files found at {path}")
    return pd.concat(parts, ignore_index=True)


def _corridor_match_rates(locations: pd.Series) -> dict[str, float]:
    tags = locations.map(tag_corridors)
    denominator = len(tags)
    return {
        corridor: float(tags.map(lambda values: corridor in values).sum() / denominator)
        if denominator
        else float("nan")
        for corridor in CORRIDORS
    }


def check_news_path_parity(
    gdelt_path: Path,
    news_path: Path,
    sample_size: int | None = None,
) -> pd.DataFrame:
    """Run the shared tagger over GDELT and news-path V2Locations."""
    gdelt_rates = _corridor_match_rates(_read_locations(gdelt_path, sample_size))
    news_rates = _corridor_match_rates(_read_locations(news_path, sample_size))
    rows = []
    for corridor in CORRIDORS:
        gdelt_rate = gdelt_rates[corridor]
        news_rate = news_rates[corridor]
        ratio = news_rate / gdelt_rate if gdelt_rate > 0 else float("nan")
        rows.append(
            {
                "corridor": corridor,
                "gdelt_match_rate": gdelt_rate,
                "news_match_rate": news_rate,
                "news_to_gdelt_ratio": ratio,
                "pass": "N/A" if gdelt_rate == 0 else ("YES" if news_rate > 0 else "NO"),
            }
        )
    return pd.DataFrame(rows)


def summarize_corridor_daily(path: Path) -> pd.DataFrame:
    """Print per-corridor threat spread from gpr_corridor_daily.csv."""
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run `python main.py corridor` first")

    df = pd.read_csv(path, parse_dates=["date"])
    if df.empty:
        raise ValueError(f"{path} is empty")

    summary = (
        df.groupby("corridor", as_index=False)
        .agg(
            corridor_name=("corridor_name", "first"),
            days=("date", "nunique"),
            mean_threat=("threat_index", "mean"),
            std_threat=("threat_index", "std"),
            max_threat=("threat_index", "max"),
            mean_risk=("corridor_risk", "mean"),
            max_risk=("corridor_risk", "max"),
            mean_raw_ratio=("raw_ratio", "mean"),
        )
        .sort_values("mean_threat", ascending=False)
    )

    daily = (
        df.sort_values("date")
        .groupby("date", as_index=False)[["positive_articles", "matched_positive_articles"]]
        .first()
    )
    positive = int(daily["positive_articles"].sum())
    matched = int(daily["matched_positive_articles"].sum())
    coverage = matched / positive if positive else float("nan")

    print(f"File: {path}")
    print(f"Rows: {len(df):,}  Days: {df['date'].nunique():,}  Corridors: {df['corridor'].nunique()}")
    print(
        f"GPR-positive article coverage: {coverage:.1%} "
        f"({matched:,}/{positive:,} article-days)"
    )
    print("\nPer-corridor threat spread (mean threat index, descending):\n")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    return summary


def _synthetic_news_text(v2locations: str) -> str:
    names: list[str] = []
    for entry in str(v2locations).split(";"):
        parts = entry.split("#")
        if len(parts) >= 2 and parts[1].strip():
            names.append(parts[1].strip())
    return " ".join(dict.fromkeys(names))


def run_parity_smoke(
    gdelt_path: Path,
    sample_size: int,
    output_dir: Path,
) -> pd.DataFrame:
    """Approximate the news NLP path on a GDELT location sample."""
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from news_dataset.nlp.locations import extract_locations

    frame = pd.read_parquet(gdelt_path, columns=["V2Locations"]).head(sample_size)
    news_path = output_dir / "_parity_smoke_news_locations.parquet"
    news_locations = frame["V2Locations"].fillna("").astype(str).map(
        lambda locations: extract_locations(_synthetic_news_text(locations), "")
    )
    pd.DataFrame({"V2Locations": news_locations}).to_parquet(
        news_path, index=False, compression="snappy"
    )

    report = check_news_path_parity(gdelt_path, news_path, sample_size or None)
    validation_dir = output_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    out_path = validation_dir / "corridor_news_parity.csv"
    report.to_csv(out_path, index=False)
    print(report.to_string(index=False))
    print(f"\n[PARITY SMOKE] Saved {out_path}")
    return report


def run(
    output_dir: Path,
    parent_path: Path | None = None,
    sample_full_path: Path | None = None,
    sample_subset_path: Path | None = None,
    gdelt_locations: Path | None = None,
    news_locations: Path | None = None,
    parity_sample_size: int | None = None,
) -> None:
    validation_dir = output_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    corridor_path = output_dir / "gpr_corridor_daily.csv"
    if not corridor_path.exists():
        raise FileNotFoundError(f"{corridor_path} not found; run the corridor command first")
    corridor_df = pd.read_csv(corridor_path)

    reports = {
        "corridor_event_response.csv": check_event_response(corridor_df),
        "corridor_discrimination.csv": check_cross_corridor_discrimination(corridor_df),
        "corridor_coverage.csv": check_match_coverage(corridor_df),
    }
    parent_path = parent_path or output_dir / "gpr_daily_index.csv"
    if parent_path.exists():
        reports["corridor_parent_leakage.csv"] = check_parent_leakage(
            corridor_df, pd.read_csv(parent_path)
        )
    if sample_full_path and sample_subset_path:
        reports["corridor_slot_sampling.csv"] = check_slot_sampling(
            pd.read_csv(sample_full_path), pd.read_csv(sample_subset_path)
        )
    if gdelt_locations and news_locations:
        reports["corridor_news_parity.csv"] = check_news_path_parity(
            gdelt_locations, news_locations, parity_sample_size
        )

    for filename, report in reports.items():
        report.to_csv(validation_dir / filename, index=False)
        print(f"\n{filename}\n{report.to_string(index=False)}")
    print(f"\n[CORRIDOR VALIDATION] Reports saved to {validation_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--parent-path", type=Path)
    parser.add_argument("--sample-full-path", type=Path)
    parser.add_argument("--sample-subset-path", type=Path)
    parser.add_argument("--gdelt-locations", type=Path)
    parser.add_argument("--news-locations", type=Path)
    parser.add_argument("--parity-sample-size", type=int)
    parser.add_argument(
        "--parity-smoke",
        action="store_true",
        help="Run GDELT vs synthetic news-path parity on one GKG parquet",
    )
    parser.add_argument(
        "--gdelt-path",
        type=Path,
        default=GKG_PROCESSED_DIR / "gkg_processed_20250101.parquet",
    )
    parser.add_argument("--sample-size", type=int, default=50000)
    parser.add_argument(
        "--summarize-daily",
        action="store_true",
        help="Print spread summary for gpr_corridor_daily.csv",
    )
    parser.add_argument(
        "--daily-path",
        type=Path,
        default=OUTPUT_DIR / "gpr_corridor_daily.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    if args.summarize_daily:
        summarize_corridor_daily(args.daily_path)
        return
    if args.parity_smoke:
        run_parity_smoke(args.gdelt_path, args.sample_size, output_dir)
        return
    run(
        output_dir=output_dir,
        parent_path=args.parent_path,
        sample_full_path=args.sample_full_path,
        sample_subset_path=args.sample_subset_path,
        gdelt_locations=args.gdelt_locations,
        news_locations=args.news_locations,
        parity_sample_size=args.parity_sample_size,
    )


if __name__ == "__main__":
    main()
