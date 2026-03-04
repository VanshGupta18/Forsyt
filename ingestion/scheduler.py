"""
APScheduler-based ingestion scheduler.
Fires run_ingestion_cycle() every 15 minutes.
"""

import logging
import time
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from ingestion.pipeline import run_ingestion_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("ingestion.scheduler")


def main():
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")

    scheduler.add_job(
        run_ingestion_cycle,
        trigger=IntervalTrigger(minutes=15),
        id="ingestion_cycle",
        name="GDELT Ingestion Cycle",
        replace_existing=True,
        max_instances=1,       # Prevent concurrent runs
        misfire_grace_time=60, # Tolerate up to 60s delay before skipping
    )

    logger.info("Ingestion scheduler started. Pulling GDELT every 15 minutes.")

    # Run once immediately at startup
    logger.info("Running initial ingestion cycle...")
    try:
        stats = run_ingestion_cycle()
        logger.info(f"Initial cycle: {stats}")
    except Exception as e:
        logger.error(f"Initial cycle failed: {e}", exc_info=True)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Ingestion scheduler stopped")


if __name__ == "__main__":
    main()
