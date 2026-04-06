"""Prototype India GPR pipeline using GDELT Events (+ optional GKG tone).

Implements:
- Cleaning
- Deduplication (before NLP)
- India + conflict filtering
- DistilBERT sentiment scoring
- Hybrid risk construction
- Daily and monthly GPR index generation

Outputs:
- daily_india_gpr_final.csv
- monthly_india_gpr_index_final.csv
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


EVENT_COLS = [
    "SQLDATE",
    "Actor1CountryCode",
    "Actor2CountryCode",
    "EventCode",
    "NumMentions",
    "GoldsteinScale",
    "SOURCEURL",
]

GKG_COLS = ["DocumentIdentifier", "V2Tone"]
CONFLICT_PREFIXES = ("13", "17", "19")


def load_data(
    events_path: str,
    gkg_path: Optional[str] = None,
    max_rows: Optional[int] = None,
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """Load events CSV and optional GKG CSV."""
    events_df = pd.read_csv(events_path, nrows=max_rows, low_memory=False)
    for col in EVENT_COLS:
        if col not in events_df.columns:
            if col in {"NumMentions", "GoldsteinScale"}:
                events_df[col] = 0
            else:
                events_df[col] = ""
    events_df = events_df[EVENT_COLS].copy()

    gkg_df: Optional[pd.DataFrame] = None
    if gkg_path:
        gkg_df = pd.read_csv(gkg_path, nrows=max_rows, low_memory=False)
        for col in GKG_COLS:
            if col not in gkg_df.columns:
                gkg_df[col] = 0 if col == "V2Tone" else ""
        gkg_df = gkg_df[GKG_COLS].copy()

    print(f"[LOAD] events rows={len(events_df):,}")
    if gkg_df is None:
        print("[LOAD] gkg rows=0 (not provided)")
    else:
        print(f"[LOAD] gkg rows={len(gkg_df):,}")

    return events_df, gkg_df


def clean_data(
    events_df: pd.DataFrame,
    gkg_df: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """Type conversion, NaN filling, and invalid-row drops."""
    events = events_df.copy()

    events["SQLDATE"] = pd.to_datetime(events["SQLDATE"].astype(str), format="%Y%m%d", errors="coerce")
    events["NumMentions"] = pd.to_numeric(events["NumMentions"], errors="coerce")
    events["GoldsteinScale"] = pd.to_numeric(events["GoldsteinScale"], errors="coerce")

    events["NumMentions"] = events["NumMentions"].fillna(0)
    events["GoldsteinScale"] = events["GoldsteinScale"].fillna(0)

    events["Actor1CountryCode"] = events["Actor1CountryCode"].fillna("").astype(str)
    events["Actor2CountryCode"] = events["Actor2CountryCode"].fillna("").astype(str)
    events["EventCode"] = events["EventCode"].fillna("").astype(str)
    events["SOURCEURL"] = events["SOURCEURL"].fillna("").astype(str)

    events = events.dropna(subset=["SQLDATE"])  # invalid dates
    events = events[events["EventCode"].str.len() > 0]  # invalid event code
    events = events.reset_index(drop=True)

    cleaned_gkg: Optional[pd.DataFrame] = None
    if gkg_df is not None:
        cleaned_gkg = gkg_df.copy()
        cleaned_gkg["DocumentIdentifier"] = cleaned_gkg["DocumentIdentifier"].fillna("").astype(str)
        cleaned_gkg["V2Tone"] = pd.to_numeric(cleaned_gkg["V2Tone"], errors="coerce").fillna(0)
        cleaned_gkg = cleaned_gkg[cleaned_gkg["DocumentIdentifier"].str.len() > 0].reset_index(drop=True)

    print(f"[CLEAN] events rows={len(events):,}")
    if cleaned_gkg is None:
        print("[CLEAN] gkg rows=0")
    else:
        print(f"[CLEAN] gkg rows={len(cleaned_gkg):,}")
    print(events.head(3).to_string(index=False))

    return events, cleaned_gkg


def deduplicate(events_df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate by (date, actors, event code) before NLP."""
    deduped = (
        events_df.groupby(
            ["SQLDATE", "Actor1CountryCode", "Actor2CountryCode", "EventCode"],
            as_index=False,
        )
        .agg(
            {
                "NumMentions": "sum",
                "GoldsteinScale": "mean",
                "SOURCEURL": "first",
            }
        )
        .reset_index(drop=True)
    )

    print(f"[DEDUP] rows before={len(events_df):,}, after={len(deduped):,}")
    print(deduped.head(3).to_string(index=False))
    return deduped


def filter_data(events_df: pd.DataFrame) -> pd.DataFrame:
    """India + conflict events."""
    india_mask = (events_df["Actor1CountryCode"] == "IND") | (events_df["Actor2CountryCode"] == "IND")
    conflict_mask = events_df["EventCode"].astype(str).str.startswith(CONFLICT_PREFIXES, na=False)
    filtered = events_df[india_mask & conflict_mask].copy().reset_index(drop=True)

    print(f"[FILTER] rows={len(filtered):,}")
    print(filtered.head(3).to_string(index=False))
    return filtered


def prepare_text(headline: str, full_text: str) -> str:
    """Return headline + first 400 words of article text."""
    clean_headline = "" if pd.isna(headline) else str(headline)
    clean_text = "" if pd.isna(full_text) else str(full_text)
    first_400_words = " ".join(clean_text.split()[:400])
    combined = f"{clean_headline} {first_400_words}".strip()
    return combined


def _mock_get_article_content(source_url: str) -> Tuple[str, str]:
    """Mock article fetcher for prototype usage."""
    url = (source_url or "").lower()

    if any(keyword in url for keyword in ["attack", "missile", "border", "clash", "military"]):
        return (
            "Security tensions rise near border",
            "Border incidents intensified overnight, with multiple reports of shelling, military movement, "
            "and elevated risk perception among policymakers and markets.",
        )

    if any(keyword in url for keyword in ["trade", "talk", "cooperation", "agreement"]):
        return (
            "Diplomatic progress in regional talks",
            "Officials reported constructive dialogue and improved diplomatic tone, lowering immediate "
            "conflict intensity despite lingering uncertainty.",
        )

    return (
        "Geopolitical developments under review",
        "Analysts tracked mixed geopolitical signals including rhetoric, diplomatic moves, and "
        "localized security incidents.",
    )


def compute_nlp_scores(
    events_df: pd.DataFrame,
    batch_size: int = 16,
    nlp_sample_size: Optional[int] = None,
    use_nlp: bool = True,
    model_name: str = "nlptown/bert-base-multilingual-uncased-sentiment",
    url_score_cache: Optional[Dict[str, float]] = None,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Compute NLP risk score r_nlp in [0,1].

    Supported label formats:
    - Binary sentiment models (NEGATIVE/POSITIVE)
    - Star-rating models (e.g., "1 star" ... "5 stars")
    """
    out = events_df.copy()
    out["r_nlp"] = 0.0

    cache: Dict[str, float] = {} if url_score_cache is None else dict(url_score_cache)
    if not use_nlp or out.empty:
        print("[NLP] skipped")
        return out, cache

    if nlp_sample_size is not None and nlp_sample_size >= 0:
        indices = list(out.index[:nlp_sample_size])
    else:
        indices = list(out.index)

    texts = []
    text_indices = []
    text_urls = []

    for idx in indices:
        url = str(out.at[idx, "SOURCEURL"])
        if url in cache:
            out.at[idx, "r_nlp"] = float(cache[url])
            continue

        headline, full_text = _mock_get_article_content(url)
        prepared = prepare_text(headline=headline, full_text=full_text)
        if prepared:
            texts.append(prepared)
            text_indices.append(idx)
            text_urls.append(url)
        else:
            out.at[idx, "r_nlp"] = 0.0
            cache[url] = 0.0

    def _label_to_risk(label: str, score: float) -> float:
        normalized_label = str(label).strip().upper()
        confidence = float(np.clip(score, 0.0, 1.0))

        # Binary sentiment heads (e.g., SST-2, FinBERT variants)
        if normalized_label == "NEGATIVE":
            return confidence
        if normalized_label in {"POSITIVE", "NEUTRAL"}:
            return 0.0

        # Star-based sentiment heads (e.g., multilingual BERT sentiment)
        star_match = re.search(r"(\d)", normalized_label)
        if star_match:
            stars = int(star_match.group(1))
            if stars == 1:
                return 1.0 * confidence
            if stars == 2:
                return 0.5 * confidence
            return 0.0

        return 0.0

    if texts:
        try:
            from transformers import pipeline

            classifier = pipeline(
                "text-classification",
                model=model_name,
            )
            preds = classifier(texts, batch_size=batch_size, truncation=True, max_length=512)
        except Exception as exc:
            print(f"[NLP] model/inference failed, fallback to r_nlp=0. error={exc}")
            preds = [{"label": "POSITIVE", "score": 0.0} for _ in texts]

        for idx, url, pred in zip(text_indices, text_urls, preds):
            label = str(pred.get("label", "")).upper()
            score = float(pred.get("score", 0.0))
            r_nlp = float(np.clip(_label_to_risk(label=label, score=score), 0.0, 1.0))
            out.at[idx, "r_nlp"] = r_nlp
            cache[url] = r_nlp

    out["r_nlp"] = out["r_nlp"].fillna(0.0).clip(0.0, 1.0)
    assert ((out["r_nlp"] >= 0) & (out["r_nlp"] <= 1)).all(), "r_nlp must be in [0,1]"

    print(f"[NLP] model={model_name}")
    print(f"[NLP] scored rows={len(indices):,}, cache_size={len(cache):,}")
    print(out[["SQLDATE", "SOURCEURL", "r_nlp"]].head(3).to_string(index=False))
    return out, cache


def compute_risk_scores(
    events_df: pd.DataFrame,
    gkg_df: Optional[pd.DataFrame] = None,
    beta_gold: float = 0.5,
    beta_nlp: float = 0.3,
    beta_tone: float = 0.2,
) -> pd.DataFrame:
    """Compute r_gold, r_tone, r_final, r_enhanced."""
    out = events_df.copy()

    if gkg_df is not None and not gkg_df.empty:
        tone = gkg_df.groupby("DocumentIdentifier", as_index=False)["V2Tone"].mean()
        out = out.merge(tone, how="left", left_on="SOURCEURL", right_on="DocumentIdentifier")
    else:
        out["V2Tone"] = 0.0

    out["V2Tone"] = pd.to_numeric(out.get("V2Tone", 0), errors="coerce").fillna(0.0)
    out["GoldsteinScale"] = pd.to_numeric(out["GoldsteinScale"], errors="coerce").fillna(0.0)

    out["r_gold"] = (np.maximum(0.0, -out["GoldsteinScale"]) / 10.0).clip(0.0, 1.0)
    out["r_tone"] = (np.maximum(0.0, -out["V2Tone"]) / 100.0).clip(0.0, 1.0)
    out["r_nlp"] = pd.to_numeric(out.get("r_nlp", 0.0), errors="coerce").fillna(0.0).clip(0.0, 1.0)

    out["r_final"] = beta_gold * out["r_gold"] + beta_nlp * out["r_nlp"] + beta_tone * out["r_tone"]
    out["r_final"] = out["r_final"].clip(0.0, 1.0)
    out["r_enhanced"] = out["r_final"] ** 1.2

    assert ((out["r_gold"] >= 0) & (out["r_gold"] <= 1)).all(), "r_gold must be in [0,1]"
    assert ((out["r_tone"] >= 0) & (out["r_tone"] <= 1)).all(), "r_tone must be in [0,1]"
    assert ((out["r_nlp"] >= 0) & (out["r_nlp"] <= 1)).all(), "r_nlp must be in [0,1]"
    assert ((out["r_final"] >= 0) & (out["r_final"] <= 1)).all(), "r_final must be in [0,1]"

    print("[RISK] computed r_gold/r_nlp/r_tone/r_final")
    print(out[["SQLDATE", "r_gold", "r_nlp", "r_tone", "r_final"]].head(3).to_string(index=False))
    return out


def compute_event_weight(events_df: pd.DataFrame, alpha: float = 0.4) -> pd.DataFrame:
    """EventWeight = NumMentions * (1 + alpha * r_enhanced) * log(1 + NumMentions)."""
    out = events_df.copy()
    out["NumMentions"] = pd.to_numeric(out["NumMentions"], errors="coerce").fillna(0.0)

    out["EventWeight"] = (
        out["NumMentions"]
        * (1.0 + alpha * out["r_enhanced"])
        * np.log(1.0 + out["NumMentions"].clip(lower=0.0))
    )

    print("[WEIGHT] computed EventWeight")
    print(out[["SQLDATE", "NumMentions", "r_enhanced", "EventWeight"]].head(3).to_string(index=False))
    return out


def compute_gpr(
    all_events_dedup_df: pd.DataFrame,
    weighted_india_conflict_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Compute daily and monthly GPR with normalization."""
    denominator = (
        all_events_dedup_df.groupby("SQLDATE", as_index=False)["NumMentions"]
        .sum()
        .rename(columns={"NumMentions": "TotalMentions_t"})
    )

    numerator = (
        weighted_india_conflict_df.groupby("SQLDATE", as_index=False)["EventWeight"]
        .sum()
        .rename(columns={"EventWeight": "IndiaRisk_t"})
    )

    daily = denominator.merge(numerator, on="SQLDATE", how="left")
    daily["IndiaRisk_t"] = daily["IndiaRisk_t"].fillna(0.0)
    daily["GPR_t"] = np.where(daily["TotalMentions_t"] > 0, daily["IndiaRisk_t"] / daily["TotalMentions_t"], 0.0)
    daily = daily.sort_values("SQLDATE").reset_index(drop=True)

    monthly = (
        daily.assign(SQLMONTH=daily["SQLDATE"].dt.to_period("M").dt.to_timestamp())
        .groupby("SQLMONTH", as_index=False)["GPR_t"]
        .mean()
        .rename(columns={"SQLMONTH": "SQLDATE", "GPR_t": "MonthlyGPR"})
        .sort_values("SQLDATE")
        .reset_index(drop=True)
    )

    monthly_mean = float(monthly["MonthlyGPR"].mean()) if not monthly.empty else 0.0
    monthly["Index_t"] = 0.0 if monthly_mean == 0.0 else (monthly["MonthlyGPR"] / monthly_mean) * 100.0

    assert (daily["GPR_t"] >= 0).all(), "GPR_t must be >= 0"
    assert not daily.isna().any().any(), "daily output has NaN"
    assert not monthly.isna().any().any(), "monthly output has NaN"

    print(f"[GPR] daily rows={len(daily):,}, monthly rows={len(monthly):,}")
    print(daily.head(3).to_string(index=False))
    print(monthly.head(3).to_string(index=False))

    return daily, monthly


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="India GPR pipeline with DistilBERT sentiment")
    parser.add_argument("--events-path", default="gdelt_events_sample.csv", help="Path to GDELT Events CSV")
    parser.add_argument("--gkg-path", default=None, help="Optional path to GDELT GKG CSV")
    parser.add_argument("--output-dir", default="data", help="Directory for output files")
    parser.add_argument("--max-rows", type=int, default=None, help="Optional row limit for quick tests")
    parser.add_argument("--disable-nlp", action="store_true", help="Disable NLP scoring")
    parser.add_argument(
        "--nlp-sample-size",
        type=int,
        default=200,
        help="Run NLP on first N filtered rows only (set -1 for all rows)",
    )
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size for HuggingFace inference")
    parser.add_argument(
        "--model-name",
        default="nlptown/bert-base-multilingual-uncased-sentiment",
        help="HuggingFace model for NLP risk scoring",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    events_raw, gkg_raw = load_data(
        events_path=args.events_path,
        gkg_path=args.gkg_path,
        max_rows=args.max_rows,
    )
    events_clean, gkg_clean = clean_data(events_raw, gkg_raw)

    events_dedup = deduplicate(events_clean)  # critical: before NLP
    filtered = filter_data(events_dedup)

    use_nlp = not args.disable_nlp
    nlp_sample_size = None if args.nlp_sample_size is not None and args.nlp_sample_size < 0 else args.nlp_sample_size

    filtered_scored, _cache = compute_nlp_scores(
        filtered,
        batch_size=args.batch_size,
        nlp_sample_size=nlp_sample_size,
        use_nlp=use_nlp,
        model_name=args.model_name,
        url_score_cache={},
    )

    risk_scored = compute_risk_scores(filtered_scored, gkg_clean)
    weighted = compute_event_weight(risk_scored, alpha=0.4)

    daily_gpr, monthly_index = compute_gpr(
        all_events_dedup_df=events_dedup,
        weighted_india_conflict_df=weighted,
    )

    sample_cols = ["SQLDATE", "NumMentions", "r_gold", "r_nlp", "r_tone", "r_final", "EventWeight"]
    print("\n[OUTPUT] Sample event rows:")
    print(weighted[sample_cols].head(10).to_string(index=False))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    daily_path = output_dir / "daily_india_gpr_final.csv"
    monthly_path = output_dir / "monthly_india_gpr_index_final.csv"

    daily_gpr.to_csv(daily_path, index=False)
    monthly_index.to_csv(monthly_path, index=False)

    print(f"\n[SAVE] {daily_path}")
    print(f"[SAVE] {monthly_path}")


if __name__ == "__main__":
    main()
