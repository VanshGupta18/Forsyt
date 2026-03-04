"""
APScheduler-based scheduler for the daily GPR index build.
Fires at 20:30 IST every weekday (Monday–Friday).
Also triggers ML inference after GPR build completes.
"""

import logging
from datetime import date
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("gpr_index.scheduler")


def run_gpr_and_inference():
    """Runs GPR build then ML inference sequentially."""
    from gpr_index.run_daily import run_gpr_index_for_date
    from ml_inference.run_daily import run_daily_inference

    logger.info("Starting daily GPR build...")
    gpr_result = run_gpr_index_for_date()
    logger.info(f"GPR complete: {gpr_result}")

    logger.info("Triggering ML inference...")
    ml_result = run_daily_inference()
    logger.info(f"ML inference complete: {ml_result}")


def run_sector_beta_recompute():
    """Quarterly sector GPR beta recomputation."""
    import subprocess
    logger.info("Running quarterly sector beta recomputation...")
    subprocess.run(["python", "scripts/compute_sector_gpr_betas.py"], check=True)


def main():
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")

    # Daily GPR + ML inference at 20:30 IST (Mon–Fri)
    scheduler.add_job(
        run_gpr_and_inference,
        trigger=CronTrigger(day_of_week="mon-fri", hour=20, minute=30,
                            timezone="Asia/Kolkata"),
        id="daily_gpr_build",
        name="Daily GPR Index + ML Inference",
        replace_existing=True,
        max_instances=1,
    )

    # Quarterly sector beta recompute (first Monday of Jan, Apr, Jul, Oct)
    scheduler.add_job(
        run_sector_beta_recompute,
        trigger=CronTrigger(month="1,4,7,10", day="1-7", day_of_week="mon",
                            hour=22, minute=0, timezone="Asia/Kolkata"),
        id="quarterly_sector_betas",
        name="Quarterly Sector GPR Beta Recompute",
        replace_existing=True,
        max_instances=1,
    )

    logger.info("GPR index scheduler started. Daily run at 20:30 IST.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("GPR scheduler stopped")


if __name__ == "__main__":
    main()
