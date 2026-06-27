"""Compare GPR indices produced by the news scraper path vs the GDELT GKG path.

Reads:
  --news-dir outputs/news/    — scraper-based GPR
  --gkg-dir  outputs/gkg/    — GDELT GKG GPR

Both directories must contain gpr_daily_index.csv.

Outputs (written to --out-dir, default outputs/compare/):
  compare_news_vs_gkg.csv     — daily correlation table (Pearson + Spearman)
  spike_comparison.csv        — top-N spike days for each source, side by side
  volume_news_vs_gkg.csv      — article volume comparison where overlap exists

Usage:
  python -m scripts.compare_gpr_sources \\
      --news-dir outputs/news \\
      --gkg-dir  outputs/gkg \\
      [--start-date 2026-06-27] \\
      [--end-date   2026-12-31] \\
      [--out-dir    outputs/compare]
  (or: python main.py compare-gpr ...)
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_daily(output_dir: Path) -> pd.DataFrame | None:
    p = output_dir / "gpr_daily_index.csv"
    if not p.exists():
        logger.warning(f"[compare] {p} not found")
        return None
    df = pd.read_csv(p, parse_dates=["date"])
    df = df.sort_values("date").set_index("date")
    return df


def _load_event(output_dir: Path) -> pd.DataFrame | None:
    p = output_dir / "gpr_event_type.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["date"])
    df = df.sort_values("date").set_index("date")
    return df


def _load_country(output_dir: Path, country_code: str = "IN") -> pd.DataFrame | None:
    p = output_dir / "gpr_country_level.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["date"])
    df = df[df["country_code"] == country_code].sort_values("date").set_index("date")
    return df


def _load_scores(output_dir: Path) -> pd.DataFrame | None:
    p = output_dir / "gpr_article_scores.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p)


# ---------------------------------------------------------------------------
# Correlation helper
# ---------------------------------------------------------------------------

def _correlate(a: pd.Series, b: pd.Series, label_a: str, label_b: str) -> dict:
    aligned = pd.concat([a, b], axis=1).dropna()
    if len(aligned) < 5:
        return {"n": len(aligned), "pearson_r": None, "pearson_p": None,
                "spearman_r": None, "spearman_p": None}
    x, y = aligned.iloc[:, 0], aligned.iloc[:, 1]
    pr, pp = stats.pearsonr(x, y)
    sr, sp = stats.spearmanr(x, y)
    return {
        "series_a":   label_a,
        "series_b":   label_b,
        "n":          len(aligned),
        "pearson_r":  round(float(pr), 4),
        "pearson_p":  round(float(pp), 4),
        "spearman_r": round(float(sr), 4),
        "spearman_p": round(float(sp), 4),
        "start":      str(aligned.index.min().date()),
        "end":        str(aligned.index.max().date()),
    }


# ---------------------------------------------------------------------------
# Main comparison
# ---------------------------------------------------------------------------

def run(
    news_dir: Path,
    gkg_dir: Path,
    out_dir: Path,
    start_date: str | None = None,
    end_date: str | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    news_daily = _load_daily(news_dir)
    gkg_daily  = _load_daily(gkg_dir)

    if news_daily is None or gkg_daily is None:
        logger.error("[compare] Cannot compare — one or both gpr_daily_index.csv missing")
        return

    # Optional date filter
    if start_date:
        news_daily = news_daily[news_daily.index >= start_date]
        gkg_daily  = gkg_daily[gkg_daily.index  >= start_date]
    if end_date:
        news_daily = news_daily[news_daily.index <= end_date]
        gkg_daily  = gkg_daily[gkg_daily.index  <= end_date]

    overlap = news_daily.index.intersection(gkg_daily.index)
    print(f"\n[compare] Overlapping days: {len(overlap)}")
    if len(overlap) < 2:
        logger.warning("[compare] Fewer than 2 overlapping days — skipping correlation")

    # ── 1. Daily correlation table ──────────────────────────────────────────
    rows = []
    for col in ["gpr_index", "gpr_acts_index", "gpr_threats_index", "gpr_7ma", "gpr_30ma"]:
        if col in news_daily.columns and col in gkg_daily.columns:
            rows.append(_correlate(
                news_daily[col].reindex(overlap),
                gkg_daily[col].reindex(overlap),
                f"news:{col}", f"gkg:{col}",
            ))
    corr_df = pd.DataFrame(rows)
    if not corr_df.empty:
        corr_df.to_csv(out_dir / "compare_news_vs_gkg.csv", index=False)
        print("\n[compare] Daily index correlations:")
        print(corr_df.to_string(index=False))

    # ── 2. Side-by-side on overlapping dates ────────────────────────────────
    if len(overlap) >= 2:
        joined = news_daily[["gpr_index"]].reindex(overlap).rename(columns={"gpr_index": "news_gpr"})
        joined["gkg_gpr"] = gkg_daily["gpr_index"].reindex(overlap)
        joined["diff"] = joined["news_gpr"] - joined["gkg_gpr"]
        joined = joined.reset_index()
        joined.to_csv(out_dir / "daily_overlap.csv", index=False)
        print(f"\n[compare] Daily overlap table → {out_dir/'daily_overlap.csv'}")

    # ── 3. Top spike days ───────────────────────────────────────────────────
    n_top = 10
    spikes_rows = []
    if "gpr_index" in news_daily.columns:
        top_news = news_daily["gpr_index"].nlargest(n_top)
        for dt, val in top_news.items():
            spikes_rows.append({"source": "news", "date": dt.date(), "gpr_index": round(val, 2)})
    if "gpr_index" in gkg_daily.columns:
        top_gkg = gkg_daily["gpr_index"].nlargest(n_top)
        for dt, val in top_gkg.items():
            spikes_rows.append({"source": "gkg", "date": dt.date(), "gpr_index": round(val, 2)})
    if spikes_rows:
        spike_df = pd.DataFrame(spikes_rows).sort_values(["source", "gpr_index"], ascending=[True, False])
        spike_df.to_csv(out_dir / "spike_comparison.csv", index=False)
        print(f"\n[compare] Spike comparison → {out_dir/'spike_comparison.csv'}")

    # ── 4. Event-type column correlations ───────────────────────────────────
    news_ev = _load_event(news_dir)
    gkg_ev  = _load_event(gkg_dir)
    if news_ev is not None and gkg_ev is not None:
        ev_overlap = news_ev.index.intersection(gkg_ev.index)
        ev_rows = []
        for col in news_ev.columns:
            if col in gkg_ev.columns and col != "date":
                ev_rows.append(_correlate(
                    news_ev[col].reindex(ev_overlap),
                    gkg_ev[col].reindex(ev_overlap),
                    f"news:{col}", f"gkg:{col}",
                ))
        if ev_rows:
            pd.DataFrame(ev_rows).to_csv(out_dir / "event_type_correlation.csv", index=False)
            print(f"[compare] Event-type correlations → {out_dir/'event_type_correlation.csv'}")

    # ── 5. India country-level correlation ──────────────────────────────────
    news_in = _load_country(news_dir, "IN")
    gkg_in  = _load_country(gkg_dir,  "IN")
    if news_in is not None and gkg_in is not None and "country_gpr_index" in news_in.columns:
        cn_overlap = news_in.index.intersection(gkg_in.index)
        c_row = _correlate(
            news_in["country_gpr_index"].reindex(cn_overlap),
            gkg_in["country_gpr_index"].reindex(cn_overlap),
            "news:India_GPR", "gkg:India_GPR",
        )
        pd.DataFrame([c_row]).to_csv(out_dir / "india_country_correlation.csv", index=False)
        print(f"[compare] India country correlation → {out_dir/'india_country_correlation.csv'}")

    # ── 6. Article volume comparison ────────────────────────────────────────
    news_sc = _load_scores(news_dir)
    gkg_sc  = _load_scores(gkg_dir)
    vol_rows = []
    if news_sc is not None and "SQLDATE" in news_sc.columns:
        news_vol = news_sc.groupby(pd.to_datetime(news_sc["SQLDATE"]).dt.date).size().rename("news_articles")
        vol_rows.append(news_vol)
    if gkg_sc is not None and "SQLDATE" in gkg_sc.columns:
        gkg_vol = gkg_sc.groupby(pd.to_datetime(gkg_sc["SQLDATE"]).dt.date).size().rename("gkg_articles")
        vol_rows.append(gkg_vol)
    if vol_rows:
        vol_df = pd.concat(vol_rows, axis=1).reset_index().rename(columns={"index": "date"})
        vol_df.to_csv(out_dir / "volume_news_vs_gkg.csv", index=False)
        print(f"[compare] Volume comparison → {out_dir/'volume_news_vs_gkg.csv'}")

    print(f"\n[compare] Done. All outputs in {out_dir}/")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare news-path vs GKG-path GPR indices")
    p.add_argument("--news-dir",    default="outputs/news",    help="News GPR output dir")
    p.add_argument("--gkg-dir",     default="outputs/gkg",     help="GKG GPR output dir")
    p.add_argument("--out-dir",     default="outputs/compare", help="Comparison output dir")
    p.add_argument("--start-date",  default=None,              help="YYYY-MM-DD filter")
    p.add_argument("--end-date",    default=None,              help="YYYY-MM-DD filter")
    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    run(
        news_dir=Path(args.news_dir),
        gkg_dir=Path(args.gkg_dir),
        out_dir=Path(args.out_dir),
        start_date=args.start_date,
        end_date=args.end_date,
    )


if __name__ == "__main__":
    main()
