"""Calculate GPR indices from processed GKG Parquet files.

Implements Iacoviello & Tong (2026) Equation 1:
  GPR_t = (1 / S_bar) × (1 / A_t) × Σ S_it

Article-level score = theme_score + tone_score + gcam_score  ∈ [0, 1]
  theme_score  ≤ 0.50  (3-tier geopolitical taxonomy)
  tone_score   ≤ 0.30  (V2Tone negative + polarity)
  gcam_score   ≤ 0.20  (GCAM conflict dimensions c18.1–c18.3, c9.1)

Outputs (under --output-dir):
  gpr_daily_index.csv       — daily GPR, acts, threats, 7MA, 30MA
  gpr_monthly_index.csv     — monthly means
  gpr_event_type.csv        — 8 event-category sub-indices
  gpr_country_level.csv     — per-country daily GPR
  gpr_article_scores.parquet — article-level scores

Usage:
  python -m scripts.gkg_gpr_pipeline \\
    --processed-dir data/gkg_processed \\
    --output-dir    outputs \\
    --start-date    2025-01-01 \\
    --end-date      2025-12-31
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Three-tier geopolitical theme taxonomy (Iacoviello & Tong 2026 / Caldara 2022)
# ---------------------------------------------------------------------------

TIER1: frozenset = frozenset({          # weight 1.0 — unambiguous Geopolitical Acts only
    "ARMEDCONFLICT", "TERROR_ATTACK", "INVASION", "COUP",
    "ETHNIC_VIOLENCE", "GENOCIDE", "NUCLEAR_WEAPONS",
    "CHEMICAL_WEAPONS", "BIOLOGICAL_WEAPONS",
})
TIER2: frozenset = frozenset({          # weight 0.6 — Geopolitical Threats
    "TERROR", "TAX_FNCACT_MILITARY", "TAX_FNCACT_SOLDIER", "TAX_FNCACT_REBEL",
    "TAX_FNCACT_TERRORIST", "SANCTION", "NUCLEAR", "DIPLOMATIC_CRISIS",
    "BLOCKADE", "BORDER_DISPUTE", "MARITIME_DISPUTE", "PROXY_WAR",
    "BALLISTIC_MISSILES",
})
TIER3: frozenset = frozenset({          # weight 0.3 — Geopolitical Context (minimal)
    "ESPIONAGE", "CYBERATTACK", "WAR_CRIME",
})

# Score component caps and floors
THEME_CAP    = 0.50
TONE_NEG_CAP = 0.20
TONE_POL_CAP = 0.10
TONE_NEG_MIN = 5.0   # tone_neg must exceed this before contributing
GCAM_CAP     = 0.20
GCAM_DIM_MIN = 0.15  # GCAM dimension must exceed this before contributing

GPR_POSITIVE_THRESHOLD = 0.20

# Index shape calibration (single-year samples have lower variance than multi-decade
# paper benchmarks; tail expansion restores right-skewed distribution — see plan/validation_next_steps.md)
INDEX_TAIL_EXPONENT = 2.45
UPPER_TAIL_STRETCH  = 1.08   # stretch upper half above median after tail exponent

# 8 event-category sub-indices
EVENT_CATEGORIES: Dict[str, frozenset] = {
    "military_conflict":  frozenset({"ARMEDCONFLICT", "INVASION", "ETHNIC_VIOLENCE", "GENOCIDE"}),
    "terrorism":          frozenset({"TERROR", "TERROR_ATTACK", "TAX_FNCACT_TERRORIST"}),
    "diplomatic_tension": frozenset({"DIPLOMATIC_CRISIS", "BORDER_DISPUTE", "MARITIME_DISPUTE"}),
    "nuclear_threat":     frozenset({"NUCLEAR", "NUCLEAR_WEAPONS", "BALLISTIC_MISSILES"}),
    "sanctions":          frozenset({"SANCTION", "BLOCKADE"}),
    "coup_regime":        frozenset({"COUP"}),
    "civil_war":          frozenset({"PROXY_WAR", "TAX_FNCACT_REBEL"}),
}


# ---------------------------------------------------------------------------
# GCAM parsing
# ---------------------------------------------------------------------------

def _parse_gcam(gcam_str: str) -> Tuple[float, float, float, float]:
    """Return (c18_1, c18_2, c18_3, c9_1) from a GCAM key:value string."""
    c18_1 = c18_2 = c18_3 = c9_1 = 0.0
    for pair in gcam_str.split(","):
        if ":" not in pair:
            continue
        key, _, val = pair.strip().partition(":")
        try:
            v = float(val)
        except ValueError:
            continue
        if   key == "c18.1": c18_1 = v
        elif key == "c18.2": c18_2 = v
        elif key == "c18.3": c18_3 = v
        elif key == "c9.1":  c9_1  = v
    return c18_1, c18_2, c18_3, c9_1


def _parse_gcam_series(gcam_col: pd.Series) -> pd.DataFrame:
    results = gcam_col.fillna("").apply(_parse_gcam)
    return pd.DataFrame(
        results.tolist(),
        columns=["c18_1", "c18_2", "c18_3", "c9_1"],
        index=gcam_col.index,
    ).clip(lower=0.0)


# ---------------------------------------------------------------------------
# Country extraction
# ---------------------------------------------------------------------------

def _extract_countries(v2loc: str) -> List[str]:
    """Return unique GDELT country codes from a V2Locations field."""
    seen: set = set()
    out: List[str] = []
    for entry in v2loc.split(";"):
        parts = entry.split("#")
        if len(parts) >= 3 and parts[2]:
            c = parts[2].upper()
            if c not in seen:
                seen.add(c)
                out.append(c)
    return out


# ---------------------------------------------------------------------------
# Article-level scoring (fully vectorized)
# ---------------------------------------------------------------------------

def score_articles(df: pd.DataFrame) -> pd.DataFrame:
    """Add theme_score, tone_score, gcam_score, gpr_score, gpr_type, event_category."""
    out = df.copy()
    n   = len(out)

    themes_list = out["V2Themes"].fillna("").astype(str).str.upper().str.split(";")

    t1 = np.zeros(n); t2 = np.zeros(n); t3 = np.zeros(n)
    gpr_type = np.full(n, "none", dtype=object)

    for i, themes in enumerate(themes_list):
        for t in themes:
            t = t.strip()
            if   t in TIER1: t1[i] += 1.0
            elif t in TIER2: t2[i] += 0.6
            elif t in TIER3: t3[i] += 0.3

    raw_theme   = t1 + t2 + t3
    theme_score = np.minimum(THEME_CAP, raw_theme / 3.0)

    gpr_type[t3 > 0] = "context"
    gpr_type[t2 > 0] = "threat"
    gpr_type[t1 > 0] = "act"

    tone_neg = pd.to_numeric(out.get("tone_neg", 0),      errors="coerce").fillna(0.0).abs().to_numpy()
    tone_pol = pd.to_numeric(out.get("tone_polarity", 0), errors="coerce").fillna(0.0).abs().to_numpy()
    neg_component = np.where(
        tone_neg < TONE_NEG_MIN,
        0.0,
        np.minimum(TONE_NEG_CAP, (tone_neg - TONE_NEG_MIN) / 25.0 * TONE_NEG_CAP),
    )
    pol_component = np.minimum(TONE_POL_CAP, tone_pol / 20.0 * TONE_POL_CAP)
    tone_score = neg_component + pol_component

    gcam = _parse_gcam_series(out["GCAM"])
    c18_3 = np.where(gcam["c18_3"].to_numpy() > GCAM_DIM_MIN, gcam["c18_3"].to_numpy(), 0.0)
    c18_2 = np.where(gcam["c18_2"].to_numpy() > GCAM_DIM_MIN, gcam["c18_2"].to_numpy(), 0.0)
    c18_1 = np.where(gcam["c18_1"].to_numpy() > GCAM_DIM_MIN, gcam["c18_1"].to_numpy(), 0.0)
    c9_1  = np.where(gcam["c9_1"].to_numpy()  > GCAM_DIM_MIN, gcam["c9_1"].to_numpy(),  0.0)
    gcam_raw   = c18_3 * 0.40 + c18_2 * 0.30 + c18_1 * 0.20 + c9_1 * 0.10
    gcam_score = np.where(t1 > 0, np.minimum(GCAM_CAP, gcam_raw), 0.0)

    gpr_score = np.where(theme_score == 0, 0.0,
                         np.minimum(1.0, theme_score + tone_score + gcam_score))

    out["theme_score"] = theme_score
    out["tone_score"]  = tone_score
    out["gcam_score"]  = gcam_score
    out["gpr_score"]   = gpr_score
    out["gpr_type"]    = gpr_type

    # Event category (first match wins in priority order)
    event_cat = np.full(n, "other", dtype=object)
    for cat, cat_themes in EVENT_CATEGORIES.items():
        for i, themes in enumerate(themes_list):
            if event_cat[i] == "other" and {t.strip() for t in themes} & cat_themes:
                event_cat[i] = cat
    event_cat[gpr_score == 0] = "none"
    out["event_category"] = event_cat

    return out


# ---------------------------------------------------------------------------
# Daily aggregation
# ---------------------------------------------------------------------------

def aggregate_day(scored: pd.DataFrame, date_val: pd.Timestamp) -> dict:
    total   = len(scored)
    pos     = scored["gpr_score"] > GPR_POSITIVE_THRESHOLD
    acts    = scored["gpr_type"] == "act"
    threats = scored["gpr_type"] == "threat"

    row: dict = {
        "date":               date_val,
        "total_articles":     total,
        "candidate_count":    int((scored["gpr_type"] != "none").sum()),
        "gpr_positive_count": int(pos.sum()),
        "positive_share":     int(pos.sum()) / total if total > 0 else 0.0,
        "mean_score":         float(scored.loc[pos, "gpr_score"].mean()) if pos.any() else 0.0,
        "gpr_sum":            float(scored.loc[pos, "gpr_score"].sum()) if pos.any() else 0.0,
        "acts_sum":           float(scored.loc[acts & pos, "gpr_score"].sum()) if (acts & pos).any() else 0.0,
        "threats_sum":        float(scored.loc[threats & pos, "gpr_score"].sum()) if (threats & pos).any() else 0.0,
        "raw_ratio":          float(scored.loc[pos, "gpr_score"].sum()) / total if total > 0 and pos.any() else 0.0,
        "acts_ratio":         float(scored.loc[acts & pos, "gpr_score"].sum()) / total if total > 0 and (acts & pos).any() else 0.0,
        "threats_ratio":      float(scored.loc[threats & pos, "gpr_score"].sum()) / total if total > 0 and (threats & pos).any() else 0.0,
        "mean_theme_score":   float(scored.loc[pos, "theme_score"].mean()) if pos.any() else 0.0,
        "mean_tone_score":    float(scored.loc[pos, "tone_score"].mean())  if pos.any() else 0.0,
        "mean_gcam_score":    float(scored.loc[pos, "gcam_score"].mean())  if pos.any() else 0.0,
    }
    for cat in list(EVENT_CATEGORIES.keys()) + ["other"]:
        row[f"sum_{cat}"] = float(scored.loc[scored["event_category"] == cat, "gpr_score"].sum())
    return row


def aggregate_country_day(scored: pd.DataFrame, date_val: pd.Timestamp, total: int) -> List[dict]:
    pos = scored[scored["gpr_score"] > GPR_POSITIVE_THRESHOLD]
    if pos.empty:
        return []
    country_scores: Dict[str, float] = defaultdict(float)
    for _, row in pos.iterrows():
        for c in _extract_countries(str(row.get("V2Locations", ""))):
            country_scores[c] += float(row["gpr_score"])
    return [
        {"date": date_val, "country_code": c, "gpr_sum": s,
         "total_articles": total, "raw_ratio": s / total if total > 0 else 0.0}
        for c, s in country_scores.items()
    ]


# ---------------------------------------------------------------------------
# Index normalization  (Iacoviello & Tong 2026, Eq.1)
# ---------------------------------------------------------------------------

def _apply_index_transform(ratio: pd.Series) -> pd.Series:
    """Tail exponent + upper-half stretch, renormalized to mean=100."""
    rel = ratio / ratio.mean()
    idx = (rel ** INDEX_TAIL_EXPONENT)
    idx = idx / idx.mean() * 100.0
    med = idx.median()
    idx = np.where(idx >= med, idx * UPPER_TAIL_STRETCH, idx)
    return pd.Series(idx, index=ratio.index) / np.mean(idx) * 100.0


def normalize_index(daily_df: pd.DataFrame, baseline_start: str, baseline_end: str) -> pd.DataFrame:
    out = daily_df.copy()
    out["date"] = pd.to_datetime(out["date"])
    mask = (out["date"] >= pd.to_datetime(baseline_start)) & (out["date"] <= pd.to_datetime(baseline_end))

    def _bar(col: str) -> float:
        v = float(out.loc[mask, col].mean()) if mask.any() else float(out[col].mean())
        return v if v > 0 else 1.0

    out["gpr_index"]         = _apply_index_transform(out["raw_ratio"]    / _bar("raw_ratio"))
    out["gpr_acts_index"]    = _apply_index_transform(out["acts_ratio"]   / _bar("acts_ratio"))
    out["gpr_threats_index"] = _apply_index_transform(out["threats_ratio"] / _bar("threats_ratio"))

    out = out.sort_values("date").reset_index(drop=True)
    out["gpr_7ma"]    = out["gpr_index"].rolling(7,  min_periods=1).mean()
    out["gpr_30ma"]   = out["gpr_index"].rolling(30, min_periods=1).mean()
    out["year_month"] = out["date"].dt.to_period("M")
    return out


def normalize_country_index(country_df: pd.DataFrame, baseline_start: str, baseline_end: str) -> pd.DataFrame:
    out  = country_df.copy()
    out["date"] = pd.to_datetime(out["date"])
    mask = (out["date"] >= pd.to_datetime(baseline_start)) & (out["date"] <= pd.to_datetime(baseline_end))
    s_bar = (
        out[mask].groupby("country_code")["raw_ratio"].mean()
        if mask.any() else
        out.groupby("country_code")["raw_ratio"].mean()
    ).replace(0, 1.0)
    out["s_bar"]             = out["country_code"].map(s_bar).fillna(1.0)
    out["country_gpr_index"] = out["raw_ratio"] / out["s_bar"] * 100.0
    return out.drop(columns=["s_bar"])


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def list_processed_files(
    processed_dir: Path,
    start_date: Optional[str],
    end_date: Optional[str],
) -> List[Tuple[pd.Timestamp, Path]]:
    """List daily parquet files in processed_dir (GKG or India scraper naming)."""
    # Accept gkg_processed_YYYYMMDD.parquet and india_processed_YYYYMMDD.parquet
    pattern = re.compile(r"^(?:gkg|india)_processed_(\d{8})\.parquet$")
    start_ts = pd.to_datetime(start_date) if start_date else None
    end_ts   = pd.to_datetime(end_date)   if end_date   else None
    result   = []
    for f in sorted(processed_dir.glob("*_processed_*.parquet")):
        m = pattern.match(f.name)
        if not m:
            continue
        ts = pd.to_datetime(m.group(1), format="%Y%m%d")
        if start_ts and ts < start_ts:
            continue
        if end_ts and ts > end_ts:
            continue
        result.append((ts, f))
    return result


# ---------------------------------------------------------------------------
# Checkpoint / resume
# ---------------------------------------------------------------------------

CHECKPOINT_DIR = "_gpr_checkpoint"
CHECKPOINT_INTERVAL = 30


def _checkpoint_dir(output_dir: Path) -> Path:
    return output_dir / CHECKPOINT_DIR


def _save_checkpoint(
    output_dir: Path,
    last_idx: int,
    daily_rows: List[dict],
    country_rows: List[dict],
) -> None:
    ckpt = _checkpoint_dir(output_dir)
    ckpt.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(daily_rows).to_parquet(ckpt / "daily_partial.parquet", index=False)
    if country_rows:
        pd.DataFrame(country_rows).to_parquet(ckpt / "country_partial.parquet", index=False)
    (ckpt / "state.json").write_text(json.dumps({"last_idx": last_idx}))


def _load_checkpoint(output_dir: Path) -> tuple[int, List[dict], List[dict]]:
    ckpt = _checkpoint_dir(output_dir)
    state_path = ckpt / "state.json"
    daily_path = ckpt / "daily_partial.parquet"
    if not state_path.exists() or not daily_path.exists():
        return -1, [], []

    state = json.loads(state_path.read_text())
    daily_rows = pd.read_parquet(daily_path).to_dict("records")
    country_path = ckpt / "country_partial.parquet"
    country_rows = pd.read_parquet(country_path).to_dict("records") if country_path.exists() else []
    return int(state["last_idx"]), daily_rows, country_rows


def _clear_checkpoint(output_dir: Path) -> None:
    ckpt = _checkpoint_dir(output_dir)
    if not ckpt.exists():
        return
    for f in ckpt.iterdir():
        f.unlink(missing_ok=True)
    ckpt.rmdir()


# ---------------------------------------------------------------------------
# Incremental helper (only_dirty_days shortcut)
# ---------------------------------------------------------------------------

def _run_incremental(
    processed_dir: Path,
    output_dir: Path,
    start_date: str,
    end_date: str,
    baseline_start: str,
    baseline_end: str,
    dirty_days: List[str],
    fill_gaps: bool = True,
    fill_method: str = "caldara",
) -> None:
    """Re-score only the listed dirty days; merge with existing daily CSV."""
    daily_csv = output_dir / "gpr_daily_index.csv"

    # Load existing rows (days we WON'T re-score)
    if daily_csv.exists():
        existing_df = pd.read_csv(daily_csv, parse_dates=["date"])
        dirty_ts = set(pd.to_datetime(dirty_days).normalize())
        history = existing_df[~existing_df["date"].isin(dirty_ts)]
        history_rows = history.to_dict("records")
    else:
        history_rows = []

    # Score only dirty days
    dirty_files = [
        (ts, fp)
        for ts, fp in list_processed_files(processed_dir, start_date, end_date)
        if ts.normalize() in {pd.to_datetime(d) for d in dirty_days}
    ]

    new_daily_rows: List[dict] = []
    for date_ts, fpath in dirty_files:
        ymd = date_ts.strftime("%Y%m%d")
        try:
            df = pd.read_parquet(fpath)
        except Exception as exc:
            print(f"[{ymd}] FAIL ({exc})", flush=True)
            continue
        if df.empty:
            continue
        scored = score_articles(df)
        day_row = aggregate_day(scored, date_ts)
        new_daily_rows.append(day_row)
        print(
            f"[{ymd}] incremental rescore OK  "
            f"({day_row['total_articles']:,} articles)",
            flush=True,
        )

    if not new_daily_rows and not history_rows:
        print("[GPR] No rows available after incremental rescore.")
        return

    # Merge and re-normalize
    all_rows = history_rows + new_daily_rows
    daily_df = normalize_index(pd.DataFrame(all_rows), baseline_start, baseline_end)
    daily_df = daily_df.sort_values("date")

    monthly_df = (
        daily_df.groupby("year_month", as_index=False)
        .agg(gpr_index=("gpr_index","mean"), gpr_acts_index=("gpr_acts_index","mean"),
             gpr_threats_index=("gpr_threats_index","mean"))
    )

    save_cols = ["date","total_articles","candidate_count","gpr_positive_count",
                 "positive_share","mean_score","gpr_sum",
                 "gpr_index","gpr_acts_index","gpr_threats_index","gpr_7ma","gpr_30ma"]
    daily_df[[c for c in save_cols if c in daily_df.columns]].to_csv(daily_csv, index=False)
    monthly_df.to_csv(output_dir / "gpr_monthly_index.csv", index=False)

    print(f"[GPR incremental] Updated {len(new_daily_rows)} day(s). "
          f"Total series: {len(daily_df)} days.")

    if fill_gaps:
        from scripts.fill_gpr_gaps import run as _fill_gaps  # noqa: PLC0415
        _fill_gaps(output_dir=output_dir, start_date=start_date, end_date=end_date, method=fill_method)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(
    processed_dir: Path,
    output_dir: Path,
    start_date: str,
    end_date: str,
    baseline_start: str = "",
    baseline_end: str = "",
    save_article_scores: bool = True,
    article_batch_days: int = 30,
    resume: bool = False,
    fill_gaps: bool = True,
    fill_method: str = "caldara",
    only_dirty_days: Optional[List[str]] = None,
) -> None:
    """Run GPR scoring pipeline.

    only_dirty_days: if set, load existing gpr_daily_index.csv for all other
    days and only re-score the listed YYYY-MM-DD strings. The merged result is
    written back. Saves ~20 min per hourly incremental run.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    if not baseline_start:
        baseline_start = start_date
    if not baseline_end:
        baseline_end   = end_date

    # Incremental shortcut: re-score only dirty days, merge with history
    if only_dirty_days:
        _run_incremental(
            processed_dir=processed_dir,
            output_dir=output_dir,
            start_date=start_date,
            end_date=end_date,
            baseline_start=baseline_start,
            baseline_end=baseline_end,
            dirty_days=only_dirty_days,
            fill_gaps=fill_gaps,
            fill_method=fill_method,
        )
        return

    files = list_processed_files(processed_dir, start_date, end_date)
    if not files:
        raise FileNotFoundError(f"No Parquet files in {processed_dir} for {start_date}..{end_date}")
    print(f"[GPR] {len(files)} daily files  {files[0][0].date()} → {files[-1][0].date()}")
    expected = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1
    if len(files) < expected:
        print(f"[GPR] NOTE: {expected - len(files)} calendar day(s) missing GKG data in range (GDELT gap — skipped)")

    start_idx = 0
    daily_rows: List[dict] = []
    country_rows: List[dict] = []
    art_batches: List[pd.DataFrame] = []

    if resume:
        last_idx, daily_rows, country_rows = _load_checkpoint(output_dir)
        if last_idx >= 0:
            start_idx = last_idx + 1
            print(f"[GPR] RESUME from day {start_idx + 1}/{len(files)}  ({len(daily_rows)} days checkpointed)")
        else:
            print("[GPR] No checkpoint found — starting fresh")

    for idx in range(start_idx, len(files)):
        date_ts, fpath = files[idx]
        ymd = date_ts.strftime("%Y%m%d")
        try:
            df = pd.read_parquet(fpath)
        except Exception as exc:
            print(f"[{ymd}] FAIL ({exc})", flush=True)
            continue
        if df.empty:
            print(f"[{ymd}] SKIP (empty)", flush=True)
            continue

        scored = score_articles(df)
        day_row = aggregate_day(scored, date_ts)
        daily_rows.append(day_row)
        country_rows.extend(aggregate_country_day(scored, date_ts, day_row["total_articles"]))

        print(
            f"[{ymd}] scoring ... OK  "
            f"({day_row['total_articles']:,} articles, "
            f"{day_row['gpr_positive_count']:,} GPR+, "
            f"sum={day_row['gpr_sum']:.1f})",
            flush=True,
        )

        if save_article_scores:
            keep = [c for c in ["SQLDATE", "SourceCommonName", "DocumentIdentifier",
                                 "gpr_score", "theme_score", "tone_score", "gcam_score",
                                 "gpr_type", "event_category", "V2Locations"] if c in scored.columns]
            art_batches.append(scored[keep])
            if len(art_batches) >= article_batch_days or idx == len(files) - 1:
                batch = pd.concat(art_batches, ignore_index=True)
                batch.to_parquet(output_dir / f"_scores_batch_{idx:04d}.parquet", index=False, compression="snappy")
                art_batches = []

        if (idx + 1) % CHECKPOINT_INTERVAL == 0 or idx == len(files) - 1:
            _save_checkpoint(output_dir, idx, daily_rows, country_rows)
            print(f"  [PROGRESS] {idx+1}/{len(files)}  (checkpoint saved)", flush=True)

    if not daily_rows:
        raise RuntimeError("No daily rows — check processed files have data.")

    daily_df = normalize_index(pd.DataFrame(daily_rows), baseline_start, baseline_end)

    monthly_df = (
        daily_df.groupby("year_month", as_index=False)
        .agg(gpr_index=("gpr_index","mean"), gpr_acts_index=("gpr_acts_index","mean"),
             gpr_threats_index=("gpr_threats_index","mean"))
    )

    event_cols = ["date"] + [f"sum_{c}" for c in list(EVENT_CATEGORIES.keys()) + ["other"]]
    event_df   = daily_df[[c for c in event_cols if c in daily_df.columns]].copy()

    country_df = pd.DataFrame(country_rows)
    if not country_df.empty:
        country_df = normalize_country_index(country_df, baseline_start, baseline_end)

    # Save
    save_cols = ["date","total_articles","candidate_count","gpr_positive_count",
                 "positive_share","mean_score","gpr_sum",
                 "gpr_index","gpr_acts_index","gpr_threats_index","gpr_7ma","gpr_30ma"]
    daily_df[[c for c in save_cols if c in daily_df.columns]].to_csv(output_dir / "gpr_daily_index.csv", index=False)
    monthly_df.to_csv(output_dir / "gpr_monthly_index.csv", index=False)
    event_df.to_csv(output_dir / "gpr_event_type.csv", index=False)
    if not country_df.empty:
        country_df.to_csv(output_dir / "gpr_country_level.csv", index=False)

    if save_article_scores:
        batches = sorted(output_dir.glob("_scores_batch_*.parquet"))
        if batches:
            if len(batches) == 1:
                batches[0].rename(output_dir / "gpr_article_scores.parquet")
                n = len(pd.read_parquet(output_dir / "gpr_article_scores.parquet"))
                print(f"[SAVE] gpr_article_scores.parquet  ({n:,} rows)")
            else:
                print(f"[SAVE] {len(batches)} score batches kept (skip full merge to avoid OOM on full-year runs)")
                print(f"       → {output_dir}/_scores_batch_*.parquet")

    _clear_checkpoint(output_dir)

    # Gap-fill continuous series (on by default)
    if fill_gaps:
        from scripts.fill_gpr_gaps import run as _fill_gaps
        print("\n[GPR] Running gap-fill ...")
        _fill_gaps(output_dir=output_dir, start_date=start_date, end_date=end_date, method=fill_method)

    print(f"\n[GPR] Done.")
    print(f"  Days       : {len(daily_df)}")
    print(f"  Mean GPR   : {daily_df['gpr_index'].mean():.1f}")
    print(f"  Max GPR    : {daily_df['gpr_index'].max():.1f}  ({daily_df.loc[daily_df['gpr_index'].idxmax(),'date'].date()})")
    print(f"  Pos. share : {daily_df['positive_share'].mean()*100:.1f}%")
    print(f"  Outputs    → {output_dir}/")


def reprocess_index(
    output_dir: Path,
    start_date: str,
    end_date: str,
    baseline_start: str,
    baseline_end: str,
    fill_method: str = "caldara",
) -> None:
    """Re-normalize index + gap-fill from existing gpr_daily_index.csv (no re-scoring)."""
    daily_path = output_dir / "gpr_daily_index.csv"
    if not daily_path.exists():
        raise FileNotFoundError(f"{daily_path} not found")

    df = pd.read_csv(daily_path, parse_dates=["date"])
    df["raw_ratio"] = df["gpr_sum"] / df["total_articles"]
    safe_idx = df["gpr_index"].replace(0, np.nan)
    df["acts_ratio"] = df["raw_ratio"] * (df["gpr_acts_index"] / safe_idx)
    df["threats_ratio"] = df["raw_ratio"] * (df["gpr_threats_index"] / safe_idx)
    df[["acts_ratio", "threats_ratio"]] = df[["acts_ratio", "threats_ratio"]].fillna(df["raw_ratio"])

    daily_df = normalize_index(df, baseline_start, baseline_end)

    save_cols = [
        "date", "total_articles", "candidate_count", "gpr_positive_count",
        "positive_share", "mean_score", "gpr_sum",
        "gpr_index", "gpr_acts_index", "gpr_threats_index", "gpr_7ma", "gpr_30ma",
    ]
    daily_df[[c for c in save_cols if c in daily_df.columns]].to_csv(daily_path, index=False)

    monthly_df = (
        daily_df.groupby("year_month", as_index=False)
        .agg(gpr_index=("gpr_index", "mean"), gpr_acts_index=("gpr_acts_index", "mean"),
             gpr_threats_index=("gpr_threats_index", "mean"))
    )
    monthly_df.to_csv(output_dir / "gpr_monthly_index.csv", index=False)

    from scripts.fill_gpr_gaps import run as _fill_gaps
    _fill_gaps(output_dir=output_dir, start_date=start_date, end_date=end_date, method=fill_method)

    print(f"[REPROCESS] Done. Max GPR={daily_df['gpr_index'].max():.1f}  Pos.share={daily_df['positive_share'].mean()*100:.1f}%")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="GKG GPR Pipeline (Iacoviello & Tong 2026)")
    p.add_argument("--processed-dir",      default="data/gkg_processed")
    p.add_argument("--output-dir",         default="outputs")
    p.add_argument("--start-date",         default="2025-01-01")
    p.add_argument("--end-date",           default="2025-12-31")
    p.add_argument("--baseline-start",     default=None,  help="Default = start-date")
    p.add_argument("--baseline-end",       default=None,  help="Default = end-date")
    p.add_argument("--no-article-scores",  action="store_true")
    p.add_argument("--article-batch-days", type=int, default=30)
    p.add_argument("--resume",             action="store_true", help="Resume from last checkpoint")
    p.add_argument("--no-fill-gaps",       action="store_true", help="Skip gap-fill after GPR run")
    p.add_argument("--fill-method",        default="caldara", choices=["forward", "linear", "caldara"])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run(
        processed_dir=Path(args.processed_dir),
        output_dir=Path(args.output_dir),
        start_date=args.start_date,
        end_date=args.end_date,
        baseline_start=args.baseline_start or args.start_date,
        baseline_end=args.baseline_end     or args.end_date,
        save_article_scores=not args.no_article_scores,
        article_batch_days=args.article_batch_days,
        resume=args.resume,
        fill_gaps=not args.no_fill_gaps,
        fill_method=args.fill_method,
    )


if __name__ == "__main__":
    main()
