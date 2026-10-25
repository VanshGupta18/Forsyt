"""India-relative bilateral GPR — geopolitical risk *between India and country X*.

For every positive GPR article that mentions **India AND another country**, the
article's gpr_score is attributed to that other country. Aggregated per day and
normalized to the same India baseline the product uses (100 = baseline-average
India-relevant stress for that pair).

This is a pure re-aggregation of the article scores the main pipeline already
writes (`gpr_article_scores.parquet` / `_scores_batch_*.parquet`) — no
re-scoring, no GDELT download. Mirrors the standalone design of
`corridor_index.py`.

Run:
    python gpr_index/main.py bilateral                       # read outputs/, write CSV
    python gpr_index/main.py bilateral --self-check          # synthetic invariants

Output: `outputs/gpr_bilateral_daily.csv`
    date, country_code, gpr_sum, total_articles, raw_ratio,
    bilateral_gpr_index, sum_<event_category>...
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import pandas as pd

from scripts.gkg_gpr_pipeline import (  # reuse — do not reimplement
    EVENT_CATEGORIES,
    GPR_POSITIVE_THRESHOLD,
    _extract_countries,
)
from scripts.paths import OUTPUT_DIR  # gpr_index/outputs

INDIA = "IN"
_CATS = list(EVENT_CATEGORIES.keys()) + ["other"]


def aggregate_bilateral_day(
    scored: pd.DataFrame, date_val: pd.Timestamp, total: int
) -> List[dict]:
    """One row per country co-mentioned with India in this day's positive articles."""
    pos = scored[scored["gpr_score"] > GPR_POSITIVE_THRESHOLD]
    if pos.empty:
        return []
    sums: Dict[str, float] = defaultdict(float)
    cats: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for _, row in pos.iterrows():
        countries = _extract_countries(str(row.get("V2Locations", "")))
        if INDIA not in countries:
            continue
        score = float(row["gpr_score"])
        cat = row.get("event_category") if row.get("event_category") in _CATS else "other"
        for c in countries:
            if c == INDIA:
                continue  # India is never bilateral with itself
            sums[c] += score
            cats[c][cat] += score
    out = []
    for c, s in sums.items():
        rec = {
            "date": date_val,
            "country_code": c,
            "gpr_sum": s,
            "total_articles": total,
            "raw_ratio": s / total if total > 0 else 0.0,
        }
        for cat in _CATS:
            rec[f"sum_{cat}"] = cats[c].get(cat, 0.0)
        out.append(rec)
    return out


def normalize_bilateral_index(
    df: pd.DataFrame, baseline_start: str = "", baseline_end: str = ""
) -> pd.DataFrame:
    """raw_ratio / per-country baseline mean * 100 (same shape as country index).

    ponytail: MVP uses a full-range per-country mean as the baseline (no split-era
    India-only window like normalize_index does). Pass --baseline-start/-end to the
    product era once bilateral history matures if the warmup era distorts levels.
    """
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    if baseline_start and baseline_end:
        mask = (out["date"] >= pd.to_datetime(baseline_start)) & (
            out["date"] <= pd.to_datetime(baseline_end)
        )
    else:
        mask = pd.Series(True, index=out.index)
    s_bar = (
        out[mask].groupby("country_code")["raw_ratio"].mean()
        if mask.any()
        else out.groupby("country_code")["raw_ratio"].mean()
    ).replace(0, 1.0)
    out["bilateral_gpr_index"] = out["raw_ratio"] / out["country_code"].map(s_bar).fillna(1.0) * 100.0
    return out


def _theme_to_category(themes: str) -> str:
    """Map a semicolon theme list to one of EVENT_CATEGORIES, else 'other'."""
    tokens = {t.strip() for t in (themes or "").split(";") if t.strip()}
    for cat, members in EVENT_CATEGORIES.items():
        if tokens & members:
            return cat
    return "other"


def _load_scores_from_db() -> pd.DataFrame:
    """Build a scored-article frame from the live news DB (real India news).

    Reuses the GKG V2Locations format stored in `nlp_locations`. gpr_score is a
    DB-derived proxy (ponytail: the exact GKG scorer isn't rerun here — presence
    of a geopolitical theme + tone negativity stands in), which is enough to rank
    India-relative bilateral pressure per country/day.
    """
    import os

    import psycopg2
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / "news_dataset" / ".env")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL not set — cannot build bilateral from DB")
    conn = psycopg2.connect(dsn, connect_timeout=10)
    # Bounded lookback so the scan stays cheap as the table grows (the bilateral
    # series only needs recent India-relative history).
    df = pd.read_sql(
        "SELECT published_at, nlp_locations, nlp_themes, nlp_tone_neg "
        "FROM articles WHERE nlp_locations IS NOT NULL AND nlp_locations <> '' "
        "AND published_at IS NOT NULL "
        "AND published_at >= NOW() - INTERVAL '400 days'",
        conn,
    )
    conn.close()
    df = df.rename(columns={"nlp_locations": "V2Locations", "nlp_themes": "themes"})
    df["date"] = pd.to_datetime(df["published_at"]).dt.normalize()
    df["event_category"] = df["themes"].map(_theme_to_category)
    tone = pd.to_numeric(df["nlp_tone_neg"], errors="coerce").fillna(0.0).clip(0, 10)
    has_theme = df["themes"].fillna("").str.strip().ne("")
    df["gpr_score"] = (0.3 + tone / 20.0).where(has_theme, 0.0)  # >threshold when themed
    return df[["date", "V2Locations", "event_category", "gpr_score"]]


def _load_scores(output_dir: Path) -> pd.DataFrame:
    merged = output_dir / "gpr_article_scores.parquet"
    batches = sorted(output_dir.glob("_scores_batch_*.parquet"))
    if merged.exists() and not batches:
        df = pd.read_parquet(merged)
    elif batches:
        df = pd.concat((pd.read_parquet(p) for p in batches), ignore_index=True)
    elif merged.exists():
        df = pd.read_parquet(merged)
    else:
        raise FileNotFoundError(
            f"No article scores in {output_dir} — run `python gpr_index/main.py gpr` first "
            "(it writes gpr_article_scores.parquet)."
        )
    df["date"] = pd.to_datetime(df["SQLDATE"]).dt.normalize()
    return df


def build(df: pd.DataFrame, baseline_start: str = "", baseline_end: str = "") -> pd.DataFrame:
    rows: List[dict] = []
    for date_val, day in df.groupby("date"):
        rows.extend(aggregate_bilateral_day(day, pd.Timestamp(date_val), len(day)))
    if not rows:
        return pd.DataFrame()
    return normalize_bilateral_index(pd.DataFrame(rows), baseline_start, baseline_end)


def _self_check() -> None:
    """Synthetic invariants from the execution plan — fails loudly if logic breaks."""
    # Day 1: India+Pakistan armed conflict (high). India+China trade (low, below thresh).
    # Day 2: quiet baseline for both. Row with no India mention must be ignored.
    rows = [
        {"SQLDATE": "2026-08-10", "gpr_score": 0.9, "event_category": "military_conflict",
         "V2Locations": "1#India#IN#IN#20#77#0;1#Pakistan#PK#PK#30#70#0"},
        {"SQLDATE": "2026-08-10", "gpr_score": 0.1, "event_category": "diplomatic_tension",
         "V2Locations": "1#India#IN#IN#20#77#0;1#China#CH#CH#35#105#0"},  # below threshold
        {"SQLDATE": "2026-08-10", "gpr_score": 0.8, "event_category": "sanctions",
         "V2Locations": "1#Russia#RS#RS#60#100#0;1#US#US#US#38#-97#0"},   # no India -> ignored
        {"SQLDATE": "2026-08-11", "gpr_score": 0.3, "event_category": "diplomatic_tension",
         "V2Locations": "1#India#IN#IN#20#77#0;1#Pakistan#PK#PK#30#70#0"},
        # filler so day-2's article total is higher -> lower raw_ratio than the conflict day
        {"SQLDATE": "2026-08-11", "gpr_score": 0.0, "event_category": "none",
         "V2Locations": "1#Japan#JA#JA#36#138#0"},
        {"SQLDATE": "2026-08-11", "gpr_score": 0.0, "event_category": "none",
         "V2Locations": "1#Brazil#BR#BR#-10#-55#0"},
    ]
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["SQLDATE"]).dt.normalize()
    out = build(df)

    codes = set(out["country_code"])
    assert INDIA not in codes, "India must never appear in its own bilateral output"
    assert "US" not in codes, "articles without an India mention must be excluded"
    assert "PK" in codes, "co-mentioned country must appear"
    pk_hot = out[(out.country_code == "PK") & (out.date == "2026-08-10")]["bilateral_gpr_index"].iloc[0]
    pk_calm = out[(out.country_code == "PK") & (out.date == "2026-08-11")]["bilateral_gpr_index"].iloc[0]
    assert pk_hot > pk_calm, f"conflict day must outscore calm day ({pk_hot} !> {pk_calm})"
    assert (out["sum_military_conflict"] >= 0).all(), "channel sums present"
    print("bilateral_index self-check: OK")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build India-relative bilateral GPR index.")
    ap.add_argument("--self-check", action="store_true", help="run synthetic invariants and exit")
    ap.add_argument("--source", choices=["parquet", "db"], default="parquet",
                    help="parquet = scored GKG articles (prod); db = live news DB (local)")
    ap.add_argument("--baseline-start", default="")
    ap.add_argument("--baseline-end", default="")
    ap.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = ap.parse_args()

    if args.self_check:
        _self_check()
        return

    output_dir = Path(args.output_dir)
    df = _load_scores_from_db() if args.source == "db" else _load_scores(output_dir)
    out = build(df, args.baseline_start, args.baseline_end)
    if out.empty:
        print("No India co-mention articles found — nothing to write.", file=sys.stderr)
        sys.exit(1)
    dest = output_dir / "gpr_bilateral_daily.csv"
    out.sort_values(["country_code", "date"]).to_csv(dest, index=False)
    print(f"Wrote {dest}  ({out['country_code'].nunique()} countries, {len(out)} rows)")


if __name__ == "__main__":
    main()
