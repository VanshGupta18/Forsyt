"""
Forsyt — Flask REST API for geopolitical news articles.
"""

import logging
from datetime import datetime

from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from db import get_geo_articles, get_geo_cycle_stats, get_geo_feed_health, get_total_count

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


def _serialize_rows(rows):
    out = []
    for row in rows:
        out.append({
            key: (value.isoformat() if hasattr(value, "isoformat") else value)
            for key, value in row.items()
        })
    return out


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
    return jsonify({
        "status": "healthy",
        "total_articles": get_total_count(),
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


if __name__ == "__main__":
    app.run(debug=True)
