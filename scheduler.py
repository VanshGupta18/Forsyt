"""
Real-time news scraper scheduler.
Runs scraping on a configurable interval and stores results in SQLite.
"""

import time
import logging
import signal
import sys
from datetime import datetime
from scraper import Data
from db import insert_articles, get_total_count, get_stats, cleanup_old_articles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Default: scrape every 15 minutes (900 seconds)
DEFAULT_INTERVAL = 15 * 60


def run_scrape():
    """Run a single scrape cycle across all sources."""
    logger.info("=" * 60)
    logger.info("Starting scrape cycle...")
    start = time.time()

    try:
        articles = Data.collect(source="all")
        if not articles:
            logger.warning("No articles scraped!")
            return 0

        logger.info(f"Scraped {len(articles)} articles from all sources")
        inserted = insert_articles(articles)
        elapsed = time.time() - start
        total = get_total_count()

        logger.info(f"Scrape cycle complete in {elapsed:.1f}s")
        logger.info(f"New articles: {inserted} | Total in database: {total}")
        return inserted

    except Exception as e:
        logger.error(f"Scrape cycle failed: {e}")
        import traceback
        traceback.print_exc()
        return 0


def run_realtime(interval=DEFAULT_INTERVAL):
    """Run the scraper in real-time mode (continuous loop)."""
    logger.info(f"Starting real-time scraper (interval: {interval}s / {interval//60}min)")
    logger.info("Press Ctrl+C to stop")

    # Handle graceful shutdown
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        logger.info("\nShutting down gracefully...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)

    cycle = 0
    while running:
        cycle += 1
        logger.info(f"\n--- Cycle #{cycle} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

        # Auto-cleanup: remove articles older than 7 days
        cleanup_old_articles(keep_days=7)

        run_scrape()

        # Print stats
        stats = get_stats()
        if stats:
            logger.info("Database stats:")
            for s in stats:
                lang = "Hindi" if s["language"] == "hi" else "English"
                logger.info(f"  {s['source']:6s} ({lang:7s}): {s['count']:>5d} articles")

        if not running:
            break

        logger.info(f"Next scrape in {interval // 60} minutes...")

        # Sleep in small chunks so we can respond to Ctrl+C quickly
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    logger.info("Scraper stopped.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Newsemble Scraper")
    parser.add_argument(
        "--once", action="store_true", help="Run a single scrape and exit"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Scrape interval in seconds (default: {DEFAULT_INTERVAL})",
    )
    args = parser.parse_args()

    if args.once:
        run_scrape()
    else:
        run_realtime(interval=args.interval)
