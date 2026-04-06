"""Prototype GPR pipeline (Events + mandatory GKG + DistilBERT).

Implements the full requested flow:
- load_data()
- clean_data()
- deduplicate()
- filter_data()
- prepare_text()
- compute_nlp_scores()
- compute_risk_scores()
- compute_event_weight()
- compute_gpr()

Outputs:
- daily_<scope>_gpr_final.csv
- monthly_<scope>_gpr_index_final.csv
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
EVENT_CORE_COLS = [
    "SQLDATE",
    "Actor1CountryCode",
    "Actor2CountryCode",
    "EventCode",
    "NumMentions",
    "GoldsteinScale",
]
GKG_COLS = ["DocumentIdentifier", "V2Tone", "processed_text"]
CONFLICT_PREFIXES = ("13", "17", "19")

NLP_LABELS = [
    "geopolitical risk",
    "military conflict",
    "diplomacy",
    "sanctions",
    "terrorism",
    "protests",
]
TOPIC_LABELS = ["military conflict", "diplomacy", "sanctions", "terrorism", "protests"]
TOPIC_WEIGHTS = {
    "military conflict": 1.0,
    "terrorism": 0.9,
    "sanctions": 0.7,
    "protests": 0.6,
    "diplomacy": 0.4,
}
TOPIC_SCORE_COLS = {label: f"topic_score_{label.replace(' ', '_')}" for label in TOPIC_LABELS}
NLP_NOISE_CLASS_THRESHOLD = 0.4

# For official GDELT daily events exports (.export.CSV, tab-separated, no header)
OFFICIAL_GDELT_EVENTS_COLS = [
    "GLOBALEVENTID", "SQLDATE", "MonthYear", "Year", "FractionDate",
    "Actor1Code", "Actor1Name", "Actor1CountryCode", "Actor1KnownGroupCode",
    "Actor1EthnicCode", "Actor1Religion1Code", "Actor1Religion2Code",
    "Actor1Type1Code", "Actor1Type2Code", "Actor1Type3Code",
    "Actor2Code", "Actor2Name", "Actor2CountryCode", "Actor2KnownGroupCode",
    "Actor2EthnicCode", "Actor2Religion1Code", "Actor2Religion2Code",
    "Actor2Type1Code", "Actor2Type2Code", "Actor2Type3Code", "IsRootEvent",
    "EventCode", "EventBaseCode", "EventRootCode", "QuadClass",
    "GoldsteinScale", "NumMentions", "NumSources", "NumArticles", "AvgTone",
    "Actor1Geo_Type", "Actor1Geo_FullName", "Actor1Geo_CountryCode",
    "Actor1Geo_ADM1Code", "Actor1Geo_Lat", "Actor1Geo_Long", "Actor1Geo_FeatureID",
    "Actor2Geo_Type", "Actor2Geo_FullName", "Actor2Geo_CountryCode",
    "Actor2Geo_ADM1Code", "Actor2Geo_Lat", "Actor2Geo_Long", "Actor2Geo_FeatureID",
    "ActionGeo_Type", "ActionGeo_FullName", "ActionGeo_CountryCode",
    "ActionGeo_ADM1Code", "ActionGeo_Lat", "ActionGeo_Long", "ActionGeo_FeatureID",
    "DATEADDED", "SOURCEURL",
]


def _parse_bound_date(value: Optional[str]) -> Optional[pd.Timestamp]:
    if value is None:
        return None
    return pd.to_datetime(value, format="%Y-%m-%d", errors="coerce")


def _extract_yyyymmdd_from_name(path: Path) -> Optional[pd.Timestamp]:
    name = path.name

    # Events daily export: YYYYMMDD.export.CSV
    m = re.match(r"^(\d{8})\.export\.csv(?:\.zip)?$", name, flags=re.IGNORECASE)
    if m:
        return pd.to_datetime(m.group(1), format="%Y%m%d", errors="coerce")

    # Processed GKG: gkg_processed_YYYYMMDD.csv
    m = re.match(r"^gkg_processed_(\d{8})\.csv$", name, flags=re.IGNORECASE)
    if m:
        return pd.to_datetime(m.group(1), format="%Y%m%d", errors="coerce")

    # Fallback: any 8-digit token in filename
    m = re.search(r"(\d{8})", name)
    if m:
        return pd.to_datetime(m.group(1), format="%Y%m%d", errors="coerce")

    return None


def _iter_csv_files(
    input_path: str,
    max_files: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Path]:
    p = Path(input_path)
    if p.is_file():
        return [p]
    if not p.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")

    files = sorted(list(p.glob("*.csv")) + list(p.glob("*.CSV")))
    if not files:
        raise FileNotFoundError(f"No CSV files found under: {input_path}")

    # De-duplicate for case-insensitive filesystems (Windows) where
    # *.csv and *.CSV can match the same files twice.
    unique: Dict[str, Path] = {}
    for f in files:
        unique[str(f.resolve()).lower()] = f
    files = sorted(unique.values(), key=lambda x: x.name)

    start_ts = _parse_bound_date(start_date)
    end_ts = _parse_bound_date(end_date)
    if (start_ts is not None and pd.isna(start_ts)) or (end_ts is not None and pd.isna(end_ts)):
        raise ValueError("start_date/end_date must be YYYY-MM-DD when provided")

    if start_ts is not None or end_ts is not None:
        filtered_files: List[Path] = []
        for f in files:
            file_ts = _extract_yyyymmdd_from_name(f)
            if file_ts is None or pd.isna(file_ts):
                # If range filter is requested, only keep date-stamped files.
                continue
            if start_ts is not None and file_ts < start_ts:
                continue
            if end_ts is not None and file_ts > end_ts:
                continue
            filtered_files.append(f)

        files = filtered_files

        if not files:
            raise FileNotFoundError(
                f"No date-matching CSV files under: {input_path} for range {start_date}..{end_date}"
            )

    if max_files is not None:
        files = files[:max_files]
    return files


def _read_single_events_file(path: Path, max_rows: Optional[int] = None) -> pd.DataFrame:
    # 1) Regular CSV with header
    try:
        df = pd.read_csv(path, nrows=max_rows, low_memory=False)
        if all(c in df.columns for c in EVENT_CORE_COLS):
            if "SOURCEURL" not in df.columns:
                df["SOURCEURL"] = ""
            return df[EVENT_COLS].copy()
    except Exception:
        pass

    # 2) Fallback for official GDELT events exports
    df = pd.read_csv(
        path,
        sep="\t",
        header=None,
        names=OFFICIAL_GDELT_EVENTS_COLS,
        usecols=EVENT_COLS,
        nrows=max_rows,
        low_memory=False,
    )

    m = re.match(r"^(\d{8})\.export\.csv$", path.name, flags=re.IGNORECASE)
    if m:
        df["SQLDATE"] = m.group(1)

    return df


def _read_single_gkg_file(path: Path, max_rows: Optional[int] = None) -> pd.DataFrame:
    # 1) Processed GKG CSV/header case
    try:
        df = pd.read_csv(path, nrows=max_rows, low_memory=False)
        if all(c in df.columns for c in ["DocumentIdentifier", "V2Tone"]):
            if "processed_text" not in df.columns:
                df["processed_text"] = ""
            return df[GKG_COLS].copy()
    except Exception:
        pass

    # 2) Raw GKG fallback (tab-separated, no header)
    # GKG fields: 4=DocumentIdentifier, 15=V2Tone
    out = pd.read_csv(
        path,
        sep="\t",
        header=None,
        usecols=[4, 15],
        names=["DocumentIdentifier", "V2Tone"],
        nrows=max_rows,
        low_memory=False,
        engine="python",
        on_bad_lines="skip",
    )
    out["processed_text"] = ""
    return out[GKG_COLS]


def load_data(
    events_path: str,
    gkg_path: str,
    max_rows: Optional[int] = None,
    max_event_files: Optional[int] = None,
    max_gkg_files: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load events data and mandatory GKG data."""
    event_files = _iter_csv_files(
        events_path,
        max_files=max_event_files,
        start_date=start_date,
        end_date=end_date,
    )
    event_frames: List[pd.DataFrame] = []

    for i, file_path in enumerate(event_files, start=1):
        try:
            event_frames.append(_read_single_events_file(file_path, max_rows=max_rows))
        except Exception as exc:
            print(f"[WARN] events read failed for {file_path.name}: {exc}")
        if i % 100 == 0 or i == len(event_files):
            print(f"[LOAD] events progress: {i}/{len(event_files)}")

    if not event_frames:
        raise RuntimeError("No readable Events CSV files were found.")

    events_df = pd.concat(event_frames, ignore_index=True)

    gkg_files = _iter_csv_files(
        gkg_path,
        max_files=max_gkg_files,
        start_date=start_date,
        end_date=end_date,
    )
    gkg_frames: List[pd.DataFrame] = []

    for i, file_path in enumerate(gkg_files, start=1):
        try:
            gkg_frames.append(_read_single_gkg_file(file_path, max_rows=max_rows))
        except Exception as exc:
            print(f"[WARN] gkg read failed for {file_path.name}: {exc}")
        if i % 200 == 0 or i == len(gkg_files):
            print(f"[LOAD] gkg progress: {i}/{len(gkg_files)}")

    if not gkg_frames:
        raise RuntimeError("No readable GKG CSV files were found.")

    gkg_df = pd.concat(gkg_frames, ignore_index=True)

    print(f"[LOAD] events rows={len(events_df):,}")
    print(f"[LOAD] gkg rows={len(gkg_df):,}")

    return events_df, gkg_df


def clean_data(
    events_df: pd.DataFrame,
    gkg_df: pd.DataFrame,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Clean events + mandatory gkg data."""
    events = events_df.copy()

    events["SQLDATE"] = pd.to_datetime(events["SQLDATE"].astype(str), format="%Y%m%d", errors="coerce")
    events["NumMentions"] = pd.to_numeric(events["NumMentions"], errors="coerce").fillna(0.0)
    events["GoldsteinScale"] = pd.to_numeric(events["GoldsteinScale"], errors="coerce").fillna(0.0)

    events["Actor1CountryCode"] = events["Actor1CountryCode"].fillna("").astype(str)
    events["Actor2CountryCode"] = events["Actor2CountryCode"].fillna("").astype(str)
    events["EventCode"] = events["EventCode"].fillna("").astype(str)
    events["SOURCEURL"] = events["SOURCEURL"].fillna("").astype(str)

    events = events.dropna(subset=["SQLDATE"]).copy()
    events = events[events["EventCode"].str.len() > 0].reset_index(drop=True)

    start_ts = _parse_bound_date(start_date)
    end_ts = _parse_bound_date(end_date)
    if start_ts is not None:
        events = events[events["SQLDATE"] >= start_ts]
    if end_ts is not None:
        events = events[events["SQLDATE"] <= end_ts]
    events = events.reset_index(drop=True)

    cleaned_gkg = gkg_df.copy()
    cleaned_gkg["DocumentIdentifier"] = cleaned_gkg["DocumentIdentifier"].fillna("").astype(str)
    cleaned_gkg["processed_text"] = cleaned_gkg.get("processed_text", "").fillna("").astype(str)

    # Some raw GKG V2Tone values can appear as comma-separated values.
    tone_str = cleaned_gkg["V2Tone"].fillna("0").astype(str)
    tone_first = tone_str.str.split(",").str[0]
    cleaned_gkg["V2Tone"] = pd.to_numeric(tone_first, errors="coerce").fillna(0.0)

    cleaned_gkg = cleaned_gkg[cleaned_gkg["DocumentIdentifier"].str.len() > 0].reset_index(drop=True)
    if cleaned_gkg.empty:
        raise RuntimeError("GKG data is mandatory but no valid rows remained after cleaning.")

    print(f"[CLEAN] events rows={len(events):,}")
    print(f"[CLEAN] gkg rows={len(cleaned_gkg):,}")
    print(events.head(3).to_string(index=False))

    return events, cleaned_gkg


def deduplicate(events_df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate BEFORE NLP (critical)."""
    out = (
        events_df.groupby(
            ["SQLDATE", "Actor1CountryCode", "Actor2CountryCode", "EventCode"],
            as_index=False,
        )
        .agg({
            "NumMentions": "sum",
            "GoldsteinScale": "mean",
            "SOURCEURL": "first",
        })
        .reset_index(drop=True)
    )

    print(f"[DEDUP] rows before={len(events_df):,}, after={len(out):,}")
    print(out.head(3).to_string(index=False))
    return out


def filter_data(events_df: pd.DataFrame, scope: str = "india") -> pd.DataFrame:
    """Filter events by scope + conflict.

    - india: India + conflict
    - global: conflict only
    """
    conflict_mask = events_df["EventCode"].astype(str).str.startswith(CONFLICT_PREFIXES, na=False)

    if scope == "global":
        out = events_df[conflict_mask].copy().reset_index(drop=True)
    else:
        india_mask = (events_df["Actor1CountryCode"] == "IND") | (events_df["Actor2CountryCode"] == "IND")
        out = events_df[india_mask & conflict_mask].copy().reset_index(drop=True)

    print(f"[FILTER] scope={scope}, rows={len(out):,}")
    print(out.head(3).to_string(index=False))
    return out


def prepare_text(headline: str, full_text: str) -> str:
    """Return headline + first 400 words."""
    h = "" if pd.isna(headline) else str(headline)
    t = "" if pd.isna(full_text) else str(full_text)
    body = " ".join(t.split()[:400])
    return f"{h} {body}".strip()


def _mock_get_article_content(source_url: str) -> Tuple[str, str]:
    """Mock article extraction (no real scraping)."""
    u = (source_url or "").lower()

    if any(k in u for k in ["attack", "missile", "border", "clash", "military"]):
        return (
            "Security tensions rise",
            "Military and cross-border tensions escalated with reports of clashes and force mobilization.",
        )
    if any(k in u for k in ["sanction", "threat", "warning", "coercion"]):
        return (
            "Threats and sanctions reported",
            "Officials issued warnings and sanctions, increasing geopolitical downside risks.",
        )
    if any(k in u for k in ["trade", "deal", "talk", "cooperation"]):
        return (
            "Diplomatic talks continue",
            "Dialogue and cooperation signals improved the short-term political tone.",
        )

    return (
        "Geopolitical update",
        "Analysts monitored mixed geopolitical developments including rhetoric and security events.",
    )


def extract_scores(result: Dict[str, object]) -> Tuple[float, Dict[str, float]]:
    """Extract r_class and per-topic scores from BART zero-shot output."""
    labels = [str(x).strip().lower() for x in result.get("labels", [])]
    scores = [float(x) for x in result.get("scores", [])]
    score_map = {k: float(np.clip(v, 0.0, 1.0)) for k, v in zip(labels, scores)}

    r_class = float(np.clip(score_map.get("geopolitical risk", 0.0), 0.0, 1.0))
    topic_scores = {
        topic: float(np.clip(score_map.get(topic, 0.0), 0.0, 1.0))
        for topic in TOPIC_LABELS
    }
    return r_class, topic_scores


def compute_multitopic_score(topic_scores: Dict[str, float]) -> float:
    """Compute weighted multi-topic blended score and keep it in [0,1]."""
    blended = sum(float(TOPIC_WEIGHTS[label]) * float(topic_scores.get(label, 0.0)) for label in TOPIC_LABELS)
    return float(np.clip(blended, 0.0, 1.0))


def compute_nlp_scores(
    events_df: pd.DataFrame,
    gkg_df: Optional[pd.DataFrame] = None,
    use_nlp: bool = True,
    nlp_sample_size: Optional[int] = 200,
    batch_size: int = 16,
    model_name: str = "facebook/bart-large-mnli",
    device: str = "auto",
    url_score_cache: Optional[Dict[str, Dict[str, object]]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Dict[str, object]]]:
    """Compute NLP risk with single-model BART and multi-topic blending."""
    out = events_df.copy()
    out["r_class"] = 0.0
    out["r_topic"] = 0.0
    out["nlp_text_preview"] = ""
    out["r_nlp"] = 0.0
    for col in TOPIC_SCORE_COLS.values():
        out[col] = 0.0

    cache: Dict[str, Dict[str, object]] = {} if url_score_cache is None else dict(url_score_cache)
    gkg_text_map: Dict[str, str] = {}

    if gkg_df is not None and not gkg_df.empty and "DocumentIdentifier" in gkg_df.columns:
        gkg_text_df = gkg_df[["DocumentIdentifier", "processed_text"]].copy()
        gkg_text_df["DocumentIdentifier"] = gkg_text_df["DocumentIdentifier"].fillna("").astype(str)
        gkg_text_df["processed_text"] = gkg_text_df["processed_text"].fillna("").astype(str)
        gkg_text_df = gkg_text_df[gkg_text_df["DocumentIdentifier"].str.len() > 0]
        if not gkg_text_df.empty:
            # Prefer longer processed text for duplicated URLs.
            gkg_text_df = gkg_text_df.assign(_len=gkg_text_df["processed_text"].str.len())
            gkg_text_df = gkg_text_df.sort_values("_len", ascending=False)
            gkg_text_map = (
                gkg_text_df.drop_duplicates(subset=["DocumentIdentifier"])
                .set_index("DocumentIdentifier")["processed_text"]
                .to_dict()
            )

    if not use_nlp or out.empty:
        print("[NLP] skipped")
        return out, cache

    if nlp_sample_size is None or nlp_sample_size < 0:
        target_indices = list(out.index)
    else:
        target_indices = list(out.index[:nlp_sample_size])

    total_targets = len(target_indices)
    progress_every = max(500, min(25_000, max(1, total_targets // 10)))
    inference_chunk_size = 4_096
    processed_count = 0
    gkg_text_hits = 0
    missing_text_count = 0

    def _log_progress(force: bool = False) -> None:
        nonlocal processed_count
        if not force and processed_count % progress_every != 0:
            return
        elapsed = max(1e-9, time.time() - started_at)
        rate = processed_count / elapsed
        remaining = max(0, total_targets - processed_count)
        eta_seconds = remaining / max(rate, 1e-9)
        print(
            f"[NLP] progress={processed_count:,}/{total_targets:,} "
            f"rate={rate:,.1f} rows/s eta={eta_seconds/3600.0:.2f}h"
        )

    def _score_texts(
        texts_batch: List[str],
        idx_batch: List[int],
        key_batch: List[str],
        classifier,
    ) -> int:
        if not texts_batch:
            return 0

        preds = classifier(
            texts_batch,
            candidate_labels=NLP_LABELS,
            multi_label=False,
            batch_size=batch_size,
            truncation=True,
            max_length=512,
        )

        if isinstance(preds, dict):
            preds = [preds]

        if len(preds) < len(texts_batch):
            preds = list(preds) + [{} for _ in range(len(texts_batch) - len(preds))]

        for idx, key, text, pred in zip(
            idx_batch,
            key_batch,
            texts_batch,
            preds,
        ):
            r_class, topic_scores = extract_scores(pred)
            r_topic = compute_multitopic_score(topic_scores)
            r_nlp = float(np.clip(r_class * r_topic, 0.0, 1.0))
            if r_class < NLP_NOISE_CLASS_THRESHOLD:
                r_nlp = 0.0

            out.at[idx, "r_class"] = float(r_class)
            out.at[idx, "r_topic"] = float(r_topic)
            out.at[idx, "nlp_text_preview"] = text[:180]
            out.at[idx, "r_nlp"] = float(r_nlp)
            for label, col in TOPIC_SCORE_COLS.items():
                out.at[idx, col] = float(topic_scores.get(label, 0.0))

            cache[key] = {
                "r_class": float(r_class),
                "topic_scores": {label: float(topic_scores.get(label, 0.0)) for label in TOPIC_LABELS},
                "r_topic": float(r_topic),
                "nlp_text_preview": text[:180],
                "r_nlp": float(r_nlp),
            }

        return len(texts_batch)

    classifier = None
    resolved_device = -1
    started_at = time.time()
    try:
        if device not in {"auto", "cpu", "cuda"}:
            raise ValueError("device must be one of: auto, cpu, cuda")

        if device == "cpu":
            resolved_device = -1
        else:
            try:
                import torch

                has_cuda = bool(torch.cuda.is_available())
            except Exception:
                has_cuda = False

            if device == "cuda" and not has_cuda:
                raise RuntimeError("CUDA was requested (--device cuda) but no CUDA device is available.")

            resolved_device = 0 if has_cuda else -1

        from transformers import pipeline

        classifier = pipeline(
            "zero-shot-classification",
            model=model_name,
            device=resolved_device,
        )
    except Exception as exc:
        print(f"[NLP] model load failed, fallback to r_nlp=0. error={exc}")
        classifier = None

    pending_texts: List[str] = []
    pending_idx: List[int] = []
    pending_keys: List[str] = []

    for idx in target_indices:
        url = str(out.at[idx, "SOURCEURL"])
        gkg_text = str(gkg_text_map.get(url, ""))
        if gkg_text.strip():
            text = prepare_text(headline="", full_text=gkg_text)
            gkg_text_hits += 1
        else:
            text = ""
            missing_text_count += 1

        cache_key = text
        if cache_key in cache:
            cached = cache[cache_key]
            out.at[idx, "r_class"] = float(cached.get("r_class", 0.0))
            out.at[idx, "r_topic"] = float(cached.get("r_topic", 0.0))
            out.at[idx, "nlp_text_preview"] = str(cached.get("nlp_text_preview", ""))
            out.at[idx, "r_nlp"] = float(cached.get("r_nlp", 0.0))
            cached_topic_scores = cached.get("topic_scores", {})
            for label, col in TOPIC_SCORE_COLS.items():
                out.at[idx, col] = float(cached_topic_scores.get(label, 0.0))
            processed_count += 1
            _log_progress()
            continue

        if not text:
            out.at[idx, "r_class"] = 0.0
            out.at[idx, "r_topic"] = 0.0
            out.at[idx, "nlp_text_preview"] = ""
            out.at[idx, "r_nlp"] = 0.0
            for col in TOPIC_SCORE_COLS.values():
                out.at[idx, col] = 0.0
            cache[cache_key] = {
                "r_class": 0.0,
                "topic_scores": {label: 0.0 for label in TOPIC_LABELS},
                "r_topic": 0.0,
                "nlp_text_preview": "",
                "r_nlp": 0.0,
            }
            processed_count += 1
            _log_progress()
            continue

        pending_texts.append(text)
        pending_idx.append(idx)
        pending_keys.append(cache_key)

        if len(pending_texts) >= inference_chunk_size:
            processed_count += _score_texts(
                pending_texts,
                pending_idx,
                pending_keys,
                classifier,
            )
            pending_texts = []
            pending_idx = []
            pending_keys = []
            _log_progress()

    if pending_texts:
        processed_count += _score_texts(
            pending_texts,
            pending_idx,
            pending_keys,
            classifier,
        )
        _log_progress(force=True)

    if processed_count < total_targets:
        # Defensive: in case of unexpected path, keep counters consistent for ETA logs.
        processed_count = total_targets
    _log_progress(force=True)

    out["r_class"] = pd.to_numeric(out["r_class"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    out["r_topic"] = pd.to_numeric(out["r_topic"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    for col in TOPIC_SCORE_COLS.values():
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    out["r_nlp"] = out["r_nlp"].fillna(0.0).clip(0.0, 1.0)

    assert ((out["r_class"] >= 0.0) & (out["r_class"] <= 1.0)).all(), "r_class must be in [0,1]"
    assert ((out["r_topic"] >= 0.0) & (out["r_topic"] <= 1.0)).all(), "r_topic must be in [0,1]"
    assert ((out["r_nlp"] >= 0.0) & (out["r_nlp"] <= 1.0)).all(), "r_nlp must be in [0,1]"

    print(f"[NLP] model={model_name}")
    print(f"[NLP] labels={NLP_LABELS}")
    print(f"[NLP] device={'cuda:0' if resolved_device >= 0 else 'cpu'}")
    print(f"[NLP] scored rows={total_targets:,}, cache_size={len(cache):,}")
    print(f"[NLP] gkg_text_hits={gkg_text_hits:,}")
    print(f"[NLP] missing_processed_text_rows={missing_text_count:,}")
    print(
        out[
            [
                "SQLDATE",
                "nlp_text_preview",
                "r_class",
                *TOPIC_SCORE_COLS.values(),
                "r_topic",
                "r_nlp",
            ]
        ].head(3).to_string(index=False)
    )
    return out, cache


def compute_risk_scores(
    events_df: pd.DataFrame,
    gkg_df: pd.DataFrame,
    beta_gold: float = 0.4,
    beta_nlp: float = 0.4,
    beta_tone: float = 0.2,
) -> pd.DataFrame:
    """Compute r_gold, r_tone, r_final, r_enhanced."""
    out = events_df.copy()

    tone_map = gkg_df.groupby("DocumentIdentifier", as_index=False)["V2Tone"].mean()
    out = out.merge(tone_map, how="left", left_on="SOURCEURL", right_on="DocumentIdentifier")

    out["GoldsteinScale"] = pd.to_numeric(out["GoldsteinScale"], errors="coerce").fillna(0.0)
    out["V2Tone"] = pd.to_numeric(out.get("V2Tone", 0.0), errors="coerce").fillna(0.0)
    out["r_nlp"] = pd.to_numeric(out.get("r_nlp", 0.0), errors="coerce").fillna(0.0).clip(0.0, 1.0)

    # Requested formulas
    out["r_gold"] = (np.maximum(0.0, -out["GoldsteinScale"]) / 10.0).clip(0.0, 1.0)
    out["r_tone"] = (np.maximum(0.0, -out["V2Tone"]) / 100.0).clip(0.0, 1.0)

    out["r_final"] = beta_gold * out["r_gold"] + beta_nlp * out["r_nlp"] + beta_tone * out["r_tone"]
    out["r_final"] = out["r_final"].clip(0.0, 1.0)
    out["r_enhanced"] = out["r_final"] ** 1.2

    assert ((out["r_gold"] >= 0) & (out["r_gold"] <= 1)).all(), "r_gold out of [0,1]"
    assert ((out["r_tone"] >= 0) & (out["r_tone"] <= 1)).all(), "r_tone out of [0,1]"
    assert ((out["r_nlp"] >= 0) & (out["r_nlp"] <= 1)).all(), "r_nlp out of [0,1]"
    assert ((out["r_final"] >= 0) & (out["r_final"] <= 1)).all(), "r_final out of [0,1]"

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
    weighted_filtered_df: pd.DataFrame,
    scope: str = "india",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Compute daily GPR, monthly GPR, and normalized index."""
    denominator = (
        all_events_dedup_df.groupby("SQLDATE", as_index=False)["NumMentions"]
        .sum()
        .rename(columns={"NumMentions": "TotalMentions_t"})
    )

    numerator = (
        weighted_filtered_df.groupby("SQLDATE", as_index=False)["EventWeight"]
        .sum()
        .rename(columns={"EventWeight": "Risk_t"})
    )

    daily = denominator.merge(numerator, how="left", on="SQLDATE")
    daily["Risk_t"] = daily["Risk_t"].fillna(0.0)
    daily["GPR_t"] = np.where(
        daily["TotalMentions_t"] > 0,
        daily["Risk_t"] / daily["TotalMentions_t"],
        0.0,
    )
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
    monthly["Index_t"] = 0.0 if monthly_mean == 0 else (monthly["MonthlyGPR"] / monthly_mean) * 100.0

    assert (daily["GPR_t"] >= 0).all(), "GPR_t must be >= 0"
    assert not daily[["SQLDATE", "TotalMentions_t", "Risk_t", "GPR_t"]].isna().any().any(), "NaNs in daily output"
    assert not monthly[["SQLDATE", "MonthlyGPR", "Index_t"]].isna().any().any(), "NaNs in monthly output"

    print(f"[GPR] scope={scope}, daily rows={len(daily):,}, monthly rows={len(monthly):,}")
    print(daily.head(3).to_string(index=False))
    print(monthly.head(3).to_string(index=False))

    return daily, monthly


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prototype GPR pipeline with single-model BART NLP + mandatory GKG tone")
    parser.add_argument("--events-path", default="gdelt_events_sample.csv", help="Events CSV file or folder")
    parser.add_argument("--gkg-path", required=True, help="GKG CSV file or folder (mandatory)")
    parser.add_argument("--output-dir", default="data", help="Output directory")
    parser.add_argument("--max-rows", type=int, default=None, help="Optional row cap per input file")
    parser.add_argument("--max-event-files", type=int, default=None, help="Optional cap on number of events files")
    parser.add_argument("--max-gkg-files", type=int, default=None, help="Optional cap on number of gkg files")
    parser.add_argument("--scope", choices=["india", "global"], default="global", help="Numerator scope")
    parser.add_argument("--start-date", default=None, help="Optional inclusive date bound YYYY-MM-DD")
    parser.add_argument("--end-date", default=None, help="Optional inclusive date bound YYYY-MM-DD")

    parser.add_argument("--disable-nlp", action="store_true", help="Disable NLP (r_nlp=0)")
    parser.add_argument("--nlp-sample-size", type=int, default=200, help="NLP on first N filtered rows; -1 for all")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size for NLP inference")
    parser.add_argument(
        "--model-name",
        default="facebook/bart-large-mnli",
        help="HuggingFace zero-shot model for risk + multi-topic scoring",
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto",
        help="NLP inference device: auto (prefer cuda), cpu, or cuda",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    events_raw, gkg_raw = load_data(
        events_path=args.events_path,
        gkg_path=args.gkg_path,
        max_rows=args.max_rows,
        max_event_files=args.max_event_files,
        max_gkg_files=args.max_gkg_files,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    events_clean, gkg_clean = clean_data(
        events_raw,
        gkg_raw,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    events_dedup = deduplicate(events_clean)  # CRITICAL: before NLP
    filtered = filter_data(events_dedup, scope=args.scope)

    use_nlp = not args.disable_nlp
    nlp_sample_size = None if args.nlp_sample_size is not None and args.nlp_sample_size < 0 else args.nlp_sample_size

    filtered_scored, _cache = compute_nlp_scores(
        filtered,
        gkg_df=gkg_clean,
        use_nlp=use_nlp,
        nlp_sample_size=nlp_sample_size,
        batch_size=args.batch_size,
        model_name=args.model_name,
        device=args.device,
        url_score_cache={},
    )

    risk_scored = compute_risk_scores(
        filtered_scored,
        gkg_df=gkg_clean,
        beta_gold=0.4,
        beta_nlp=0.4,
        beta_tone=0.2,
    )

    weighted = compute_event_weight(risk_scored, alpha=0.4)

    daily_gpr, monthly_index = compute_gpr(
        all_events_dedup_df=events_dedup,
        weighted_filtered_df=weighted,
        scope=args.scope,
    )

    sample_cols = [
        "SQLDATE",
        "nlp_text_preview",
        "r_class",
        *TOPIC_SCORE_COLS.values(),
        "r_topic",
        "r_nlp",
        "r_final",
        "EventWeight",
    ]
    print("\n[OUTPUT] sample rows:")
    print(weighted[sample_cols].head(10).to_string(index=False))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    daily_path = output_dir / f"daily_{args.scope}_gpr_final.csv"
    monthly_path = output_dir / f"monthly_{args.scope}_gpr_index_final.csv"

    daily_gpr.to_csv(daily_path, index=False)
    monthly_index.to_csv(monthly_path, index=False)

    print(f"\n[SAVE] {daily_path}")
    print(f"[SAVE] {monthly_path}")


if __name__ == "__main__":
    main()
