"""
Forsyt — Flask REST API.
Serves geopolitical news articles via REST endpoints.
"""

import os
import logging
from datetime import datetime

from flask import Flask, jsonify
from flask_restful import Api, Resource
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from api.utils import read_data_db
from db import get_geo_cycle_stats, get_total_count, get_geo_feed_health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
api = Api(app)


# ============================================================
# REST API Resources
# ============================================================


class News(Resource):
    def get(self, tier=None):
        if tier is not None:
            try:
                tier_val = int(tier)
                if tier_val not in [1, 2]:
                    return "Tier must be 1 or 2", 400
                return read_data_db(tier=tier_val)
            except ValueError:
                return "Invalid tier format", 400
        return read_data_db()


class Health(Resource):
    def get(self):
        total = get_total_count()
        return {
            "status": "healthy",
            "total_articles": total,
            "database": "postgresql" if os.environ.get("DATABASE_URL") else "sqlite",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


class Stats(Resource):
    def get(self):
        stats = get_geo_cycle_stats(limit=10)
        total = get_total_count()
        feed_health = get_geo_feed_health()
        
        # Ensure we return a dictionary structure suitable for JSON serialization
        formatted_health = {}
        for source, health_data in feed_health.items():
            formatted_health[source] = {
                k: (v.isoformat() if hasattr(v, 'isoformat') else v) 
                for k, v in health_data.items()
            }
            
        formatted_stats = []
        for stat in stats:
            formatted_stats.append({
                k: (v.isoformat() if hasattr(v, 'isoformat') else v)
                for k, v in stat.items()
            })

        return {
            "total_articles": total,
            "recent_cycles": formatted_stats,
            "feed_health": formatted_health
        }


api.add_resource(News, "/news", "/news/", "/news/<string:tier>")
api.add_resource(Health, "/health", "/health/")
api.add_resource(Stats, "/stats", "/stats/")


if __name__ == "__main__":
    app.run(debug=True)
