"""
Forsyt — unified REST API for geopolitical risk intelligence.

Beginner note — what is this file?
    This is a Flask app: Flask is a small Python web framework that lets you
    turn plain Python functions into HTTP endpoints just by putting an
    `@app.get("/some/path")` decorator above them. When a browser (or, in
    this project, the React frontend) makes a GET request to that path, Flask
    runs the decorated function and sends back whatever it returns — here,
    always `jsonify(...)`, which converts a Python dict into a JSON HTTP
    response. This file itself only wires up routes -> handler functions; the
    actual data-fetching logic lives in api/gpr_service.py and
    api/page_bundles.py, which this file imports and calls.

    Routes prefixed "/api/pages/..." return one big combined JSON payload per
    dashboard screen ("bundles") so the frontend can render a whole page
    from a single request instead of many small ones.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NEWS_DATASET = REPO_ROOT / "news_dataset"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv(NEWS_DATASET / ".env")

from news_dataset.api.gpr_service import (  # noqa: E402
    build_dual_signal_payload,
    get_events_feed,
    get_health_snapshot,
    get_platform_status,
)
from news_dataset.api.page_bundles import (  # noqa: E402
    build_corridor_bundle,
    build_home_bundle,
    build_macro_bundle,
    build_news_bundle,
    build_portfolio_bundle,
    build_quality_bundle,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

CACHEABLE_PATHS = ("/api/pages/",)


def _maybe_cache_headers(response, path: str):
    if any(path.startswith(prefix) for prefix in CACHEABLE_PATHS):
        response.headers["Cache-Control"] = "max-age=120, stale-while-revalidate=300"
    return response


app = Flask(__name__)


@app.after_request
def add_cache_headers(response):
    return _maybe_cache_headers(response, request.path)


CORS(
    app,
    resources={
        r"/api/*": {"origins": "*"},
        r"/health*": {"origins": "*"},
    },
)


@app.get("/")
# Landing page for the API itself — lists every available endpoint so a
# developer hitting the bare API URL in a browser can see what's here.
def root():
    return jsonify({
        "service": "forsyt-api",
        "frontend_dev": "cd frontend && npm run dev",
        "endpoints": {
            "health": "/health",
            "status": "/api/status",
            "events": "/api/events/feed",
            "news_image": "/api/news/image",
            "dual_signal": "/api/market/dual-signal",
            "pages_home": "/api/pages/home",
            "pages_macro": "/api/pages/macro",
            "pages_news": "/api/pages/news",
            "pages_corridor": "/api/pages/corridor",
            "pages_portfolio": "/api/pages/portfolio",
            "pages_quality": "/api/pages/quality",
        },
    })


# Simple "is the server up" check — returns article counts + latest
# GPR/corridor/news dates so a monitoring tool can see if data is fresh.
@app.get("/health")
@app.get("/health/")
def health():
    return jsonify(get_health_snapshot())


# Freshness/status summary: which data source (Postgres vs CSV fallback) is
# being used, when each part of the pipeline last ran, and any staleness
# warnings.
@app.get("/api/status")
def api_status():
    return jsonify(get_platform_status())


# The raw scrollable news feed: recent tagged articles, optionally filtered
# by theme/corridor/tier/date range via query-string parameters.
@app.get("/api/events/feed")
def api_events_feed():
    return jsonify({
        "events": get_events_feed(
            limit=int(request.args.get("limit", 100)),
            theme=request.args.get("theme"),
            corridor=request.args.get("corridor"),
            tier=request.args.get("tier"),
            start=request.args.get("start"),
            end=request.args.get("end"),
            tagged_only=request.args.get("tagged_only", "").lower() in {"1", "true", "yes"},
        ),
        "source": "postgresql",
    })


# Given a news article's URL (?link=...), tries to find a thumbnail image for
# it by fetching the page and reading its og:image/twitter:image HTML tag.
@app.get("/api/news/image")
def api_news_image():
    from news_dataset.api.link_preview import resolve_news_image

    link = request.args.get("link", "").strip()
    if not link:
        return jsonify({"error": "link required", "image_url": None}), 400
    return jsonify({"image_url": resolve_news_image(link)})


# The combined "geopolitical risk + market volatility" reading used on the
# stress-monitor page — merges the GPR index with NIFTY price data.
@app.get("/api/market/dual-signal")
def api_dual_signal():
    refresh = request.args.get("refresh", "").lower() in {"1", "true", "yes"}
    try:
        payload = build_dual_signal_payload(refresh=refresh)
        return jsonify(payload)
    except Exception as exc:
        logger.exception("dual-signal failed")
        return jsonify({"error": str(exc)}), 500


# Everything the Home dashboard page needs in one response: health, current
# GPR score, corridor list, market quotes, dual signal, and platform status.
@app.get("/api/pages/home")
def api_pages_home():
    try:
        return jsonify(build_home_bundle())
    except Exception as exc:
        logger.exception("home bundle failed")
        return jsonify({"error": str(exc)}), 503


# Everything the Macro/dual-signal dashboard page needs: dual signal, market
# quotes + indicators, GPR history, corridors, and market chart histories.
@app.get("/api/pages/macro")
def api_pages_macro():
    try:
        return jsonify(build_macro_bundle())
    except Exception as exc:
        logger.exception("macro bundle failed")
        return jsonify({"error": str(exc)}), 503


# Everything the News feed page needs: tagged events plus GPR context so the
# feed can be shown alongside the risk trend.
@app.get("/api/pages/news")
def api_pages_news():
    try:
        limit = int(request.args.get("limit", 50))
        return jsonify(build_news_bundle(limit=limit))
    except Exception as exc:
        logger.exception("news bundle failed")
        return jsonify({"error": str(exc)}), 503


# Everything the Corridor (trade-route risk) page needs, optionally scoped to
# one corridor via ?corridor=.
@app.get("/api/pages/corridor")
def api_pages_corridor():
    corridor = request.args.get("corridor")
    try:
        feed_limit = int(request.args.get("limit", 40))
        return jsonify(build_corridor_bundle(corridor=corridor, feed_limit=feed_limit))
    except Exception as exc:
        logger.exception("corridor bundle failed")
        return jsonify({"error": str(exc)}), 503


# Everything the Portfolio-context page needs: current GPR, dual signal, and
# a handful of market quotes relevant to a portfolio view.
@app.get("/api/pages/portfolio")
def api_pages_portfolio():
    try:
        return jsonify(build_portfolio_bundle())
    except Exception as exc:
        logger.exception("portfolio bundle failed")
        return jsonify({"error": str(exc)}), 503


# The "how accurate is this index" methodology/quality report — pass-fail
# validation checks plus pipeline health, shown on the accuracy/quality page.
@app.get("/api/pages/quality")
def api_pages_quality():
    refresh = request.args.get("refresh", "").lower() in {"1", "true", "yes"}
    try:
        return jsonify(build_quality_bundle(refresh=refresh))
    except Exception as exc:
        logger.exception("quality bundle failed")
        return jsonify({"error": str(exc)}), 503


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(debug=True, host="127.0.0.1", port=port)
