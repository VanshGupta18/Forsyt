"""
Forsyt — unified REST API for geopolitical risk intelligence.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NEWS_DATASET = REPO_ROOT / "news_dataset"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from flask import Flask, jsonify, request, send_from_directory
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
    serialize_rows,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DASHBOARD_DIR = REPO_ROOT / "dashboard"

app = Flask(__name__)
CORS(app)


def _serialize_rows(rows):
    return serialize_rows(rows)




@app.get("/")
def root():
    return jsonify({
        "service": "forsyt-api",
        "legacy_dashboard": "/legacy",
        "frontend_dev": "cd frontend && npm run dev",
    })

@app.get("/legacy")
@app.get("/legacy/")
def legacy_dashboard_home():
    """Static product dashboard (HTML/JS); React UI lives in frontend/."""
    return send_from_directory(DASHBOARD_DIR, "index.html")


@app.get("/legacy/<path:filename>")
def legacy_dashboard_assets(filename: str):
    return send_from_directory(DASHBOARD_DIR, filename)


@app.get("/dashboard/<path:filename>")
def dashboard_assets(filename: str):
    return send_from_directory(DASHBOARD_DIR, filename)


@app.get("/news")
@app.get("/news/")
def news_all():
    return _serialize_rows(get_geo_articles())


@app.get("/news/<tier>")
def news_by_tier(tier: str):
    try:
        tier_val = int(tier)
    except ValueError:
        return "Invalid tier format", 400
    if tier_val not in (1, 2):
        return "Tier must be 1 or 2", 400
    return _serialize_rows(get_geo_articles(tier=tier_val))


@app.get("/health")
@app.get("/health/")
def health():
    news = get_news_stats()
    return jsonify({
        "status": "healthy",
        **news,
        "database": "postgresql",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


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
        "recent_cycles": _serialize_rows(get_geo_cycle_stats(limit=10)),
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
    limit = int(request.args.get("limit", 500))
    return jsonify({"history": get_gpr_history(start=start, end=end, limit=limit)})


@app.get("/api/corridors")
def api_corridors():
    return jsonify(get_corridors())


@app.get("/api/corridors/<corridor_id>")
def api_corridor_detail(corridor_id: str):
    start = request.args.get("start")
    end = request.args.get("end")
    history = get_corridor_history(corridor_id, start=start, end=end)
    if not history:
        return jsonify({"error": f"no data for corridor {corridor_id}"}), 404
    return jsonify({"corridor": corridor_id, "history": history})


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
    app.run(debug=True)
