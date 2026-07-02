"""
Newsemble — Flask REST API with integrated background scraper.
Authors: Vishal Singhania (vishalvvs), Rishabh Gupta (rg089)

Serves news articles via REST endpoints and optionally runs a daily
scraper in a background thread (configurable via SCRAPE_INTERVAL env var).
"""

import os
import threading
import time
import logging
from datetime import datetime

from flask import Flask, jsonify
from flask_restful import Api, Resource
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from utils import read_data_db
from db import get_stats, get_total_count, insert_articles, cleanup_old_articles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
api = Api(app)

# ── Scrape interval from env (default: 86400s = 24h, set to 0 to disable) ──
SCRAPE_INTERVAL = int(os.environ.get("SCRAPE_INTERVAL", "86400"))


# ============================================================
# REST API Resources
# ============================================================


class News(Resource):
    def get(self, source="all"):
        source = source.lower()
        papers = [
            # English
            "tie", "toi", "ndtv", "it", "th",
            # Hindi
            "au", "bbc", "oi", "lh", "n18",
            "all",
        ]
        if source in papers:
            return read_data_db(source)
        s = """
        Valid sources:
        ENGLISH: TIE (Indian Express), TOI (Times of India), NDTV, IT (India Today), TH (The Hindu)
        HINDI: AU (Amar Ujala), BBC (BBC Hindi), OI (OneIndia Hindi), LH (Live Hindustan), N18 (News18 Hindi)
        ALL: All sources combined
        """
        return s, 404


class Health(Resource):
    def get(self):
        total = get_total_count()
        return {
            "status": "healthy",
            "total_articles": total,
            "database": "postgresql" if os.environ.get("DATABASE_URL") else "sqlite",
            "scraper_interval": SCRAPE_INTERVAL,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


class Stats(Resource):
    def get(self):
        stats = get_stats()
        total = get_total_count()
        return {
            "total_articles": total,
            "sources": stats,
        }


api.add_resource(News, "/news", "/news/", "/news/<string:source>")
api.add_resource(Health, "/health", "/health/")
api.add_resource(Stats, "/stats", "/stats/")


# ============================================================
# Background Scraper Thread
# ============================================================


def background_scraper():
    """Run the scraper in a background thread on a fixed interval."""
    # Import here to avoid circular imports and slow startup
    from scraper import Data

    logger.info(f"Background scraper started (interval: {SCRAPE_INTERVAL}s / {SCRAPE_INTERVAL // 3600}h)")

    # Wait 30 seconds after startup before first scrape to let the server settle
    time.sleep(30)

    while True:
        try:
            logger.info("=" * 60)
            logger.info(f"Background scrape starting at {datetime.utcnow().isoformat()}Z")
            start = time.time()

            # Cleanup old articles
            cleanup_old_articles(keep_days=7)

            # Scrape all sources
            articles = Data.collect(source="all")
            if articles:
                inserted = insert_articles(articles)
                elapsed = time.time() - start
                total = get_total_count()
                logger.info(f"Scrape complete in {elapsed:.1f}s — {inserted} new articles, {total} total")
            else:
                logger.warning("No articles scraped!")

        except Exception as e:
            logger.error(f"Background scrape failed: {e}")
            import traceback
            traceback.print_exc()

        # Sleep until the next cycle
        logger.info(f"Next scrape in {SCRAPE_INTERVAL // 3600}h {(SCRAPE_INTERVAL % 3600) // 60}m")
        time.sleep(SCRAPE_INTERVAL)


# Start the background scraper thread (only if interval > 0 and not in reloader)
if SCRAPE_INTERVAL > 0 and not os.environ.get("WERKZEUG_RUN_MAIN"):
    scraper_thread = threading.Thread(target=background_scraper, daemon=True, name="scraper")
    scraper_thread.start()
    logger.info("Background scraper thread launched")
elif SCRAPE_INTERVAL == 0:
    logger.info("Background scraper disabled (SCRAPE_INTERVAL=0)")


if __name__ == "__main__":
    app.run(debug=True)
