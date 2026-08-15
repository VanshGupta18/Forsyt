"""Driving-headline selection for the Indian Market Stress Monitor."""

from __future__ import annotations

from typing import Any

GEO_THEME_TOKENS = (
    "armedconflict",
    "terror",
    "invasion",
    "coup",
    "sanction",
    "blockade",
    "war",
    "military",
    "border",
    "nuclear",
    "conflict",
    "geopolit",
    "missile",
    "strike",
    "escalat",
)

MARKET_KEYWORDS = (
    "market",
    "nifty",
    "sensex",
    "stock",
    "rupee",
    "inr",
    "rbi",
    "inflation",
    "bse",
    "nse",
    "forex",
    "equity",
    "sebi",
    "gdp",
    "sanction",
    "crude",
    "oil",
    "vix",
    "bond",
    "yield",
    "fii",
    "dii",
    "trade",
    "economy",
    "monetary",
    "fiscal",
    "import",
    "export",
)


def _article_text(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("title") or ""),
        str(row.get("nlp_themes") or ""),
        str(row.get("nlp_locations") or ""),
        str(row.get("matched_keywords") or ""),
    ]
    return " ".join(parts).lower()


def _normalize_themes(row: dict[str, Any]) -> str:
    themes = row.get("nlp_themes") or ""
    if themes:
        return str(themes)
    raw = row.get("matched_keywords")
    if not raw:
        return ""
    try:
        import json

        kw = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(kw, list):
            return ", ".join(str(k) for k in kw if k)
        if isinstance(kw, dict):
            return ", ".join(f"{k}: {v}" for k, v in kw.items())
        return str(kw)
    except Exception:
        return str(raw)


def _passes_geo_gate(row: dict[str, Any], text: str) -> bool:
    if row.get("tier") == 1:
        return True
    if any(token in text for token in GEO_THEME_TOKENS):
        return True
    tone_neg = row.get("nlp_tone_neg")
    try:
        if tone_neg is not None and float(tone_neg) >= 0.35:
            return True
    except (TypeError, ValueError):
        pass
    return False


def _passes_market_gate(text: str) -> bool:
    return any(kw in text for kw in MARKET_KEYWORDS)


def _corridor_match(text: str, top_corridor: str | None) -> bool:
    if not top_corridor:
        return False
    slug = top_corridor.lower().replace("_", " ")
    tokens = [t for t in slug.split() if len(t) > 3]
    return any(t in text for t in tokens)


def _classify_why(market: bool, corridor: bool) -> str:
    if corridor:
        return "corridor_match"
    if market:
        return "market_keyword"
    return "geo_theme"


def _serialize_row(row: dict[str, Any], why: str) -> dict[str, Any]:
    return {
        "title": row.get("title"),
        "source": row.get("source"),
        "link": row.get("link"),
        "nlp_themes": _normalize_themes(row),
        "nlp_locations": row.get("nlp_locations"),
        "published_at": row.get("published_at") or row.get("scraped_at"),
        "why_included": why,
    }


def select_driving_events(
    rows: list[dict[str, Any]],
    *,
    limit: int = 8,
    top_corridor: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    both: list[dict[str, Any]] = []
    geo_only: list[dict[str, Any]] = []

    for row in rows:
        text = _article_text(row)
        if not _passes_geo_gate(row, text):
            continue
        market = _passes_market_gate(text)
        corridor = _corridor_match(text, top_corridor)
        why = _classify_why(market, corridor)
        item = _serialize_row(row, why)
        if market or corridor:
            both.append(item)
        else:
            geo_only.append(item)

    gate_b_relaxed = len(both) < 3 and len(geo_only) > 0
    selected = (both + geo_only) if gate_b_relaxed else both
    if not selected:
        selected = both + geo_only

    meta = {
        "candidates_scanned": len(rows),
        "geo_market_pass": len(both),
        "geo_only_pass": len(geo_only),
        "returned": min(len(selected), limit),
        "gate_b_relaxed": gate_b_relaxed,
    }
    return selected[:limit], meta
