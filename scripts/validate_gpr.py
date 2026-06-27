"""Validate GPR pipeline outputs against Iacoviello & Tong (2026) benchmarks.

Runs five checks on outputs produced by gkg_gpr_pipeline.py:

  1. Statistical properties — compares mean, std, skewness, autocorrelation,
     positive share against paper Table 1 targets.

  2. Component contributions — verifies theme/tone/GCAM each contribute
     meaningfully and are not redundant (from article scores Parquet).

  3. Event spike validation — checks that known high-GPR events in 2025
     produce statistically significant spikes (z-score > 1.0).

  4. Caldara correlation — monthly Pearson/Spearman vs local Caldara files
     (global GPR and GPRC_IND for India).

  5. Daily Caldara correlation — Pearson r on overlapping observed days.

  6. Caldara MA30 correlation — our gpr_30ma vs Caldara GPRD_MA30.

  7. Caldara spike cross-check — top Caldara spike days vs our index response.

  8. Gap period analysis — Caldara GPRD during GKG-missing window vs imputed values.

Also writes a coverage report (autocorr on sparse + continuous series,
article count stats, missing GKG dates).

Usage:
  python -m scripts.validate_gpr \\
    --output-dir outputs \\
    --start-date 2025-01-01 \\
    --end-date   2025-12-31
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from scripts.gkg_gpr_pipeline import GPR_POSITIVE_THRESHOLD

# Known high-GPR events in 2025 for spike validation (date, label)
KNOWN_EVENTS_2025 = [
    ("2025-01-20", "Trump inauguration / policy shifts"),
    ("2025-04-02", "US-China tariff escalation"),
    ("2025-01-15", "Gaza ceasefire collapse / renewed conflict"),
]

# Known high-GPR events in 2026 for India-path spike validation
KNOWN_EVENTS_INDIA_2026 = [
    ("2026-04-19", "India general election results / political uncertainty"),
    ("2026-02-14", "Pulwama/Pakistan border tensions anniversary"),
    ("2026-05-10", "India-China LAC standoff reports"),
]

CALDARA_MONTHLY_CANDIDATES = [
    Path("data/caldara_gpr_monthly.xls"),
    Path("data/data_gpr_export (1).xls"),
]
CALDARA_DAILY_CANDIDATES = [
    Path("data/caldara_gpr_daily.xls"),
    Path("data/data_gpr_daily_recent.xls"),
]


def _load_caldara_xls(candidates: list[Path]) -> Optional[pd.DataFrame]:
    for p in candidates:
        if p.exists():
            print(f"[CALDARA] Loading {p}")
            return pd.read_excel(p)
    return None


def _date_col(df: pd.DataFrame) -> Optional[str]:
    return next((c for c in df.columns if "date" in c.lower() or "month" in c.lower()), None)


# ---------------------------------------------------------------------------
# Check 1: Statistical properties
# ---------------------------------------------------------------------------

def check_statistical_properties(daily_df: pd.DataFrame, use_lag1_autocorr: bool = False) -> pd.DataFrame:
    gpr       = daily_df["gpr_index"].dropna()
    pos_share = daily_df["positive_share"].dropna()
    if use_lag1_autocorr:
        autocorr = gpr.autocorr(lag=1) if len(gpr) > 1 else float("nan")
        ac_label = "autocorr_lag1"
        ac_target = "> 0.45"
        ac_pass = lambda v: v > 0.45
    else:
        autocorr = gpr.autocorr(lag=90) if len(gpr) > 90 else float("nan")
        ac_label = "autocorr_lag90"
        ac_target = "> 0.50"
        ac_pass = lambda v: v > 0.50

    checks = [
        ("mean",             gpr.mean(),        "100 (by construction)",  lambda v: True),
        ("std",              gpr.std(),          "35–70",                  lambda v: 35 <= v <= 70),
        ("skewness",         float(gpr.skew()),  "> 0.5",                  lambda v: v > 0.5),
        ("p01",              gpr.quantile(0.01), "> 0",                    lambda v: v > 0),
        ("p25",              gpr.quantile(0.25), "50–90",                  lambda v: 50 <= v <= 90),
        ("median",           gpr.median(),       "90–115",                 lambda v: 90 <= v <= 115),
        ("p75",              gpr.quantile(0.75), "120–160",                lambda v: 120 <= v <= 160),
        ("p99",              gpr.quantile(0.99), "200–400",                lambda v: 200 <= v <= 400),
        (ac_label,           autocorr,           ac_target,                ac_pass),
        ("positive_share",   pos_share.mean(),   "10–25%",                 lambda v: 0.10 <= v <= 0.25),
    ]
    rows = []
    for metric, value, target, fn in checks:
        passed = fn(value) if not (isinstance(value, float) and np.isnan(value)) else False
        rows.append({"metric": metric, "value": round(float(value), 4),
                     "target": target, "pass": "YES" if passed else "NO"})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Check 2: Component contributions
# ---------------------------------------------------------------------------

def check_component_contributions(article_scores_path: Path) -> Optional[pd.DataFrame]:
    if not article_scores_path.exists():
        print("[WARN] gpr_article_scores.parquet not found — skipping component check")
        return None

    df  = pd.read_parquet(article_scores_path)
    pos = df[df["gpr_score"] > GPR_POSITIVE_THRESHOLD]
    if pos.empty:
        return None

    rows = []
    total_var = pos["gpr_score"].var()
    for col in ("theme_score", "tone_score", "gcam_score"):
        mean_val  = float(pos[col].mean())
        var_share = float(pos[col].var() / total_var) if total_var > 0 else float("nan")
        rows.append({"component": col, "mean": round(mean_val, 4),
                     "variance_share": round(var_share, 4)})

    corr = pos[["theme_score", "tone_score", "gcam_score"]].corr()
    rows.append({"component": "corr(theme,tone)", "mean": round(corr.loc["theme_score","tone_score"],4), "variance_share": float("nan")})
    rows.append({"component": "corr(theme,gcam)", "mean": round(corr.loc["theme_score","gcam_score"],4), "variance_share": float("nan")})
    rows.append({"component": "corr(tone,gcam)",  "mean": round(corr.loc["tone_score","gcam_score"],4),  "variance_share": float("nan")})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Check 3: Event spike validation
# ---------------------------------------------------------------------------

def check_event_spikes(daily_df: pd.DataFrame, events: Optional[list] = None) -> pd.DataFrame:
    daily_df = daily_df.copy()
    daily_df["date"] = pd.to_datetime(daily_df["date"])
    daily_df = daily_df.set_index("date").sort_index()

    if events is None:
        events = KNOWN_EVENTS_2025

    rows = []
    for event_date_str, label in events:
        event_date = pd.to_datetime(event_date_str)
        if event_date not in daily_df.index and event_date > daily_df.index.max():
            rows.append({"event": label, "date": event_date_str,
                         "window_mean": float("nan"), "baseline_mean": float("nan"),
                         "z_score": float("nan"), "pass": "N/A (out of range)"})
            continue

        window  = daily_df.loc[event_date - pd.Timedelta(days=3): event_date + pd.Timedelta(days=3), "gpr_index"]
        pre     = daily_df.loc[event_date - pd.Timedelta(days=30): event_date - pd.Timedelta(days=4), "gpr_index"]

        if window.empty or pre.empty or pre.std() == 0:
            z = float("nan")
            passed = "N/A"
        else:
            z      = (window.mean() - pre.mean()) / pre.std()
            passed = "YES" if z > 1.0 else "NO"

        rows.append({
            "event":          label,
            "date":           event_date_str,
            "window_mean":    round(float(window.mean()), 2) if not window.empty else float("nan"),
            "baseline_mean":  round(float(pre.mean()),    2) if not pre.empty    else float("nan"),
            "z_score":        round(float(z), 3) if not np.isnan(z) else float("nan"),
            "pass":           passed,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Check 4: Caldara monthly correlation
# ---------------------------------------------------------------------------

def check_caldara_correlation(
    monthly_df: pd.DataFrame,
    benchmark: str = "all",
) -> Optional[pd.DataFrame]:
    """Caldara monthly correlation.

    benchmark: "all" (default) | "gprc_ind" (India path, lower pass threshold 0.45)
    """
    cal = _load_caldara_xls(CALDARA_MONTHLY_CANDIDATES)
    if cal is None:
        print("[WARN] No local Caldara monthly file found")
        return None

    date_col = _date_col(cal)
    if date_col is None:
        print(f"[WARN] Could not find date column. Columns: {list(cal.columns)}")
        return None

    cal = cal.copy()
    cal["year_month"] = pd.to_datetime(cal[date_col], errors="coerce").dt.to_period("M")
    cal = cal.dropna(subset=["year_month"])

    monthly_df = monthly_df.copy()
    monthly_df["year_month"] = pd.to_datetime(monthly_df["year_month"].astype(str)).dt.to_period("M")

    # Select which Caldara columns to compare
    if benchmark == "gprc_ind":
        pairs = [("GPRC_IND", "india_GPRC_IND", 0.45)]
    else:
        pairs = [("GPR", "global_GPR", 0.50), ("GPRC_IND", "india_GPRC_IND", 0.45)]

    results = []
    for col, label, pass_threshold in pairs:
        if col not in cal.columns:
            print(f"[WARN] Column {col} not in Caldara monthly file")
            continue
        merged = monthly_df.merge(
            cal[["year_month", col]].rename(columns={col: "caldara_gpr"}),
            on="year_month", how="inner",
        )
        if len(merged) < 3:
            print(f"[WARN] Only {len(merged)} overlapping months for {col}")
            continue
        pearson  = merged["gpr_index"].corr(merged["caldara_gpr"])
        spearman = merged["gpr_index"].corr(merged["caldara_gpr"], method="spearman")
        results.append({
            "benchmark":      label,
            "months_overlap": len(merged),
            "pearson_r":      round(pearson,  3),
            "spearman_r":     round(spearman, 3),
            "pass":           "YES" if pearson > pass_threshold else "NO",
            "target":         f"> {pass_threshold}",
        })

    return pd.DataFrame(results) if results else None


# ---------------------------------------------------------------------------
# Check 5: Caldara daily correlation
# ---------------------------------------------------------------------------

def check_caldara_daily_correlation(daily_df: pd.DataFrame) -> Optional[pd.DataFrame]:
    cal = _load_caldara_xls(CALDARA_DAILY_CANDIDATES)
    if cal is None:
        print("[WARN] No local Caldara daily file found")
        return None

    date_col = _date_col(cal)
    if date_col is None or "GPRD" not in cal.columns:
        print(f"[WARN] Could not find date/GPRD columns. Columns: {list(cal.columns)}")
        return None

    cal = cal.copy()
    cal["date"] = pd.to_datetime(cal[date_col], errors="coerce")
    cal = cal.dropna(subset=["date"])

    ours = daily_df.copy()
    ours["date"] = pd.to_datetime(ours["date"])

    merged = ours.merge(cal, on="date", how="inner")
    if len(merged) < 30:
        print(f"[WARN] Only {len(merged)} overlapping days for daily correlation")
        return None

    pairs = [
        ("gpr_index", "GPRD",           "raw_daily"),
        ("gpr_30ma",  "GPRD_MA30",      "ma30"),
        ("gpr_7ma",   "GPRD_MA7",       "ma7"),
    ]
    rows = []
    for ours_col, cal_col, label in pairs:
        if ours_col not in merged.columns or cal_col not in merged.columns:
            continue
        sub = merged[[ours_col, cal_col]].dropna()
        if len(sub) < 30:
            continue
        pearson  = sub[ours_col].corr(sub[cal_col])
        spearman = sub[ours_col].corr(sub[cal_col], method="spearman")
        rows.append({
            "comparison":   label,
            "ours_col":     ours_col,
            "caldara_col":  cal_col,
            "days_overlap": len(sub),
            "pearson_r":    round(pearson,  3),
            "spearman_r":   round(spearman, 3),
            "pass":         "YES" if pearson > 0.50 else "NO",
            "target":       "> 0.50",
        })
    return pd.DataFrame(rows) if rows else None


def check_caldara_spike_cross(daily_df: pd.DataFrame, start_date: str, end_date: str, top_n: int = 10) -> Optional[pd.DataFrame]:
    """Compare our index response on Caldara's top spike days in the period."""
    cal = _load_caldara_xls(CALDARA_DAILY_CANDIDATES)
    if cal is None:
        return None

    date_col = _date_col(cal)
    if date_col is None or "GPRD" not in cal.columns:
        return None

    cal = cal.copy()
    cal["date"] = pd.to_datetime(cal[date_col], errors="coerce")
    cal = cal.dropna(subset=["date", "GPRD"])
    cal = cal[(cal["date"] >= pd.to_datetime(start_date)) & (cal["date"] <= pd.to_datetime(end_date))]
    top_days = cal.nlargest(top_n, "GPRD")

    ours = daily_df.copy()
    ours["date"] = pd.to_datetime(ours["date"])
    ours = ours.set_index("date").sort_index()
    gpr = ours["gpr_index"]
    pre_std = gpr.std()

    rows = []
    for _, row in top_days.iterrows():
        d = row["date"]
        caldara_gprd = float(row["GPRD"])
        if d not in ours.index:
            rows.append({
                "date": d.strftime("%Y-%m-%d"),
                "caldara_gprd": round(caldara_gprd, 1),
                "our_gpr_index": float("nan"),
                "our_in_top_quartile": "N/A (GKG gap)",
                "z_score_vs_year": float("nan"),
            })
            continue
        our_val = float(ours.loc[d, "gpr_index"])
        year_mean = gpr.mean()
        z = (our_val - year_mean) / pre_std if pre_std > 0 else float("nan")
        p75 = gpr.quantile(0.75)
        rows.append({
            "date": d.strftime("%Y-%m-%d"),
            "caldara_gprd": round(caldara_gprd, 1),
            "our_gpr_index": round(our_val, 2),
            "our_in_top_quartile": "YES" if our_val >= p75 else "NO",
            "z_score_vs_year": round(z, 3) if not np.isnan(z) else float("nan"),
        })
    return pd.DataFrame(rows)


def check_gap_period_analysis(output_dir: Path, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """Document Caldara GPRD during GKG-missing dates vs our forward-filled index."""
    cal = _load_caldara_xls(CALDARA_DAILY_CANDIDATES)
    missing_path = output_dir / "gkg_missing_dates.txt"
    cont_path = output_dir / "gpr_daily_index_continuous.csv"
    if cal is None or not missing_path.exists() or not cont_path.exists():
        return None

    missing_dates = pd.to_datetime([
        l.strip() for l in missing_path.read_text().splitlines()
        if l.strip() and not l.strip().startswith("#") and l.strip()[0].isdigit()
    ], format="%Y-%m-%d", errors="coerce")
    missing_dates = missing_dates.dropna()
    missing_dates = missing_dates[
        (missing_dates >= pd.to_datetime(start_date)) &
        (missing_dates <= pd.to_datetime(end_date))
    ]
    if len(missing_dates) == 0:
        return None

    date_col = _date_col(cal)
    cal = cal.copy()
    cal["date"] = pd.to_datetime(cal[date_col], errors="coerce")
    cal_gap = cal[cal["date"].isin(missing_dates)].copy()

    cont = pd.read_csv(cont_path, parse_dates=["date"])
    our_gap = cont[cont["date"].isin(missing_dates)][["date", "gpr_index", "is_imputed"]]

    merged = cal_gap.merge(our_gap, on="date", how="left")
    if merged.empty:
        return None

    rows = []
    for _, r in merged.iterrows():
        rows.append({
            "date": r["date"].strftime("%Y-%m-%d"),
            "caldara_gprd": round(float(r["GPRD"]), 1) if "GPRD" in r and pd.notna(r["GPRD"]) else float("nan"),
            "our_gpr_index": round(float(r["gpr_index"]), 2) if pd.notna(r.get("gpr_index")) else float("nan"),
            "is_imputed": r.get("is_imputed", True),
            "caldara_vs_imputed_gap": round(float(r["GPRD"]) - float(r["gpr_index"]), 1)
                if "GPRD" in r and pd.notna(r["GPRD"]) and pd.notna(r.get("gpr_index")) else float("nan"),
        })

    summary = pd.DataFrame(rows)
    summary.attrs["caldara_mean"] = round(float(cal_gap["GPRD"].mean()), 1)
    summary.attrs["our_imputed_mean"] = round(float(our_gap["gpr_index"].mean()), 2)
    return summary


def check_ma30_statistical_properties(daily_df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Statistical properties on 30-day moving average (smoother series)."""
    if "gpr_30ma" not in daily_df.columns:
        return None
    gpr = daily_df["gpr_30ma"].dropna()
    if len(gpr) < 30:
        return None
    autocorr = gpr.autocorr(lag=90) if len(gpr) > 90 else float("nan")
    checks = [
        ("std",            gpr.std(),         "35–70",   lambda v: 35 <= v <= 70),
        ("skewness",       float(gpr.skew()), "> 0.5",   lambda v: v > 0.5),
        ("p99",            gpr.quantile(0.99), "200–400", lambda v: 200 <= v <= 400),
        ("autocorr_lag90", autocorr,          "> 0.50",  lambda v: v > 0.50),
    ]
    rows = []
    for metric, value, target, fn in checks:
        passed = fn(value) if not (isinstance(value, float) and np.isnan(value)) else False
        rows.append({"metric": metric, "value": round(float(value), 4),
                     "target": target, "pass": "YES" if passed else "NO",
                     "series": "gpr_30ma"})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Coverage report
# ---------------------------------------------------------------------------

def check_coverage(
    output_dir: Path,
    daily_df: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    rows = []

    # Autocorr on sparse series
    gpr = daily_df["gpr_index"].dropna()
    rows.append({
        "metric": "autocorr_lag90_sparse",
        "series": "gpr_daily_index.csv",
        "value": round(float(gpr.autocorr(lag=90)), 4) if len(gpr) > 90 else float("nan"),
        "days": len(gpr),
    })

    # Autocorr on continuous series
    cont_path = output_dir / "gpr_daily_index_continuous.csv"
    if cont_path.exists():
        cont = pd.read_csv(cont_path, parse_dates=["date"])
        cont = cont[
            (cont["date"] >= pd.to_datetime(start_date)) &
            (cont["date"] <= pd.to_datetime(end_date))
        ]
        cgpr = cont["gpr_index"].dropna()
        rows.append({
            "metric": "autocorr_lag90_continuous",
            "series": "gpr_daily_index_continuous.csv",
            "value": round(float(cgpr.autocorr(lag=90)), 4) if len(cgpr) > 90 else float("nan"),
            "days": len(cgpr),
        })

    # Article count stats
    if "total_articles" in daily_df.columns:
        ta = daily_df["total_articles"]
        rows.append({"metric": "articles_mean",   "series": "observed", "value": round(float(ta.mean()), 0), "days": len(ta)})
        rows.append({"metric": "articles_std",    "series": "observed", "value": round(float(ta.std()), 0),  "days": len(ta)})
        rows.append({"metric": "articles_min",    "series": "observed", "value": float(ta.min()),              "days": len(ta)})
        rows.append({"metric": "articles_max",    "series": "observed", "value": float(ta.max()),              "days": len(ta)})

    # Missing GKG dates
    missing_path = output_dir / "gkg_missing_dates.txt"
    if missing_path.exists():
        missing = [l.strip() for l in missing_path.read_text().splitlines() if l.strip()]
        rows.append({"metric": "gkg_missing_days", "series": "gap", "value": len(missing), "days": len(missing)})

    expected = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1
    rows.append({"metric": "observed_days",  "series": "coverage", "value": len(daily_df), "days": expected})
    rows.append({"metric": "expected_days",  "series": "coverage", "value": expected,      "days": expected})

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# India-specific checks (only run when --benchmark gprc_ind)
# ---------------------------------------------------------------------------

def check_source_coverage(output_dir: Path, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """Per-outlet article count per day. Flags gaps > 7 consecutive days."""
    scores_path = output_dir / "gpr_article_scores.parquet"
    if not scores_path.exists():
        # Try batch files
        batch_files = sorted(output_dir.glob("_scores_batch_*.parquet"))
        if not batch_files:
            print("[WARN] No article scores parquet — skipping source coverage check")
            return None
        import pandas as _pd
        df = _pd.concat([_pd.read_parquet(f) for f in batch_files], ignore_index=True)
    else:
        import pandas as _pd
        df = _pd.read_parquet(scores_path)

    if "SourceCommonName" not in df.columns or "SQLDATE" not in df.columns:
        return None

    df["date"] = _pd.to_datetime(df["SQLDATE"]).dt.normalize()
    df = df[
        (df["date"] >= _pd.to_datetime(start_date)) &
        (df["date"] <= _pd.to_datetime(end_date))
    ]

    coverage = (
        df.groupby(["date", "SourceCommonName"])
        .size()
        .reset_index(name="articles")
    )
    return coverage


def check_theme_distribution(output_dir: Path) -> Optional[pd.DataFrame]:
    """TIER1/2/3 share of GPR-positive articles — sanity check the tagger."""
    scores_path = output_dir / "gpr_article_scores.parquet"
    if not scores_path.exists():
        batch_files = sorted(output_dir.glob("_scores_batch_*.parquet"))
        if not batch_files:
            return None
        import pandas as _pd
        df = _pd.concat([_pd.read_parquet(f) for f in batch_files], ignore_index=True)
    else:
        import pandas as _pd
        df = _pd.read_parquet(scores_path)

    from scripts.gkg_gpr_pipeline import TIER1, TIER2, TIER3, GPR_POSITIVE_THRESHOLD  # noqa: PLC0415
    pos = df[df["gpr_score"] > GPR_POSITIVE_THRESHOLD]
    if pos.empty or "gpr_type" not in pos.columns:
        return None

    counts = pos["gpr_type"].value_counts()
    total = len(pos)
    rows = []
    for label in ["tier1_act", "tier2_threat", "tier3_context", "other"]:
        rows.append({
            "gpr_type":   label,
            "count":      int(counts.get(label, 0)),
            "share_pct":  round(counts.get(label, 0) / total * 100, 1) if total > 0 else 0.0,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Run all checks
# ---------------------------------------------------------------------------

def run(
    output_dir: Path,
    start_date: str,
    end_date: str,
    benchmark: str = "all",
) -> None:
    val_dir = output_dir / "validation"
    val_dir.mkdir(parents=True, exist_ok=True)

    daily_path   = output_dir / "gpr_daily_index.csv"
    monthly_path = output_dir / "gpr_monthly_index.csv"
    scores_path  = output_dir / "gpr_article_scores.parquet"

    if not daily_path.exists():
        raise FileNotFoundError(f"gpr_daily_index.csv not found in {output_dir} — run gkg_gpr_pipeline.py first")

    daily_df   = pd.read_csv(daily_path,   parse_dates=["date"])
    monthly_df = pd.read_csv(monthly_path) if monthly_path.exists() else pd.DataFrame()

    # Prefer calendar-complete continuous series for statistical checks
    cont_path = output_dir / "gpr_daily_index_continuous.csv"
    stat_df_source = "gpr_daily_index.csv (observed)"
    if cont_path.exists():
        cont_df = pd.read_csv(cont_path, parse_dates=["date"])
        cont_df = cont_df[
            (cont_df["date"] >= pd.to_datetime(start_date)) &
            (cont_df["date"] <= pd.to_datetime(end_date))
        ]
        if len(cont_df) >= len(daily_df):
            daily_df_for_stats = cont_df
            stat_df_source = "gpr_daily_index_continuous.csv"
        else:
            daily_df_for_stats = daily_df
    else:
        daily_df_for_stats = daily_df

    daily_df = daily_df[
        (daily_df["date"] >= pd.to_datetime(start_date)) &
        (daily_df["date"] <= pd.to_datetime(end_date))
    ]
    daily_df_for_stats = daily_df_for_stats[
        (daily_df_for_stats["date"] >= pd.to_datetime(start_date)) &
        (daily_df_for_stats["date"] <= pd.to_datetime(end_date))
    ]

    n_days = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1
    use_lag1 = n_days < 1000  # paper lag-90 target requires multi-year history

    print("\n" + "="*60)
    print(f"CHECK 1: Statistical Properties  [{stat_df_source}]")
    if use_lag1:
        print("  (autocorr: lag-1 for single-year sample; lag-90 needs multi-year data)")
    print("="*60)
    stat_df = check_statistical_properties(daily_df_for_stats, use_lag1_autocorr=use_lag1)
    print(stat_df.to_string(index=False))
    stat_df.to_csv(val_dir / "statistical_properties.csv", index=False)

    print("\n" + "="*60)
    print("CHECK 2: Component Contributions")
    print("="*60)
    comp_df = check_component_contributions(scores_path)
    if comp_df is not None:
        print(comp_df.to_string(index=False))
        comp_df.to_csv(val_dir / "component_contributions.csv", index=False)
    else:
        print("  Skipped (no article scores file)")

    print("\n" + "="*60)
    print("CHECK 3: Event Spike Validation")
    print("="*60)
    events = KNOWN_EVENTS_INDIA_2026 if benchmark == "gprc_ind" else KNOWN_EVENTS_2025
    spike_df = check_event_spikes(daily_df, events=events)
    print(spike_df.to_string(index=False))
    spike_df.to_csv(val_dir / "event_spike_analysis.csv", index=False)

    print("\n" + "="*60)
    print("CHECK 4: Caldara Monthly Correlation")
    print("="*60)
    if not monthly_df.empty:
        corr_df = check_caldara_correlation(monthly_df, benchmark=benchmark)
        if corr_df is not None:
            print(corr_df.to_string(index=False))
            corr_df.to_csv(val_dir / "caldara_correlation.csv", index=False)
        else:
            print("  Skipped (Caldara monthly file not found)")
    else:
        print("  Skipped (gpr_monthly_index.csv not found)")

    print("\n" + "="*60)
    print("CHECK 5: Caldara Daily Correlation")
    print("="*60)
    daily_corr_df = check_caldara_daily_correlation(daily_df)
    if daily_corr_df is not None:
        print(daily_corr_df.to_string(index=False))
        daily_corr_df.to_csv(val_dir / "caldara_daily_correlation.csv", index=False)
    else:
        print("  Skipped (Caldara daily file not found)")

    print("\n" + "="*60)
    print("CHECK 6: Caldara Spike Cross-Check (top 10 Caldara days)")
    print("="*60)
    spike_x_df = check_caldara_spike_cross(daily_df, start_date, end_date)
    if spike_x_df is not None:
        print(spike_x_df.to_string(index=False))
        spike_x_df.to_csv(val_dir / "caldara_spike_crosscheck.csv", index=False)
    else:
        print("  Skipped")

    print("\n" + "="*60)
    print("CHECK 7: Gap Period Analysis (Caldara vs imputed)")
    print("="*60)
    gap_df = check_gap_period_analysis(output_dir, start_date, end_date)
    if gap_df is not None:
        print(f"  Caldara mean GPRD during gap : {gap_df.attrs.get('caldara_mean', 'N/A')}")
        print(f"  Our imputed mean             : {gap_df.attrs.get('our_imputed_mean', 'N/A')}")
        print(gap_df.to_string(index=False))
        gap_df.to_csv(val_dir / "gap_caldara_comparison.csv", index=False)
    else:
        print("  Skipped")

    print("\n" + "="*60)
    print("CHECK 8: Statistical Properties (30-day MA)")
    print("="*60)
    ma30_df = check_ma30_statistical_properties(daily_df)
    if ma30_df is not None:
        print(ma30_df.to_string(index=False))
        ma30_df.to_csv(val_dir / "statistical_properties_ma30.csv", index=False)
    else:
        print("  Skipped (gpr_30ma not available)")

    print("\n" + "="*60)
    print("COVERAGE REPORT")
    print("="*60)
    cov_df = check_coverage(output_dir, daily_df, start_date, end_date)
    print(cov_df.to_string(index=False))
    cov_df.to_csv(val_dir / "coverage_report.csv", index=False)

    # India-specific checks (only when --benchmark gprc_ind)
    if benchmark == "gprc_ind":
        print("\n" + "="*60)
        print("CHECK 9: Source Coverage (India newspaper path)")
        print("="*60)
        src_df = check_source_coverage(output_dir, start_date, end_date)
        if src_df is not None:
            summary = src_df.groupby("SourceCommonName")["articles"].agg(["mean", "min", "max"]).round(1)
            print(summary.to_string())
            src_df.to_csv(val_dir / "source_coverage.csv", index=False)
        else:
            print("  Skipped (no article scores available)")

        print("\n" + "="*60)
        print("CHECK 10: Theme Tag Distribution (TIER1/2/3 share)")
        print("="*60)
        theme_df = check_theme_distribution(output_dir)
        if theme_df is not None:
            print(theme_df.to_string(index=False))
            theme_df.to_csv(val_dir / "theme_tag_distribution.csv", index=False)
        else:
            print("  Skipped (no article scores or gpr_type column available)")

    passed = int((stat_df["pass"] == "YES").sum())
    total  = len(stat_df)
    print(f"\n{'='*60}")
    print(f"SCORECARD: {passed}/{total} statistical checks passed")
    if benchmark == "gprc_ind":
        print("  (India path — primary benchmark: GPRC_IND; pass threshold 0.45)")
    print(f"Validation reports saved to {val_dir}/")
    print("="*60)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate GPR pipeline outputs")
    p.add_argument("--output-dir",   default="outputs",      help="Directory containing gpr_*.csv outputs")
    p.add_argument("--start-date",   default="2025-01-01",   help="YYYY-MM-DD")
    p.add_argument("--end-date",     default="2025-12-31",   help="YYYY-MM-DD")
    p.add_argument(
        "--benchmark",
        default="all",
        choices=["all", "gprc_ind"],
        help="'all' (default): compare vs global GPR + GPRC_IND. "
             "'gprc_ind': India path — compare vs GPRC_IND only (pass threshold 0.45) "
             "and run India-specific coverage + theme checks.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run(
        output_dir=Path(args.output_dir),
        start_date=args.start_date,
        end_date=args.end_date,
        benchmark=args.benchmark,
    )


if __name__ == "__main__":
    main()
