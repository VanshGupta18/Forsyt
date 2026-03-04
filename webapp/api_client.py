"""
API client for the India AI-GPR web app.
Wraps all FastAPI endpoint calls with error handling and fallback mock data.
Set API_URL and API_KEY in .env (or environment) — defaults to localhost for dev.
"""

import os
import json
import logging
import requests
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "dev_key")

HEADERS = {"Authorization": f"Bearer {API_KEY}"}
TIMEOUT = 8


def _get(path: str, params: dict = None) -> Optional[dict]:
    try:
        resp = requests.get(f"{API_URL}{path}", headers=HEADERS,
                            params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"GET {path} failed: {e}")
        return None


def _post(path: str, payload) -> Optional[dict]:
    try:
        resp = requests.post(f"{API_URL}{path}", headers=HEADERS,
                             json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"POST {path} failed: {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Public API wrappers
# ──────────────────────────────────────────────────────────────────────────────

def get_gpr_latest() -> dict:
    data = _get("/gpr/latest")
    if data:
        return data
    # Demo fallback so the app still works without a live backend
    return {
        "date": str(date.today()),
        "normalized_gpr": 1.42,
        "data_quality_flag": "OK",
        "source": "demo",
    }


def get_gpr_history(days: int = 90) -> list:
    from_d = (date.today() - timedelta(days=days)).isoformat()
    to_d   = date.today().isoformat()
    data = _get("/gpr/history", params={"from_date": from_d, "to_date": to_d})
    if data and "series" in data:
        return data["series"]
    return _mock_history(days)


def get_signal_latest() -> dict:
    data = _get("/signals/latest")
    if data:
        return data
    return {
        "signal": "HIGH_VOL",
        "high_vol_probability": 0.76,
        "model_version": "xgboost_v1",
        "inference_date": str(date.today()),
        "top_drivers": [
            {"feature": "india_ai_gpr_t1",   "shap_value": 0.312},
            {"feature": "nifty_vol_lag1",     "shap_value": 0.198},
            {"feature": "crude_oil_return",   "shap_value": -0.143},
        ],
        "source": "demo",
    }


def get_events(query_date: str = None, min_severity: float = 0.3) -> list:
    params = {"min_severity": min_severity}
    if query_date:
        params["query_date"] = query_date
    data = _get("/events/", params=params)
    if data and "events" in data:
        return data["events"]
    return _mock_events()


def analyse_portfolio(holdings: list) -> dict:
    """holdings = [{"ticker": "INFY", "weight": 0.30}, ...]"""
    data = _post("/portfolio/analyse", holdings)
    if data:
        return data
    return _mock_portfolio(holdings)


def get_health() -> dict:
    data = _get("/health")
    return data or {"status": "unknown", "postgres": "unknown", "redis": "unknown"}


def get_corridor_risk(country: str) -> dict:
    data = _get("/trade/corridor-risk", params={"country": country})
    if data:
        return data
    return _mock_corridor(country)


def get_all_corridors() -> list:
    data = _get("/trade/corridor-risk/all")
    if data:
        return data
    return _mock_all_corridors()


def get_corridors_by_sector(sector: str) -> dict:
    data = _get("/trade/corridor-risk/by-sector", params={"sector": sector})
    if data:
        return data
    # Fallback: filter mock data
    all_c = _mock_all_corridors()
    SECTOR_MAP = {
        "Energy":      ["Russia", "Saudi Arabia", "Iraq", "Iran"],
        "IT":          ["USA", "China"],
        "Pharma":      ["USA", "Germany"],
        "Electronics": ["China", "South Korea", "Japan"],
        "Defence":     ["Russia"],
        "Fertilisers": ["Russia"],
        "Auto":        ["Germany", "Japan", "South Korea"],
        "Textiles":    ["Bangladesh", "China"],
        "Mining":      ["Australia"],
    }
    matched = SECTOR_MAP.get(sector.title(), [])
    return {
        "sector": sector,
        "corridors": [c for c in all_c if c["country"] in matched]
    }


def _mock_corridor(country: str) -> dict:
    """Return a placeholder for unknown country in demo mode."""
    return {
        "country": country, "iso": "UNK",
        "gpr": 1.5, "sanctions": False, "sanctions_type": "None",
        "trade_volume_bn": 10.0, "trade_rank": 99,
        "primary_exports": ["—"], "primary_imports": ["—"],
        "risk_level": "MEDIUM",
        "risk_drivers": ["Demo mode — backend unreachable"],
        "sectors_exposed": ["—"],
        "corridor_note": "Live data unavailable. Connect backend for real scores.",
    }


def _mock_all_corridors() -> list:
    return [
        {"country": "China",        "iso": "CHN", "gpr": 2.8,  "risk_level": "HIGH",   "sanctions": True,  "trade_volume_bn": 136.2, "trade_rank": 1},
        {"country": "USA",          "iso": "USA", "gpr": 1.2,  "risk_level": "LOW",    "sanctions": False, "trade_volume_bn": 120.0, "trade_rank": 2},
        {"country": "UAE",          "iso": "ARE", "gpr": 0.8,  "risk_level": "LOW",    "sanctions": False, "trade_volume_bn": 84.5,  "trade_rank": 3},
        {"country": "Russia",       "iso": "RUS", "gpr": 3.6,  "risk_level": "HIGH",   "sanctions": True,  "trade_volume_bn": 65.7,  "trade_rank": 4},
        {"country": "Saudi Arabia", "iso": "SAU", "gpr": 1.4,  "risk_level": "MEDIUM", "sanctions": False, "trade_volume_bn": 52.8,  "trade_rank": 5},
        {"country": "Iraq",         "iso": "IRQ", "gpr": 2.4,  "risk_level": "MEDIUM", "sanctions": False, "trade_volume_bn": 34.0,  "trade_rank": 6},
        {"country": "Singapore",    "iso": "SGP", "gpr": 0.4,  "risk_level": "LOW",    "sanctions": False, "trade_volume_bn": 35.6,  "trade_rank": 8},
        {"country": "Germany",      "iso": "DEU", "gpr": 0.6,  "risk_level": "LOW",    "sanctions": False, "trade_volume_bn": 30.1,  "trade_rank": 7},
        {"country": "South Korea",  "iso": "KOR", "gpr": 1.1,  "risk_level": "LOW",    "sanctions": False, "trade_volume_bn": 28.3,  "trade_rank": 11},
        {"country": "Australia",    "iso": "AUS", "gpr": 0.5,  "risk_level": "LOW",    "sanctions": False, "trade_volume_bn": 25.1,  "trade_rank": 10},
        {"country": "Japan",        "iso": "JPN", "gpr": 0.7,  "risk_level": "LOW",    "sanctions": False, "trade_volume_bn": 22.4,  "trade_rank": 13},
        {"country": "Iran",         "iso": "IRN", "gpr": 3.2,  "risk_level": "HIGH",   "sanctions": True,  "trade_volume_bn": 8.2,   "trade_rank": 12},
        {"country": "Bangladesh",   "iso": "BGD", "gpr": 1.3,  "risk_level": "LOW",    "sanctions": False, "trade_volume_bn": 14.0,  "trade_rank": 9},
        {"country": "Pakistan",     "iso": "PAK", "gpr": 3.8,  "risk_level": "HIGH",   "sanctions": False, "trade_volume_bn": 0.9,   "trade_rank": 20},
        {"country": "Nepal",        "iso": "NPL", "gpr": 0.9,  "risk_level": "LOW",    "sanctions": False, "trade_volume_bn": 8.1,   "trade_rank": 15},
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Demo / mock data (used when backend is unreachable)
# ──────────────────────────────────────────────────────────────────────────────

def _mock_history(days: int) -> list:
    import math, random
    random.seed(42)
    series = []
    for i in range(days):
        d = date.today() - timedelta(days=days - i)
        val = 0.5 * math.sin(i / 15) + random.gauss(0, 0.3)
        series.append({"date": str(d), "normalized_gpr": round(val, 4),
                       "event_count": random.randint(0, 12)})
    # Inject known spikes for demo
    for idx, spike_date in enumerate(["2020-06-15", "2019-02-14", "2016-09-18"]):
        for row in series:
            if row["date"] == spike_date:
                row["normalized_gpr"] = 3.2 - idx * 0.3
    return series


def _mock_events() -> list:
    return [
        {"event_id": 1, "event_type": "military_conflict",
         "severity": 0.82, "india_exposure": 0.91, "confidence": 0.88,
         "event_date": str(date.today()),
         "raw_text": "India-Pakistan border tensions escalate near LoC"},
        {"event_id": 2, "event_type": "sanctions_imposed",
         "severity": 0.61, "india_exposure": 0.55, "confidence": 0.79,
         "event_date": str(date.today()),
         "raw_text": "US expands Iran sanctions affecting oil imports"},
        {"event_id": 3, "event_type": "trade_disruption",
         "severity": 0.38, "india_exposure": 0.72, "confidence": 0.83,
         "event_date": str(date.today()),
         "raw_text": "Red Sea shipping disruptions raise freight costs for Indian exporters"},
    ]


def _mock_portfolio(holdings: list) -> dict:
    sector_map = {
        "INFY": "IT", "TCS": "IT", "WIPRO": "IT", "HCLTECH": "IT",
        "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking",
        "RELIANCE": "Energy", "ONGC": "Energy", "COALINDIA": "Energy",
        "DRREDDY": "Pharma", "SUNPHARMA": "Pharma",
        "TATASTEEL": "Metal", "JSWSTEEL": "Metal",
    }
    beta_map = {"IT": 0.82, "Banking": 0.54, "Energy": 1.21,
                "Pharma": 0.33, "Metal": 1.44}
    gpr = 1.42  # mock current GPR
    breakdown, score, unknown = [], 0.0, []
    seen = {}
    for h in holdings:
        t = h["ticker"].upper()
        sector = sector_map.get(t)
        if not sector:
            unknown.append(t); continue
        seen[sector] = seen.get(sector, 0) + h["weight"]
    for sector, weight in seen.items():
        beta = beta_map.get(sector, 0.5)
        rc = round(weight * beta * gpr, 4)
        score += rc
        breakdown.append({"sector": sector, "total_weight": weight,
                           "gpr_beta": beta, "risk_contribution": rc})
    return {
        "portfolio_gpr_score": round(score, 4),
        "signal": "HIGH_VOL" if score > 1.0 else "LOW_VOL",
        "sector_breakdown": sorted(breakdown, key=lambda x: -x["risk_contribution"]),
        "unrecognised_tickers": unknown,
        "gpr_date": str(date.today()),
    }
