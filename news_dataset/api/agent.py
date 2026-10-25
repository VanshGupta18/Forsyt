"""Ask Forsyt — an India-relative geopolitical-risk analyst agent.

A Strands agent (multi-step, tool-using) on Gemini, whose tools wrap Forsyt's
own data. Answers free-form questions like "compare India's risk with China vs
Pakistan and what's driving it" by deciding which tools to call.

POST /api/ask  {"question": "..."}  -> {"answer": "...", "source": "..."}

Degrades gracefully: if strands-agents isn't installed OR GEMINI_API_KEY is
unset OR the loop errors, returns a deterministic answer built from the same
tools — never 500s the UI.

Env: GEMINI_API_KEY (LLM path), GEMINI_MODEL (default gemini-3.8-flash).
"""
from __future__ import annotations

import json
import logging
import os

from flask import Flask, jsonify, request

from news_dataset.api.cache import _MISSING, cache_get, cache_set
from news_dataset.api.countries import FIPS_CODES, country_meta
from news_dataset.api.country import build_country_bundle

logger = logging.getLogger(__name__)
CACHE_TTL = 3600
DEFAULT_MODEL = "gemini-3.8-flash"

SYSTEM = (
    "You are Forsyt's geopolitical-risk analyst for Indian markets. Answer questions about "
    "each country's risk RELATIVE TO INDIA and about today's Indian market stress (news risk, "
    "NIFTY volatility, joint regime, oil-GPR, driving headlines) and about recent news "
    "(search_news: use short keyword queries) using ONLY the tools provided. When you rely on a "
    "headline, cite it as \"Title\" (Source, YYYY-MM-DD); ignore search results that aren't "
    "relevant. Ground every claim "
    "strictly in tool results; never invent figures, tickers, or countries. Be concise and "
    "factual, plain text. This is NOT investment advice — never recommend buying, selling, or "
    "holding. If the tools lack the data, say so plainly."
)


# --- Tools: thin wrappers over data we already serve ------------------------

def _tool_list_countries() -> list[dict]:
    """List the countries Forsyt tracks for India-relative risk (name + FIPS code)."""
    return [country_meta(f) for f in FIPS_CODES]


def _tool_country_brief(fips: str) -> dict:
    """India-relative risk brief for one country by FIPS code (e.g. CH=China, PK=Pakistan):
    score, band, trend, dominant channels, corridors, market. Returns an error dict for
    unknown codes."""
    b = build_country_bundle((fips or "").upper(), summary=False)
    if b is None:
        return {"error": f"unknown country code {fips!r}; call list_countries first"}
    return b


def _tool_market_snapshot() -> dict:
    """Today's Indian market stress read: India news-risk (GPR) level, percentile, regime and
    7d change; NIFTY 5-day volatility forecast and regime; the joint stress regime; and the
    headlines currently driving risk; and India's oil-GPR (energy-corridor pressure)."""
    from news_dataset.api.gpr_service import _oil_gpr, build_dual_signal_payload
    d = build_dual_signal_payload()
    oil = {k: v for k, v in (_oil_gpr() or {}).items() if k != "spark"}
    geo = dict(d.get("geopolitical") or {})
    # titles + source are enough for the model; links/NLP tags only cost tokens
    geo["driving_events"] = [
        {k: e.get(k) for k in ("title", "source", "published_at")}
        for e in geo.get("driving_events") or []
    ]
    geo.pop("explain", None)
    return {"geopolitical": geo, "nifty_volatility": d.get("nifty_volatility"),
            "joint_stress": d.get("joint_stress"), "oil_gpr": oil}


def _tool_search_news(query: str, days: int = 14) -> list[dict] | dict:
    """Full-text search of Forsyt's news archive over the last `days` (max 90). Use short
    keyword queries (e.g. "Pakistan border", "crude oil"). Returns up to 8 best matches as
    {title, source, published_at, link}."""
    from news_dataset.db import search_news
    try:
        return search_news(query, days)
    except Exception:
        logger.exception("search_news failed")
        return {"error": "news search is unavailable right now"}


def _register_strands_tools():
    """Return @tool-decorated callables, or None if strands isn't available."""
    try:
        from strands import tool
    except Exception:
        return None
    return [tool(_tool_list_countries), tool(_tool_country_brief), tool(_tool_market_snapshot),
            tool(_tool_search_news)]


def _build_agent():
    """Return a Strands Agent on Gemini, or None if unavailable."""
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    tools = _register_strands_tools()
    if tools is None:
        return None
    try:
        from strands import Agent
        from strands.models.gemini import GeminiModel
        model = GeminiModel(model_id=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL))
        return Agent(model=model, tools=tools, system_prompt=SYSTEM)
    except Exception:
        logger.exception("failed to build Strands agent; falling back")
        return None


def _deterministic_answer(question: str) -> str:
    """No-LLM fallback: name any tracked countries mentioned and give their scores."""
    import re
    q = question or ""
    ql = q.lower()
    hits = [m for f in FIPS_CODES if (m := country_meta(f))
            and (m["name"].lower() in ql
                 or re.search(rf"\b{f}\b", q))]  # FIPS only as a whole uppercase token
    if not hits:
        try:
            m = _tool_market_snapshot()
            g, v, j, o = (m["geopolitical"], m["nifty_volatility"] or {},
                          m["joint_stress"] or {}, m["oil_gpr"])
            return (f"Ask Forsyt isn't fully available right now. Today's read: news risk "
                    f"{g.get('gpr_index')} ({g.get('regime')}, {g.get('geo_percentile')}th pctile); "
                    f"NIFTY 5d vol forecast {v.get('vol_forecast_5d')}% ({v.get('regime')}); joint "
                    f"stress {j.get('stress_regime')}; oil-GPR {o.get('index')}. Name a country "
                    "for its India-relative risk. (This is not investment advice.)")
        except Exception:
            logger.exception("market fallback failed")
        names = ", ".join(country_meta(f)["name"] for f in FIPS_CODES)
        return ("Ask Forsyt isn't fully available right now. I track India-relative risk for: "
                f"{names}. Name one or two to compare.")
    lines = []
    for m in hits[:3]:
        b = build_country_bundle(m["fips"], summary=False) or {}
        sc = b.get("score") or {}
        v = sc.get("value")
        lines.append(f"{m['name']}: India-relative risk "
                     + (f"{v} ({sc.get('band')}, {sc.get('trend')})." if v is not None
                        else "insufficient data.")
                     )
    return " ".join(lines) + " (This is not investment advice.)"


def answer_question(question: str) -> dict:
    agent = _build_agent()
    if agent is None:
        return {"answer": _deterministic_answer(question), "source": "deterministic"}
    try:
        result = agent(question)
        u = result.metrics.accumulated_usage
        logger.info("ask tokens in=%s out=%s cycles=%s", u.get("inputTokens"),
                    u.get("outputTokens"), result.metrics.cycle_count)
        return {"answer": str(result), "source": "agent"}
    except Exception:
        logger.exception("agent loop failed; using deterministic fallback")
        return {"answer": _deterministic_answer(question), "source": "fallback"}


def register_agent(app: Flask) -> None:
    @app.post("/api/ask")
    def api_ask():
        body = request.get_json(silent=True) or {}
        question = (body.get("question") or "").strip()
        if not question:
            return jsonify({"error": "question required"}), 400
        key = f"ask:{hash(question)}"
        hit = cache_get(key, ttl_seconds=CACHE_TTL)
        if hit is not _MISSING:
            return jsonify(hit)
        out = answer_question(question)
        cache_set(key, out)
        return jsonify(out)
