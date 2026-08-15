"""
Forsyt — unified REST API for geopolitical risk intelligence.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NEWS_DATASET = REPO_ROOT / "news_dataset"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv(NEWS_DATASET / ".env")

from news_dataset.db import (  # noqa: E402
    get_geo_articles,
    get_geo_cycle_stats,
    get_geo_feed_health,
    get_total_count,
)
from news_dataset.api.gpr_service import (  # noqa: E402
    build_dual_signal_payload,
    get_corridor_history,
    get_corridors,
    get_events_feed,
    get_gpr_current,
    get_gpr_history,
    get_news_stats,
    get_platform_status,
    serialize_rows,
)
from news_dataset.api.market_service import (  # noqa: E402
    compute_indicators,
    fetch_history,
    fetch_quotes,
)
from news_dataset.api.metrics_service import build_accuracy_metrics  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(
    app,
    resources={
        r"/api/*": {"origins": "*"},
        r"/health*": {"origins": "*"},
        r"/stats*": {"origins": "*"},
    },
)


@app.get("/")
def root():
    return jsonify({
        "service": "forsyt-api",
        "frontend_dev": "cd frontend && npm run dev",
        "endpoints": {
            "status": "/api/status",
            "gpr": "/api/gpr/current",
            "corridors": "/api/corridors",
            "events": "/api/events/feed",
            "dual_signal": "/api/market/dual-signal",
            "market_quotes": "/api/market/quotes",
            "market_history": "/api/market/history",
            "market_indicators": "/api/market/indicators",
            "metrics_accuracy": "/api/metrics/accuracy",
        },
    })

@app.get("/news")
@app.get("/news/")
def news_all():
    return serialize_rows(get_geo_articles())


@app.get("/news/<tier>")
def news_by_tier(tier: str):
    try:
        tier_val = int(tier)
    except ValueError:
        return "Invalid tier format", 400
    if tier_val not in (1, 2):
        return "Tier must be 1 or 2", 400
    return serialize_rows(get_geo_articles(tier=tier_val))


@app.get("/health")
@app.get("/health/")
def health():
    news = get_news_stats()
    status = get_platform_status()
    return jsonify({
        "status": "healthy",
        **news,
        "database": "postgresql",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "gpr_latest_date": status["latest_dates"].get("gpr"),
        "corridor_latest_date": status["latest_dates"].get("corridor"),
        "news_latest_at": status["latest_dates"].get("news"),
        "last_platform_refresh": status["last_pipeline_runs"].get("platform_refresh"),
        "stale_warning": status.get("stale_warning"),
    })


@app.get("/api/status")
def api_status():
    return jsonify(get_platform_status())


@app.get("/stats")
@app.get("/stats/")
def stats():
    feed_health = {
        source: {
            key: (value.isoformat() if hasattr(value, "isoformat") else value)
            for key, value in health.items()
        }
        for source, health in get_geo_feed_health().items()
    }
    return jsonify({
        "total_articles": get_total_count(),
        "recent_cycles": serialize_rows(get_geo_cycle_stats(limit=10)),
        "feed_health": feed_health,
    })


@app.get("/api/gpr/current")
def api_gpr_current():
    current = get_gpr_current()
    if not current:
        return jsonify({"error": "no GPR data available"}), 404
    return jsonify(current)


@app.get("/api/gpr/history")
def api_gpr_history():
    start = request.args.get("start")
    end = request.args.get("end")
    try:
        limit = int(request.args.get("limit", 500))
    except ValueError:
        return jsonify({"error": "invalid limit", "history": []}), 400
    try:
        history = get_gpr_history(start=start, end=end, limit=limit)
        return jsonify({"history": history, "count": len(history)})
    except Exception as exc:
        logger.exception("gpr history failed")
        return jsonify({"error": str(exc), "history": []}), 503


@app.get("/api/corridors")
def api_corridors():
    try:
        return jsonify(get_corridors())
    except Exception as exc:
        logger.exception("corridors failed")
        return jsonify({"error": str(exc), "date": None, "corridors": []}), 503


@app.get("/api/corridors/<corridor_id>")
def api_corridor_detail(corridor_id: str):
    start = request.args.get("start")
    end = request.args.get("end")
    try:
        limit = int(request.args.get("limit", 500))
    except ValueError:
        limit = 500
    history = get_corridor_history(corridor_id, start=start, end=end)
    if not history:
        return jsonify({"error": f"no data for corridor {corridor_id}"}), 404
    if limit and len(history) > limit:
        history = history[-limit:]
    from gpr_index.scripts.corridor_index import CORRIDOR_SCORE_DISCLAIMER
    from gpr_index.scripts.corridors import corridor_metadata

    return jsonify({
        "corridor": corridor_id,
        "disclaimer": CORRIDOR_SCORE_DISCLAIMER,
        "metadata": corridor_metadata().get(corridor_id),
        "history": history,
    })


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


@app.get("/api/news/recent")
def api_news_recent():
    return jsonify({
        "articles": get_events_feed(
            limit=int(request.args.get("limit", 50)),
            theme=request.args.get("theme"),
            tier=request.args.get("tier"),
            tagged_only=False,
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


@app.get("/api/market/quotes")
def api_market_quotes():
    raw = request.args.get("symbols", "")
    symbols = [s.strip() for s in raw.split(",") if s.strip()] or None
    try:
        payload = fetch_quotes(symbols)
        status = 200 if payload.get("quotes") else 503
        return jsonify(payload), status
    except Exception as exc:
        logger.exception("market quotes failed")
        return jsonify({"error": str(exc), "quotes": [], "errors": [str(exc)]}), 503


@app.get("/api/market/history")
def api_market_history():
    symbol = request.args.get("symbol", "nifty")
    period = request.args.get("period", "3mo")
    try:
        return jsonify(fetch_history(symbol, period=period))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        logger.exception("market history failed")
        return jsonify({"error": str(exc)}), 503


@app.get("/api/market/indicators")
def api_market_indicators():
    symbol = request.args.get("symbol", "nifty")
    try:
        return jsonify(compute_indicators(symbol))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        logger.exception("market indicators failed")
        return jsonify({"error": str(exc)}), 503


@app.get("/api/metrics/accuracy")
def api_metrics_accuracy():
    refresh_vol = request.args.get("refresh_vol", "").lower() in {"1", "true", "yes"}
    try:
        return jsonify(build_accuracy_metrics(refresh_vol=refresh_vol))
    except Exception as exc:
        logger.exception("metrics accuracy failed")
        return jsonify({"error": str(exc)}), 503


@app.get("/api/market/dual-signal")
def api_dual_signal():
    refresh = request.args.get("refresh", "").lower() in {"1", "true", "yes"}
    try:
        payload = build_dual_signal_payload(refresh=refresh)
        return jsonify(payload)
    except Exception as exc:
        logger.exception("dual-signal failed")
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(debug=True, host="127.0.0.1", port=port)
