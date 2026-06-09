#!/usr/bin/env python3
"""Streaming GPR pipeline for GDELT Events + GKG + DistilBERT.

Implements the requested flow:
- Stream files one by one
- Clean, deduplicate, merge GKG
- DistilBERT zero-shot scoring
- Dynamic topic blending
- Goldstein, tone, combined risk
- Hybrid event inclusion
- Daily and monthly GPR outputs
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

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
GKG_COLS = ["DocumentIdentifier", "V2Tone", "processed_text"]

INCLUDE_EVENT_PREFIXES = ("13", "14", "17", "18", "19")
NLP_CLASS_LABEL = "geopolitical risk"
NLP_NOISE_CLASS_THRESHOLD = 0.15

# ── Caldara-style continuity parameters ──────────────────────────────────────
SMOOTHING_SPAN = 7                  # EWM smoothing span for daily GPR

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

INDIA_CODES = {"IND", "IN"}


def _parse_bound_date(value: Optional[str]) -> Optional[pd.Timestamp]:
    if value is None:
        return None
    return pd.to_datetime(value, format="%Y-%m-%d", errors="coerce")


def _extract_date_from_name(path: Path) -> Optional[pd.Timestamp]:
    name = path.name
    match = re.match(r"^(\d{8})\.export\.csv(?:\.zip)?$", name, flags=re.IGNORECASE)
    if match:
        return pd.to_datetime(match.group(1), format="%Y%m%d", errors="coerce")

    match = re.match(r"^gkg_processed_(\d{8})\.csv$", name, flags=re.IGNORECASE)
    if match:
        return pd.to_datetime(match.group(1), format="%Y%m%d", errors="coerce")

    match = re.search(r"(\d{8})", name)
    if match:
        return pd.to_datetime(match.group(1), format="%Y%m%d", errors="coerce")

    return None


def _collect_csv_files(input_path: str, start_date: Optional[str], end_date: Optional[str], max_files: Optional[int]) -> List[Path]:
    path = Path(input_path)
    if path.is_file():
        return [path]
    if not path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")

    files = sorted(list(path.glob("*.csv")) + list(path.glob("*.CSV")))
    unique: Dict[str, Path] = {}
    for file_path in files:
        unique[str(file_path.resolve()).lower()] = file_path
    files = sorted(unique.values(), key=lambda x: x.name)

    start_ts = _parse_bound_date(start_date)
    end_ts = _parse_bound_date(end_date)
    if (start_ts is not None and pd.isna(start_ts)) or (end_ts is not None and pd.isna(end_ts)):
        raise ValueError("start_date/end_date must be YYYY-MM-DD")

    if start_ts is not None or end_ts is not None:
        filtered: List[Path] = []
        for file_path in files:
            file_ts = _extract_date_from_name(file_path)
            if file_ts is None or pd.isna(file_ts):
                continue
            if start_ts is not None and file_ts < start_ts:
                continue
            if end_ts is not None and file_ts > end_ts:
                continue
            filtered.append(file_path)
        files = filtered
        if not files:
            raise FileNotFoundError(f"No date-matching CSV files under: {input_path}")

    if max_files is not None:
        files = files[:max_files]
    return files


def _build_file_map(input_path: str, start_date: Optional[str], end_date: Optional[str], max_files: Optional[int]) -> Dict[pd.Timestamp, Path]:
    file_map: Dict[pd.Timestamp, Path] = {}
    for file_path in _collect_csv_files(input_path, start_date, end_date, max_files):
        file_ts = _extract_date_from_name(file_path)
        if file_ts is None or pd.isna(file_ts):
            continue
        file_map[file_ts.normalize()] = file_path
    return dict(sorted(file_map.items(), key=lambda x: x[0]))


def _read_events_file(path: Path, max_rows: Optional[int] = None) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, nrows=max_rows, low_memory=False)
        if all(c in df.columns for c in ["SQLDATE", "Actor1CountryCode", "Actor2CountryCode", "EventCode", "NumMentions", "GoldsteinScale", "SOURCEURL"]):
            return df[EVENT_COLS].copy()
    except Exception:
        pass

    return pd.read_csv(
        path,
        sep="\t",
        header=None,
        names=OFFICIAL_GDELT_EVENTS_COLS,
        usecols=EVENT_COLS,
        nrows=max_rows,
        engine="python",
        on_bad_lines="skip",
    )


def _read_gkg_file(path: Path, max_rows: Optional[int] = None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame(columns=GKG_COLS)

    try:
        df = pd.read_csv(path, nrows=max_rows, low_memory=False)
        if all(c in df.columns for c in ["DocumentIdentifier", "V2Tone"]):
            if "processed_text" not in df.columns:
                df["processed_text"] = ""
            return df[GKG_COLS].copy()
    except Exception:
        pass

    try:
        df = pd.read_csv(
            path,
            sep="\t",
            header=None,
            usecols=[4, 15],
            names=["DocumentIdentifier", "V2Tone"],
            nrows=max_rows,
            engine="python",
            on_bad_lines="skip",
        )
        df["processed_text"] = ""
        return df[GKG_COLS].copy()
    except Exception:
        return pd.DataFrame(columns=GKG_COLS)


def _clean_events(events_df: pd.DataFrame, start_date: Optional[str], end_date: Optional[str]) -> pd.DataFrame:
    events = events_df.copy()
    for col in ["Actor1CountryCode", "Actor2CountryCode", "EventCode", "SOURCEURL"]:
        if col not in events.columns:
            events[col] = ""
    for col in ["NumMentions", "GoldsteinScale"]:
        if col not in events.columns:
            events[col] = 0.0

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

    return events.reset_index(drop=True)


def _clean_gkg(gkg_df: pd.DataFrame) -> pd.DataFrame:
    gkg = gkg_df.copy()
    if gkg.empty:
        return pd.DataFrame(columns=GKG_COLS)

    for col in ["DocumentIdentifier", "processed_text", "V2Tone"]:
        if col not in gkg.columns:
            gkg[col] = "" if col != "V2Tone" else 0.0

    gkg["DocumentIdentifier"] = gkg["DocumentIdentifier"].fillna("").astype(str)
    gkg["processed_text"] = gkg["processed_text"].fillna("").astype(str)
    tone_str = gkg["V2Tone"].fillna("0").astype(str)
    tone_first = tone_str.str.split(",").str[0]
    gkg["V2Tone"] = pd.to_numeric(tone_first, errors="coerce").fillna(0.0)
    gkg = gkg[gkg["DocumentIdentifier"].str.len() > 0].reset_index(drop=True)
    return gkg[GKG_COLS].copy()


def deduplicate(events_df: pd.DataFrame) -> pd.DataFrame:
    out = (
        events_df.groupby(["SQLDATE", "Actor1CountryCode", "Actor2CountryCode", "EventCode"], as_index=False)
        .agg({"NumMentions": "sum", "GoldsteinScale": "mean", "SOURCEURL": "first"})
        .reset_index(drop=True)
    )
    print(f"[DEDUP] rows before={len(events_df):,}, after={len(out):,}")
    print(out.head(3).to_string(index=False))
    return out


def merge_gkg(events_df: pd.DataFrame, gkg_df: pd.DataFrame) -> pd.DataFrame:
    out = events_df.copy()
    if gkg_df.empty:
        out["processed_text"] = ""
        out["V2Tone"] = 0.0
        return out

    gkg = gkg_df.copy()
    gkg["DocumentIdentifier"] = gkg["DocumentIdentifier"].fillna("").astype(str)
    gkg["processed_text"] = gkg["processed_text"].fillna("").astype(str)
    gkg["V2Tone"] = pd.to_numeric(gkg["V2Tone"], errors="coerce").fillna(0.0)
    gkg = gkg[gkg["DocumentIdentifier"].str.len() > 0]

    # Prefer the longest available processed text for duplicate URLs.
    gkg = gkg.assign(_len=gkg["processed_text"].str.len())
    gkg = gkg.sort_values(["DocumentIdentifier", "_len"], ascending=[True, False])
    gkg = gkg.drop_duplicates(subset=["DocumentIdentifier"], keep="first").drop(columns=["_len"])

    out = out.merge(
        gkg[["DocumentIdentifier", "processed_text", "V2Tone"]],
        how="left",
        left_on="SOURCEURL",
        right_on="DocumentIdentifier",
    )
    out["processed_text"] = out["processed_text"].fillna("").astype(str)
    out["V2Tone"] = pd.to_numeric(out.get("V2Tone", 0.0), errors="coerce").fillna(0.0)
    return out


def prepare_text(processed_text: str, sourceurl: str = "", event_code: str = "", actor1: str = "", actor2: str = "") -> str:
    text = "" if pd.isna(processed_text) else str(processed_text).strip()
    if not text:
        text = " ".join([str(sourceurl or ""), str(event_code or ""), str(actor1 or ""), str(actor2 or "")]).strip()
    words = text.split()
    return " ".join(words[:400])


def _label_scores(result: Dict[str, object]) -> Dict[str, float]:
    labels = [str(x).strip().lower() for x in result.get("labels", [])]
    scores = [float(x) for x in result.get("scores", [])]
    return {label: float(np.clip(score, 0.0, 1.0)) for label, score in zip(labels, scores)}


def _resolve_device(device: str) -> int:
    if device == "cpu":
        return -1
    if device not in {"auto", "cuda"}:
        raise ValueError("device must be one of: auto, cpu, cuda")

    try:
        import torch

        has_cuda = bool(torch.cuda.is_available())
    except Exception:
        has_cuda = False

    if device == "cuda" and not has_cuda:
        raise RuntimeError("CUDA requested but unavailable.")
    return 0 if has_cuda else -1


def _build_classifier(model_name: str, device: str):
    from transformers import pipeline

    return pipeline("zero-shot-classification", model=model_name, device=_resolve_device(device))


def compute_nlp_scores(
    events_df: pd.DataFrame,
    classifier,
    use_nlp: bool = True,
    nlp_sample_size: Optional[int] = None,
    batch_size: int = 16,
    url_score_cache: Optional[Dict[str, Dict[str, object]]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Dict[str, object]]]:
    out = events_df.copy()
    out["r_class"] = 0.0
    out["r_nlp"] = 0.0
    out["nlp_text_preview"] = ""

    cache: Dict[str, Dict[str, object]] = {} if url_score_cache is None else dict(url_score_cache)
    if not use_nlp or out.empty or classifier is None:
        print("[NLP] skipped")
        return out, cache

    if "nlp_text" not in out.columns:
        out["nlp_text"] = out.apply(
            lambda row: prepare_text(
                row.get("processed_text", ""),
                row.get("SOURCEURL", ""),
                row.get("EventCode", ""),
                row.get("Actor1CountryCode", ""),
                row.get("Actor2CountryCode", ""),
            ),
            axis=1,
        )

    if nlp_sample_size is None or nlp_sample_size < 0:
        target_indices = list(out.index)
    else:
        target_indices = list(out.index[:nlp_sample_size])

    total_targets = len(target_indices)
    if total_targets == 0:
        return out, cache

    progress_every = max(500, min(25_000, max(1, total_targets // 10)))
    inference_chunk_size = max(32, min(256, max(1, batch_size * 8)))
    started_at = time.time()
    processed_count = 0
    batch_counter = 0

    def _log_progress(force: bool = False) -> None:
        nonlocal processed_count
        if not force and processed_count % progress_every != 0:
            return
        elapsed = max(1e-9, time.time() - started_at)
        rate = processed_count / elapsed
        remaining = max(0, total_targets - processed_count)
        eta_seconds = remaining / max(rate, 1e-9)
        print(
            f"[NLP] progress={processed_count:,}/{total_targets:,} rate={rate:,.1f} rows/s eta={eta_seconds/3600.0:.2f}h"
        )

    def _score_texts(texts_batch: List[str], idx_batch: List[int], batch_id: int) -> int:
        if not texts_batch:
            return 0

        print(f"[NLP-BATCH] start id={batch_id:,} size={len(texts_batch):,}")
        try:
            preds = classifier(
                texts_batch,
                candidate_labels=[NLP_CLASS_LABEL],
                multi_label=True,
                batch_size=batch_size,
                truncation=True,
                max_length=512,
            )
        except Exception as exc:
            if len(texts_batch) == 1:
                print(f"[NLP-BATCH] skip id={batch_id:,} idx={idx_batch[0]} reason={type(exc).__name__}: {exc}")
                return 1
            print(f"[NLP-BATCH] split id={batch_id:,} size={len(texts_batch):,} reason={type(exc).__name__}: {exc}")
            mid = len(texts_batch) // 2
            left = _score_texts(texts_batch[:mid], idx_batch[:mid], batch_id=batch_id * 2)
            right = _score_texts(texts_batch[mid:], idx_batch[mid:], batch_id=batch_id * 2 + 1)
            return left + right

        if isinstance(preds, dict):
            preds = [preds]

        if len(preds) < len(texts_batch):
            preds = list(preds) + [{} for _ in range(len(texts_batch) - len(preds))]

        for idx, text, pred in zip(idx_batch, texts_batch, preds):
            score_map = _label_scores(pred)
            r_class = float(np.clip(score_map.get(NLP_CLASS_LABEL, 0.0), 0.0, 1.0))
            r_nlp = r_class
            if r_class < NLP_NOISE_CLASS_THRESHOLD:
                r_nlp = 0.0

            out.at[idx, "r_class"] = r_class
            out.at[idx, "r_nlp"] = r_nlp
            out.at[idx, "nlp_text_preview"] = text[:180]

            cache[text] = {
                "r_class": r_class,
                "r_nlp": r_nlp,
                "nlp_text_preview": text[:180],
            }

        print(f"[NLP-BATCH] done id={batch_id:,} rows={len(texts_batch):,}")
        return len(texts_batch)

    pending_texts: List[str] = []
    pending_idx: List[int] = []

    for idx in target_indices:
        text = str(out.at[idx, "nlp_text"] or "")
        if text in cache:
            cached = cache[text]
            out.at[idx, "r_class"] = float(cached.get("r_class", 0.0))
            out.at[idx, "r_nlp"] = float(cached.get("r_nlp", 0.0))
            out.at[idx, "nlp_text_preview"] = str(cached.get("nlp_text_preview", ""))
            processed_count += 1
            _log_progress()
            continue

        if not text:
            text = prepare_text("", str(out.at[idx, "SOURCEURL"]), str(out.at[idx, "EventCode"]), str(out.at[idx, "Actor1CountryCode"]), str(out.at[idx, "Actor2CountryCode"]))
            out.at[idx, "nlp_text"] = text

        pending_texts.append(text)
        pending_idx.append(idx)

        if len(pending_texts) >= inference_chunk_size:
            batch_counter += 1
            processed_count += _score_texts(pending_texts, pending_idx, batch_id=batch_counter)
            pending_texts = []
            pending_idx = []
            _log_progress()

    if pending_texts:
        batch_counter += 1
        processed_count += _score_texts(pending_texts, pending_idx, batch_id=batch_counter)
        _log_progress(force=True)

    _log_progress(force=True)
    out["r_class"] = pd.to_numeric(out["r_class"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    out["r_nlp"] = pd.to_numeric(out["r_nlp"], errors="coerce").fillna(0.0).clip(0.0, 1.0)

    assert ((out["r_class"] >= 0.0) & (out["r_class"] <= 1.0)).all()
    assert ((out["r_nlp"] >= 0.0) & (out["r_nlp"] <= 1.0)).all()

    print(f"[NLP] model rows={total_targets:,}, cache_size={len(cache):,}")
    print(out[["SQLDATE", "nlp_text_preview", "r_class", "r_nlp"]].head(3).to_string(index=False))
    return out, cache


def compute_risk_scores(events_df: pd.DataFrame) -> pd.DataFrame:
    out = events_df.copy()
    out["GoldsteinScale"] = pd.to_numeric(out["GoldsteinScale"], errors="coerce").fillna(0.0)
    out["V2Tone"] = pd.to_numeric(out.get("V2Tone", 0.0), errors="coerce").fillna(0.0)
    out["r_class"] = pd.to_numeric(out.get("r_class", 0.0), errors="coerce").fillna(0.0).clip(0.0, 1.0)
    out["r_nlp"] = pd.to_numeric(out.get("r_nlp", 0.0), errors="coerce").fillna(0.0).clip(0.0, 1.0)

    out["r_gold"] = (np.maximum(0.0, -out["GoldsteinScale"]) / 10.0).clip(0.0, 1.0)
    out["r_tone"] = (np.maximum(0.0, -out["V2Tone"]) / 100.0).clip(0.0, 1.0)
    out["r_final"] = (0.4 * out["r_gold"] + 0.4 * out["r_nlp"] + 0.2 * out["r_tone"]).clip(0.0, 1.0)
    
    # Power law suppression forces mundane news (r_final~0.3) to ~0, while keeping wars (r_final~0.9) high
    out["r_enhanced"] = (out["r_final"] ** 6.0).clip(0.0, 1.0)

    # CALDARA PURE KEYWORD MULTIPLIER
    # DistilBERT sometimes over-scores domestic crime/fires as "geopolitical risk".
    keywords = "war|military|terrorism|missile|invasion|conflict|geopolitical|nuclear|troops"
    has_keyword = out.get("SOURCEURL", pd.Series(dtype=str)).astype(str).str.contains(keywords, case=False, regex=True)

    # Boost keyword events massively to match Caldara's exact methodology
    out.loc[has_keyword, "r_enhanced"] = (out.loc[has_keyword, "r_enhanced"] * 10.0).clip(0.0, 1.0)

    print("[RISK] computed r_gold/r_nlp/r_tone/r_final")
    print(out[["SQLDATE", "r_gold", "r_nlp", "r_tone", "r_final"]].head(3).to_string(index=False))
    return out


def compute_event_weight(events_df: pd.DataFrame) -> pd.DataFrame:
    out = events_df.copy()
    out["NumMentions"] = pd.to_numeric(out["NumMentions"], errors="coerce").fillna(0.0)
    out["EventWeight"] = out["NumMentions"] * np.log1p(out["NumMentions"].clip(lower=0.0))
    out["EventWeight"] = pd.to_numeric(out["EventWeight"], errors="coerce").fillna(0.0).clip(lower=0.0)
    print("[WEIGHT] computed EventWeight")
    print(out[["SQLDATE", "NumMentions", "r_enhanced", "EventWeight"]].head(3).to_string(index=False))
    return out


def _include_mask(df: pd.DataFrame, scope: str) -> pd.Series:
    """Diagnostic mask – counts how many events pass the traditional conflict filter."""
    event_mask = df["EventCode"].astype(str).str.startswith(INCLUDE_EVENT_PREFIXES, na=False)
    nlp_mask = pd.to_numeric(df.get("r_nlp", 0.0), errors="coerce").fillna(0.0) > 0.15
    goldstein_mask = pd.to_numeric(df.get("r_gold", 0.0), errors="coerce").fillna(0.0) > 0.3
    include = event_mask | nlp_mask | goldstein_mask
    if scope == "india":
        india_mask = (
            df.get("Actor1CountryCode", "").astype(str).str.upper().isin(INDIA_CODES)
            | df.get("Actor2CountryCode", "").astype(str).str.upper().isin(INDIA_CODES)
        )
        include = include & india_mask
    return include


def process_day(
    day: pd.Timestamp,
    events_path: Optional[Path],
    gkg_path: Optional[Path],
    classifier,
    cache: Dict[str, Dict[str, object]],
    scope: str,
    use_nlp: bool,
    nlp_sample_size: Optional[int],
    batch_size: int,
    max_rows: Optional[int],
) -> Tuple[pd.DataFrame, Dict[str, Dict[str, object]]]:
    day_key = pd.Timestamp(day).normalize()
    if events_path is None or not events_path.exists():
        return pd.DataFrame([
            {"SQLDATE": day_key, "TotalMentions_t": 0.0, "Risk_t": 0.0, "IncludedEvents_t": 0, "AllEvents_t": 0}
        ]), cache

    events_raw = _read_events_file(events_path, max_rows=max_rows)
    gkg_raw = _read_gkg_file(gkg_path, max_rows=max_rows) if gkg_path is not None and gkg_path.exists() else pd.DataFrame(columns=GKG_COLS)

    events = _clean_events(events_raw, start_date=None, end_date=None)
    gkg = _clean_gkg(gkg_raw)
    if events.empty:
        return pd.DataFrame([
            {"SQLDATE": day_key, "TotalMentions_t": 0.0, "Risk_t": 0.0, "IncludedEvents_t": 0, "AllEvents_t": 0}
        ]), cache

    # Keep only rows belonging to the intended day; some exports can contain spillover dates.
    events = events[events["SQLDATE"].dt.normalize() == day_key].reset_index(drop=True)
    if events.empty:
        return pd.DataFrame([
            {"SQLDATE": day_key, "TotalMentions_t": 0.0, "Risk_t": 0.0, "IncludedEvents_t": 0, "AllEvents_t": 0}
        ]), cache

    events = deduplicate(events)
    merged = merge_gkg(events, gkg)
    merged["nlp_text"] = merged.apply(
        lambda row: prepare_text(
            row.get("processed_text", ""),
            row.get("SOURCEURL", ""),
            row.get("EventCode", ""),
            row.get("Actor1CountryCode", ""),
            row.get("Actor2CountryCode", ""),
        ),
        axis=1,
    )

    scored, cache = compute_nlp_scores(
        merged,
        classifier=classifier,
        use_nlp=use_nlp,
        nlp_sample_size=nlp_sample_size,
        batch_size=batch_size,
        url_score_cache=cache,
    )
    risk_scored = compute_risk_scores(scored)
    weighted = compute_event_weight(risk_scored)

    # ── Caldara-style aggregation ─────────────────────────────────────────
    # ALL events contribute to Risk_t, weighted by their risk score.
    # r_enhanced is the soft "keyword match" — events with zero risk
    # contribute zero; high-risk events contribute proportionally.
    # This is the GDELT analogue of Caldara counting risk-keyword articles.
    risk_t = float((weighted["r_enhanced"] * weighted["EventWeight"]).sum())

    # Diagnostic: how many events pass the traditional conflict filter
    include = _include_mask(weighted, scope=scope)

    day_row = pd.DataFrame([
        {
            "SQLDATE": day.normalize(),
            "TotalMentions_t": float(weighted["NumMentions"].sum()),
            "Risk_t": risk_t,
            "IncludedEvents_t": int(include.sum()),
            "AllEvents_t": int(len(weighted)),
        }
    ])
    return day_row, cache


def build_history(
    events_path: str,
    gkg_path: str,
    output_dir: str,
    scope: str = "global",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_rows: Optional[int] = None,
    max_event_files: Optional[int] = None,
    max_gkg_files: Optional[int] = None,
    disable_nlp: bool = False,
    nlp_sample_size: int = -1,
    batch_size: int = 16,
    model_name: str = "typeform/distilbert-base-uncased-mnli",
    device: str = "auto",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    event_map = _build_file_map(events_path, start_date, end_date, max_event_files)
    gkg_map = _build_file_map(gkg_path, start_date, end_date, max_gkg_files)

    start_ts = _parse_bound_date(start_date)
    end_ts = _parse_bound_date(end_date)
    if start_ts is None:
        start_ts = min(event_map.keys()) if event_map else min(gkg_map.keys())
    if end_ts is None:
        end_ts = max(event_map.keys()) if event_map else max(gkg_map.keys())

    if start_ts is None or end_ts is None:
        raise RuntimeError("No date-stamped files found in the requested range.")

    full_dates = pd.date_range(start=start_ts.normalize(), end=end_ts.normalize(), freq="D")
    use_nlp = not disable_nlp
    nlp_limit = None if nlp_sample_size is not None and nlp_sample_size < 0 else nlp_sample_size

    classifier = None
    if use_nlp:
        classifier = _build_classifier(model_name=model_name, device=device)

    cache: Dict[str, Dict[str, object]] = {}
    rows: List[pd.DataFrame] = []

    for i, day in enumerate(full_dates, start=1):
        event_file = event_map.get(day.normalize())
        gkg_file = gkg_map.get(day.normalize())
        print(f"[DAY] {day.date()} events={'yes' if event_file else 'no'} gkg={'yes' if gkg_file else 'no'}")
        day_row, cache = process_day(
            day=day,
            events_path=event_file,
            gkg_path=gkg_file,
            classifier=classifier,
            cache=cache,
            scope=scope,
            use_nlp=use_nlp,
            nlp_sample_size=nlp_limit,
            batch_size=batch_size,
            max_rows=max_rows,
        )
        rows.append(day_row)

        if i % 25 == 0 or i == len(full_dates):
            print(f"[DAY] progress={i:,}/{len(full_dates):,}")

    daily = pd.concat(rows, ignore_index=True)
    daily = daily.sort_values("SQLDATE").reset_index(drop=True)
    full_range = pd.DataFrame({"SQLDATE": full_dates})
    daily = full_range.merge(daily, on="SQLDATE", how="left")
    daily["TotalMentions_t"] = pd.to_numeric(daily["TotalMentions_t"], errors="coerce").fillna(0.0)
    daily["Risk_t"] = pd.to_numeric(daily["Risk_t"], errors="coerce").fillna(0.0)
    daily["IncludedEvents_t"] = pd.to_numeric(daily.get("IncludedEvents_t", 0), errors="coerce").fillna(0).astype(int)
    daily["AllEvents_t"] = pd.to_numeric(daily.get("AllEvents_t", 0), errors="coerce").fillna(0).astype(int)

    # Fix GDELT data outages (days with 0 mentions) using interpolation
    bad_mask = daily["TotalMentions_t"] == 0.0
    daily.loc[bad_mask, "Risk_t"] = np.nan
    daily.loc[bad_mask, "TotalMentions_t"] = np.nan
    daily["Risk_t"] = daily["Risk_t"].interpolate(method="linear").fillna(0.0)
    daily["TotalMentions_t"] = daily["TotalMentions_t"].interpolate(method="linear").fillna(0.0)

    # SMOOTHED DENOMINATOR: 30-day average prevents massive non-political internet events from crashing the index
    daily["Smoothed_TotalMentions"] = daily["TotalMentions_t"].rolling(window=30, min_periods=1).mean()

    epsilon = 1e-6
    daily["GPR_t_raw"] = np.where(
        daily["Smoothed_TotalMentions"] > 0,
        daily["Risk_t"] / (daily["Smoothed_TotalMentions"] + epsilon),
        0.0,
    )
    daily["GPR_t_raw"] = pd.to_numeric(daily["GPR_t_raw"], errors="coerce").fillna(0.0).clip(lower=0.0)

    # EWM smoothing for Caldara-style continuity
    daily["GPR_t"] = daily["GPR_t_raw"].ewm(span=SMOOTHING_SPAN, min_periods=1).mean()
    daily["GPR_t"] = daily["GPR_t"].clip(lower=0.0)

    assert np.isfinite(daily[["TotalMentions_t", "Risk_t", "GPR_t", "GPR_t_raw"]].to_numpy()).all(), "Non-finite values in daily output"
    assert not daily[["SQLDATE", "TotalMentions_t", "Risk_t", "GPR_t"]].isna().any().any(), "NaNs in daily output"

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
    monthly["Index_t"] = pd.to_numeric(monthly["Index_t"], errors="coerce").fillna(0.0)
    assert np.isfinite(monthly[["MonthlyGPR", "Index_t"]].to_numpy()).all(), "Non-finite values in monthly output"
    assert not monthly[["SQLDATE", "MonthlyGPR", "Index_t"]].isna().any().any(), "NaNs in monthly output"

    print(f"[GPR] scope={scope}, daily rows={len(daily):,}, monthly rows={len(monthly):,}")
    print(daily.head(3).to_string(index=False))
    print(monthly.head(3).to_string(index=False))
    print(f"[GPR] epsilon={epsilon:.6f}")
    return daily, monthly


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Streaming GPR pipeline with DistilBERT and GKG merge")
    parser.add_argument("--events-path", required=True, help="Events CSV folder or file")
    parser.add_argument("--gkg-path", required=True, help="GKG CSV folder or file")
    parser.add_argument("--output-dir", default="data", help="Directory for output files")
    parser.add_argument("--max-rows", type=int, default=None, help="Optional row cap per input file")
    parser.add_argument("--max-event-files", type=int, default=None, help="Optional cap on number of event files")
    parser.add_argument("--max-gkg-files", type=int, default=None, help="Optional cap on number of GKG files")
    parser.add_argument("--scope", choices=["india", "global"], default="global", help="Aggregation scope")
    parser.add_argument("--start-date", required=True, help="Inclusive start date YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="Inclusive end date YYYY-MM-DD")
    parser.add_argument("--disable-nlp", action="store_true", help="Disable NLP scoring")
    parser.add_argument("--nlp-sample-size", type=int, default=-1, help="Run NLP on first N rows per day; -1 for all")
    parser.add_argument("--batch-size", type=int, default=16, help="NLP batch size")
    parser.add_argument("--model-name", default="typeform/distilbert-base-uncased-mnli", help="Zero-shot model name")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto", help="Inference device")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    daily, monthly = build_history(
        events_path=args.events_path,
        gkg_path=args.gkg_path,
        output_dir=args.output_dir,
        scope=args.scope,
        start_date=args.start_date,
        end_date=args.end_date,
        max_rows=args.max_rows,
        max_event_files=args.max_event_files,
        max_gkg_files=args.max_gkg_files,
        disable_nlp=args.disable_nlp,
        nlp_sample_size=args.nlp_sample_size,
        batch_size=args.batch_size,
        model_name=args.model_name,
        device=args.device,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    daily_path = output_dir / "daily_gpr_final.csv"
    monthly_path = output_dir / "monthly_gpr_index_final.csv"
    daily.to_csv(daily_path, index=False)
    monthly.to_csv(monthly_path, index=False)

    print(f"[SAVE] {daily_path}")
    print(f"[SAVE] {monthly_path}")


if __name__ == "__main__":
    main()
