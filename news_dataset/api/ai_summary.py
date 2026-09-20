"""AI summary for the Portfolio GPR Risk panel (POST /api/portfolio/summary).

Given a portfolio's geopolitical-risk analysis, explains the overall risk, which
sectors drive it, the dominant pressure channels (GPR/oil/INR/trade), how it
behaves under the scenarios, and the live trade-route drivers.

Runs through the Strands agent built by news_dataset/agent_model.py — the same
provider the daily corridor explainer uses, so there is one model setting for
the whole project rather than one per feature. If no provider is configured, or
the call fails for any reason, this returns a deterministic narrative built from
the same numbers, so the panel never breaks.

See agent_model.py for the provider environment variables.
"""
from __future__ import annotations

import json
import logging

from flask import Flask, jsonify, request

from news_dataset import agent_model
from news_dataset.api.cache import _MISSING, cache_get, cache_set

logger = logging.getLogger(__name__)

CACHE_TTL = 3600  # summaries are stable for a given portfolio snapshot


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _portfolio_deterministic(a: dict) -> str:
    """A grounded portfolio summary from the analysis numbers (no LLM)."""
    rs = a.get("risk_score")
    rb = a.get("risk_band")
    pr = a.get("pressures") or {}
    drivers = a.get("drivers") or {}
    sectors = a.get("sectors") or []
    scen = a.get("scenarios") or []
    top = sorted(sectors, key=lambda s: abs(_num(s.get("contribution"))), reverse=True)[:3]

    parts: list[str] = []
    if rs is not None:
        parts.append(f"Portfolio GPR risk is {rs}" + (f" ({rb})." if rb else "."))
    if top:
        tops = ", ".join(f"{s.get('sector')} ({_num(s.get('contribution')):+.2f})" for s in top)
        parts.append(f"Sector risk is led by {tops}.")
    chans = [
        f"{label} {pr[k]}"
        for k, label in (("broad", "GPR"), ("energy", "oil"), ("fx", "INR"), ("trade", "trade"))
        if pr.get(k) is not None
    ]
    if chans:
        parts.append("Dominant pressure channels: " + ", ".join(chans) + ".")
    if scen:
        parts.append(
            "Under stress scenarios it moves to "
            + "; ".join(f"{s.get('name')} {s.get('score')} ({_num(s.get('delta')):+g})" for s in scen)
            + "."
        )
    if drivers.get("energy_corridor") or drivers.get("trade_corridor"):
        parts.append(
            f"Live route drivers: energy via {drivers.get('energy_corridor', '—')}, "
            f"trade via {drivers.get('trade_corridor', '—')}."
        )
    return " ".join(parts) or "Not enough data to summarise this portfolio."


def _portfolio_prompt(a: dict) -> str:
    return (
        "You are a markets-risk explainer for an India-focused geopolitical-risk platform. "
        "Given JSON for a whole PORTFOLIO's geopolitical-risk analysis, write a flowing prose "
        "summary of 4-6 short sentences. Cover the overall GPR risk score and what its band means, "
        "which sectors drive the exposure and in which direction, the dominant pressure channels "
        "among news/GPR, oil, INR and trade, how the portfolio moves under the given stress "
        "scenarios, and the live trade-route drivers. Write only the summary itself - do not restate "
        "these instructions, do not number or label points, do not count sentences, do not answer as "
        "a checklist. Ground every claim strictly in the numbers provided; never invent figures or "
        "tickers. Neutral and factual, plain text only (no markdown, no headings, no bullet "
        "characters). This is NOT investment advice - do not recommend buying, selling, or holding.\n\n"
        f"ANALYSIS: {json.dumps(a, default=str)}"
    )


def _agent_summary(prompt: str) -> str:
    """One turn through the configured model. No tools — this is a caption task."""
    # Deliberately minimal: _portfolio_prompt() is self-contained (persona,
    # formatting rules and the not-investment-advice constraint all live there,
    # tuned against real output). Restating any of it here risks contradicting it.
    agent = agent_model.build_agent(
        "Follow the user's instructions exactly.",
        temperature=0.3,
    )
    text = str(agent(prompt)).strip()
    if not text:
        raise ValueError("empty model response")
    return text


def register_ai_summary(app: Flask) -> None:
    @app.post("/api/portfolio/summary")
    def api_portfolio_summary():
        body = request.get_json(silent=True) or {}
        a = body.get("analysis") or {}
        if a.get("risk_score") is None:
            return jsonify({"error": "analysis required"}), 400

        sectors = a.get("sectors") or []
        sig = "|".join(f"{s.get('sector')}:{s.get('weight')}" for s in sectors)
        cache_key = f"pfsum:{a.get('risk_score')}:{a.get('gpr_index')}:{hash(sig)}"
        hit = cache_get(cache_key, ttl_seconds=CACHE_TTL)
        if hit is not _MISSING:
            return jsonify(hit)

        fallback = _portfolio_deterministic(a)
        if not agent_model.is_configured():
            out = {"summary": fallback, "source": "deterministic"}
        else:
            try:
                out = {
                    "summary": _agent_summary(_portfolio_prompt(a)),
                    # the provider name, so the UI can show what produced this
                    "source": agent_model.provider_name(),
                }
            except Exception:
                logger.exception("agent portfolio summary failed; using deterministic fallback")
                out = {"summary": fallback, "source": "fallback"}

        cache_set(cache_key, out)
        return jsonify(out)
