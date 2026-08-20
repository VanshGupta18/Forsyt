"""
Forsyt — unified REST API for geopolitical risk intelligence.
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


@app.get("/health")
@app.get("/health/")
def health():
    return jsonify(get_health_snapshot())


@app.get("/api/status")
def api_status():
    return jsonify(get_platform_status())


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


@app.get("/api/news/image")
def api_news_image():
    from news_dataset.api.link_preview import resolve_news_image

    link = request.args.get("link", "").strip()
    if not link:
        return jsonify({"error": "link required", "image_url": None}), 400
    return jsonify({"image_url": resolve_news_image(link)})


@app.get("/api/market/dual-signal")
def api_dual_signal():
    refresh = request.args.get("refresh", "").lower() in {"1", "true", "yes"}
    try:
        payload = build_dual_signal_payload(refresh=refresh)
        return jsonify(payload)
    except Exception as exc:
        logger.exception("dual-signal failed")
        return jsonify({"error": str(exc)}), 500


@app.get("/api/pages/home")
def api_pages_home():
    try:
        return jsonify(build_home_bundle())
    except Exception as exc:
        logger.exception("home bundle failed")
        return jsonify({"error": str(exc)}), 503


@app.get("/api/pages/macro")
def api_pages_macro():
    try:
        return jsonify(build_macro_bundle())
    except Exception as exc:
        logger.exception("macro bundle failed")
        return jsonify({"error": str(exc)}), 503


@app.get("/api/pages/news")
def api_pages_news():
    try:
        limit = int(request.args.get("limit", 50))
        return jsonify(build_news_bundle(limit=limit))
    except Exception as exc:
        logger.exception("news bundle failed")
        return jsonify({"error": str(exc)}), 503


@app.get("/api/pages/corridor")
def api_pages_corridor():
    corridor = request.args.get("corridor")
    try:
        feed_limit = int(request.args.get("limit", 40))
        return jsonify(build_corridor_bundle(corridor=corridor, feed_limit=feed_limit))
    except Exception as exc:
        logger.exception("corridor bundle failed")
        return jsonify({"error": str(exc)}), 503


@app.get("/api/pages/portfolio")
def api_pages_portfolio():
    try:
        return jsonify(build_portfolio_bundle())
    except Exception as exc:
        logger.exception("portfolio bundle failed")
        return jsonify({"error": str(exc)}), 503


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
