"""Diagnose GPR article scoring on a sample of processed GKG days.

Runs before/after taxonomy and component changes to measure positive_share,
score distribution, theme hit rates, and threshold sensitivity.

Usage:
  python -m scripts.diagnose_gpr_scoring --sample-days 5 --max-articles-per-day 30000
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import List

import pandas as pd

from scripts.gkg_gpr_pipeline import (
    GPR_POSITIVE_THRESHOLD,
    TIER1,
    TIER2,
    TIER3,
    list_processed_files,
    score_articles,
)


SCORE_BUCKETS = [
    ("score_eq_0",       lambda s: s == 0),
    ("score_0.01_0.20",  lambda s: (s > 0) & (s <= 0.20)),
    ("score_0.21_0.40",  lambda s: (s > 0.20) & (s <= 0.40)),
    ("score_0.41_0.60",  lambda s: (s > 0.40) & (s <= 0.60)),
    ("score_0.61_1.00",  lambda s: s > 0.60),
]

THRESHOLDS = (0.20, 0.25, 0.30, 0.35)
ALL_TIERS = {"tier1": TIER1, "tier2": TIER2, "tier3": TIER3}


def _theme_hits(themes_series: pd.Series) -> dict:
    n = len(themes_series)
    if n == 0:
        return {"tier1_pct": 0, "tier2_pct": 0, "tier3_pct": 0, "any_theme_pct": 0}
    t1 = t2 = t3 = any_t = 0
    for raw in themes_series.fillna("").astype(str):
        tokens = {t.strip() for t in raw.upper().split(";") if t.strip()}
        hit1 = bool(tokens & TIER1)
        hit2 = bool(tokens & TIER2)
        hit3 = bool(tokens & TIER3)
        t1 += hit1
        t2 += hit2
        t3 += hit3
        any_t += hit1 or hit2 or hit3
    return {
        "tier1_pct": round(100 * t1 / n, 2),
        "tier2_pct": round(100 * t2 / n, 2),
        "tier3_pct": round(100 * t3 / n, 2),
        "any_theme_pct": round(100 * any_t / n, 2),
    }


def _per_code_hits(themes_series: pd.Series, n: int) -> List[dict]:
    """Top theme codes by hit rate across all articles."""
    counts: Counter = Counter()
    for raw in themes_series.fillna("").astype(str):
        tokens = {t.strip() for t in raw.upper().split(";") if t.strip()}
        for tier_name, tier_set in ALL_TIERS.items():
            for code in tokens & tier_set:
                counts[(tier_name, code)] += 1
    rows = []
    for (tier, code), cnt in counts.most_common(15):
        rows.append({
            "check": "tier_code_hit_rate",
            "tier": tier,
            "code": code,
            "count": cnt,
            "pct": round(100 * cnt / n, 3),
        })
    return rows


def _verify_theme_matching() -> List[dict]:
    cases = [
        {"themes": "TAX_FNCACT_MILITARY", "expect_tier2": True, "note": "full code in TIER2"},
        {"themes": "MILITARY", "expect_tier2": False, "note": "bare MILITARY removed from TIER2"},
        {"themes": "WB_CONFLICT_AND_VIOLENCE", "expect_score_zero": True, "note": "broad code removed"},
        {"themes": "ARMEDCONFLICT", "expect_tier1": True, "note": "Tier1 act"},
        {"themes": "", "expect_score_zero": True, "note": "empty themes"},
    ]
    rows = []
    for c in cases:
        df = pd.DataFrame([{
            "V2Themes": c["themes"],
            "tone_neg": 0.0,
            "tone_polarity": 0.0,
            "GCAM": "",
        }])
        scored = score_articles(df)
        row = {
            "themes": c["themes"] or "(empty)",
            "note": c["note"],
            "theme_score": float(scored["theme_score"].iloc[0]),
            "gpr_score": float(scored["gpr_score"].iloc[0]),
            "gpr_type": scored["gpr_type"].iloc[0],
        }
        if c.get("expect_score_zero"):
            row["pass"] = "YES" if row["gpr_score"] == 0 else "NO"
        elif c.get("expect_tier2"):
            row["pass"] = "YES" if row["gpr_type"] in ("threat", "act") else "NO"
        elif c.get("expect_tier1"):
            row["pass"] = "YES" if row["gpr_type"] == "act" else "NO"
        else:
            row["pass"] = "YES" if row["gpr_score"] == 0 else "NO"
        rows.append(row)
    return rows


def run(
    processed_dir: Path,
    output_dir: Path,
    start_date: str,
    end_date: str,
    sample_days: int | None = None,
    max_articles_per_day: int | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = list_processed_files(processed_dir, start_date, end_date)
    if sample_days and len(files) > sample_days:
        step = max(1, len(files) // sample_days)
        files = files[::step][:sample_days]

    if not files:
        raise FileNotFoundError(f"No processed files in {processed_dir} for {start_date}..{end_date}")

    print(f"[DIAGNOSE] {len(files)} days  {files[0][0].date()} → {files[-1][0].date()}")
    print(f"[DIAGNOSE] GPR_POSITIVE_THRESHOLD = {GPR_POSITIVE_THRESHOLD}")
    if max_articles_per_day:
        print(f"[DIAGNOSE] max {max_articles_per_day:,} articles/day (sampled)")

    frames: List[pd.DataFrame] = []
    for _, fpath in files:
        try:
            df = pd.read_parquet(fpath)
        except Exception as exc:
            print(f"  [WARN] {fpath.name}: {exc}")
            continue
        if df.empty:
            continue
        if max_articles_per_day and len(df) > max_articles_per_day:
            df = df.sample(n=max_articles_per_day, random_state=42)
        frames.append(score_articles(df))
        print(f"  scored {fpath.name}  ({len(df):,} articles)", flush=True)

    if not frames:
        raise RuntimeError("No articles loaded for diagnosis")

    all_scored = pd.concat(frames, ignore_index=True)
    n = len(all_scored)
    scores = all_scored["gpr_score"]

    dist_rows = []
    for label, mask_fn in SCORE_BUCKETS:
        cnt = int(mask_fn(scores).sum())
        dist_rows.append({
            "check": "score_distribution",
            "bucket": label,
            "count": cnt,
            "pct": round(100 * cnt / n, 2),
        })

    hits = _theme_hits(all_scored["V2Themes"])
    theme_rows = [{"check": "theme_hit_rate", "metric": k, "value": v} for k, v in hits.items()]
    code_rows = _per_code_hits(all_scored["V2Themes"], n)

    pos = all_scored[scores > 0]
    comp_rows = []
    if not pos.empty:
        for col in ("theme_score", "tone_score", "gcam_score"):
            comp_rows.append({
                "check": "component_means",
                "component": col,
                "mean": round(float(pos[col].mean()), 4),
                "median": round(float(pos[col].median()), 4),
            })

    thresh_rows = []
    for t in THRESHOLDS:
        share = float((scores > t).mean())
        thresh_rows.append({
            "check": "threshold_sensitivity",
            "threshold": t,
            "positive_share_pct": round(100 * share, 2),
        })

    match_rows = [{"check": "theme_matching", **r} for r in _verify_theme_matching()]

    report = pd.concat([
        pd.DataFrame(dist_rows),
        pd.DataFrame(theme_rows),
        pd.DataFrame(code_rows),
        pd.DataFrame(comp_rows),
        pd.DataFrame(thresh_rows),
        pd.DataFrame(match_rows),
    ], ignore_index=True)
    out_path = output_dir / "scoring_diagnosis.csv"
    report.to_csv(out_path, index=False)

    print("\n--- Score distribution ---")
    for r in dist_rows:
        print(f"  {r['bucket']:18} {r['pct']:6.2f}%  ({r['count']:,})")
    print("\n--- Theme hit rates ---")
    for r in theme_rows:
        print(f"  {r['metric']:16} {r['value']}%")
    print("\n--- Top theme codes ---")
    for r in code_rows[:10]:
        print(f"  {r['tier']:6} {r['code']:30} {r['pct']:6.3f}%")
    print("\n--- Component means (gpr_score > 0) ---")
    for r in comp_rows:
        print(f"  {r['component']:14} mean={r['mean']:.4f}  median={r['median']:.4f}")
    print("\n--- Threshold sensitivity ---")
    for r in thresh_rows:
        print(f"  threshold={r['threshold']:.2f}  positive_share={r['positive_share_pct']:.2f}%")
    print("\n--- Theme matching checks ---")
    for r in match_rows:
        print(f"  {r['themes']:25} gpr={r['gpr_score']:.3f}  pass={r['pass']}")
    print(f"\n[DIAGNOSE] Report → {out_path}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Diagnose GPR article scoring")
    p.add_argument("--processed-dir", default="data/gkg_processed")
    p.add_argument("--output-dir",    default="outputs/validation")
    p.add_argument("--start-date",    default="2025-01-01")
    p.add_argument("--end-date",      default="2025-12-31")
    p.add_argument("--sample-days",   type=int, default=5)
    p.add_argument("--max-articles-per-day", type=int, default=30000,
                   help="Random sample per day for faster runs (default 30000)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run(
        processed_dir=Path(args.processed_dir),
        output_dir=Path(args.output_dir),
        start_date=args.start_date,
        end_date=args.end_date,
        sample_days=args.sample_days,
        max_articles_per_day=args.max_articles_per_day,
    )


if __name__ == "__main__":
    main()
