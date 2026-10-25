"""Country cards — India-relative risk brief per country.

GET /api/pages/country/<fips>  -> one bundle:
    country, score{value,band,trend,low_confidence}, channels, history,
    corridors, market, summary

Reads gpr_bilateral_daily.csv (built by `python gpr_index/main.py bilateral`)
and reuses the corridor CSV + the ai_summary Gemini/fallback path. Degrades to
an explicit low_confidence state when data is missing — never 500s the UI.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from flask import Flask, jsonify

from news_dataset.api.ai_summary import country_summary
from news_dataset.api.cache import _MISSING, cache_get, cache_set
from news_dataset.api.countries import FIPS_CODES, country_meta
from news_dataset.api.country_facts import (
    country_energy,
    country_facts,
    country_macro,
    country_ports,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GPR_OUTPUT = REPO_ROOT / "gpr_index" / "outputs"
BILATERAL_CSV = GPR_OUTPUT / "gpr_bilateral_daily.csv"
CORRIDOR_CSV = GPR_OUTPUT / "gpr_corridor_daily.csv"
CACHE_TTL = 3600
MIN_ARTICLES = 5  # below this the pair is low-confidence

# 100 = baseline-average India-relative stress for the pair.
_BANDS = [(90, "Low"), (130, "Normal"), (200, "Elevated"), (float("inf"), "High")]

# fips -> market index ticker (yfinance). Live values are a later upgrade; the
# card shows the symbol and a null value until then (null is a first-class state).
_TICKERS = {
    "CH": "^SSEC", "US": "^GSPC", "RS": "IMOEX.ME", "SA": "^TASI.SR",
    "AE": "^ADI", "BG": "^DSEX", "CE": "^CSE", "IS": "^TA125.TA",
    "QA": "^QSI", "SN": "^STI", "PK": "^KSE", "IR": None, "NP": None,
    "BM": None, "AF": None,
}


def _band(value: float) -> str:
    for hi, label in _BANDS:
        if value < hi:
            return label
    return "High"


def _load_bilateral() -> pd.DataFrame:
    if not BILATERAL_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(BILATERAL_CSV, parse_dates=["date"])
    return df


def _corridors_for(fips: str) -> list[dict]:
    meta = country_meta(fips) or {}
    ids = meta.get("corridors") or []
    if not ids or not CORRIDOR_CSV.exists():
        return []
    cdf = pd.read_csv(CORRIDOR_CSV, parse_dates=["date"])
    out = []
    for cid in ids:
        rows = cdf[cdf["corridor"] == cid]
        if rows.empty:
            continue
        latest = rows.sort_values("date").iloc[-1]
        out.append({
            "id": cid,
            "name": latest.get("corridor_name", cid),
            "risk_7ma": _round(latest.get("corridor_risk_7ma")),
        })
    return out


def _round(v, n=2):
    try:
        return round(float(v), n)
    except (TypeError, ValueError):
        return None


def _country_news(name: str, limit: int = 6) -> list[dict]:
    """Recent tagged articles mentioning the country (best-effort, name match)."""
    try:
        from news_dataset.api.gpr_service import get_events_feed
        events = get_events_feed(limit=120, tagged_only=False)
    except Exception:
        return []
    needle = name.lower()
    hits = [e for e in events if needle in str(e.get("title", "")).lower()]
    return [
        {"title": e.get("title"), "link": e.get("link"),
         "source": e.get("source"), "published_at": e.get("published_at")}
        for e in hits[:limit]
    ]


def _enrich(bundle: dict, meta: dict) -> dict:
    """Add free/open context: reference facts, macro indicators, country news."""
    iso2 = meta.get("iso2")
    iso3 = meta.get("iso3")
    bundle["facts"] = country_facts(iso2) if iso2 else None
    bundle["macro"] = country_macro(iso2) if iso2 else None
    bundle["ports"] = country_ports(iso3) if iso3 else None
    bundle["energy"] = country_energy(iso3) if iso3 else None
    bundle["top_events"] = _country_news(meta.get("name", ""))
    return bundle


def _channels(recent: pd.DataFrame) -> dict:
    """Event-category sums -> 0-100 bars relative to the country's own peak channel."""
    cols = [c for c in recent.columns if c.startswith("sum_") and c != "sum_none"]
    sums = {c[4:]: float(recent[c].sum()) for c in cols}
    peak = max(sums.values(), default=0.0)
    if peak <= 0:
        return {k: 0 for k in sums}
    return {k: round(100 * v / peak) for k, v in sums.items()}


def build_country_bundle(fips: str, summary: bool = True) -> dict | None:
    meta = country_meta(fips)
    if meta is None:
        return None

    df = _load_bilateral()
    sub = df[df["country_code"] == fips].sort_values("date") if not df.empty else df
    ticker = _TICKERS.get(fips)
    market = {"index": ticker, "last": None, "chg_week_pct": None} if ticker else None

    if sub is None or sub.empty:
        # No data yet for this pair — honest low-confidence card, not a crash.
        bundle = {
            "country": meta,
            "score": {"value": None, "band": None, "trend": None, "low_confidence": True},
            "channels": {}, "history": [], "corridors": _corridors_for(fips),
            "market": market,
        }
        _enrich(bundle, meta)
        if summary:
            bundle["summary"] = country_summary(bundle)["summary"]
        return bundle

    latest = sub.iloc[-1]
    value = _round(latest["bilateral_gpr_index"], 1) or 0.0
    recent = sub.tail(30)
    prev = sub.iloc[-8:-1]["bilateral_gpr_index"].mean() if len(sub) > 1 else value
    trend = "rising" if value > prev * 1.05 else "falling" if value < prev * 0.95 else "stable"
    low_conf = int(latest.get("total_articles", 0)) < MIN_ARTICLES or len(sub) < 14

    bundle = {
        "country": meta,
        "score": {"value": round(value), "band": _band(value), "trend": trend,
                  "low_confidence": low_conf},
        "channels": _channels(recent),
        "history": [{"date": d.strftime("%Y-%m-%d"), "value": _round(v, 1)}
                    for d, v in zip(recent["date"], recent["bilateral_gpr_index"])],
        "corridors": _corridors_for(fips),
        "market": market,
    }
    _enrich(bundle, meta)
    if summary:  # the agent skips it: one Gemini call per tool use hit 429s
        bundle["summary"] = country_summary(bundle)["summary"]
    return bundle


def register_country(app: Flask) -> None:
    @app.get("/api/pages/country/<fips>")
    def api_country(fips: str):
        fips = fips.upper()
        cache_key = f"country:{fips}:{BILATERAL_CSV.stat().st_mtime if BILATERAL_CSV.exists() else 0}"
        hit = cache_get(cache_key, ttl_seconds=CACHE_TTL)
        if hit is not _MISSING:
            return jsonify(hit)
        bundle = build_country_bundle(fips)
        if bundle is None:
            return jsonify({"error": f"unknown or unsupported country: {fips}"}), 404
        cache_set(cache_key, bundle)
        return jsonify(bundle)

    @app.get("/api/countries")
    def api_countries():
        return jsonify({"countries": [country_meta(f) for f in FIPS_CODES]})
