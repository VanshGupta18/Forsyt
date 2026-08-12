"""
Scheduler for batch NLP extraction on scraped geo articles.

Designed for the same stateless cron pattern as geo_scheduler:
  python -m news_dataset.nlp.scheduler --once

Each --once invocation processes one batch of pending rows (default 200).
Run hourly via GitHub Actions so new scrape rows get themes/locations within
a few hours instead of waiting for the nightly daily_index job.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from news_dataset.db import (  # noqa: E402
    count_articles_pending_nlp,
    get_last_pipeline_run,
    log_pipeline_run,
)
from news_dataset.nlp.run_extraction import NLP_MODEL_VERSION, run as run_nlp  # noqa: E402

logger = logging.getLogger(__name__)

STAGE = "nlp_scheduler"
DEFAULT_INTERVAL = int(os.environ.get("NLP_SCHEDULER_INTERVAL_SECONDS", "3600"))
DEFAULT_BATCH = int(os.environ.get("NLP_SCHEDULER_BATCH_SIZE", "200"))
POLL_TICK = 300  # continuous mode: check every 5 minutes


def _parse_ts(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def scheduler_due(now, last_run_at, interval_seconds):
    if last_run_at is None:
        return True
    return (now - last_run_at) >= timedelta(seconds=interval_seconds)


def run_cycle(*, once=False, force=False, batch_size=DEFAULT_BATCH, until_empty=False):
    """Process pending NLP rows when due. Returns a summary dict."""
    now = datetime.now(timezone.utc)

    if not once and not force:
        last = get_last_pipeline_run(STAGE)
        last_at = _parse_ts(last["run_at"]) if last else None
        if not scheduler_due(now, last_at, DEFAULT_INTERVAL):
            logger.info("nlp_scheduler: not due yet (last run %s)", last_at)
            return {
                "due": False,
                "pending": count_articles_pending_nlp(NLP_MODEL_VERSION),
                "updated": 0,
                "failed": 0,
            }

    pending = count_articles_pending_nlp(NLP_MODEL_VERSION)
    if pending == 0:
        logger.info("nlp_scheduler: no pending articles")
        log_pipeline_run(STAGE, "skipped", {"pending": 0, "reason": "nothing pending"})
        return {"due": True, "pending": 0, "updated": 0, "failed": 0}

    logger.info(
        "nlp_scheduler: %s pending; processing batch up to %s (until_empty=%s)",
        pending,
        batch_size,
        until_empty,
    )
    updated, failed = run_nlp(limit=batch_size, until_empty=until_empty)
    remaining = count_articles_pending_nlp(NLP_MODEL_VERSION)
    status = "ok" if failed == 0 else "partial"
    log_pipeline_run(
        STAGE,
        status,
        {
            "pending_before": pending,
            "updated": updated,
            "failed": failed,
            "remaining": remaining,
            "until_empty": until_empty,
            "model_version": NLP_MODEL_VERSION,
        },
    )
    logger.info(
        "nlp_scheduler: %s updated, %s failed, %s still pending",
        updated,
        failed,
        remaining,
    )
    return {
        "due": True,
        "pending": pending,
        "updated": updated,
        "failed": failed,
        "remaining": remaining,
    }


def run_continuous():
    logger.info(
        "Starting NLP scheduler (interval %ss, batch %s, poll every %ss)",
        DEFAULT_INTERVAL,
        DEFAULT_BATCH,
        POLL_TICK,
    )
    running = True

    def _stop(sig, frame):
        nonlocal running
        logger.info("Shutting down gracefully...")
        running = False

    signal.signal(signal.SIGINT, _stop)

    while running:
        try:
            run_cycle()
        except Exception:
            logger.exception("nlp_scheduler: cycle failed")
        for _ in range(POLL_TICK):
            if not running:
                break
            time.sleep(1)

    logger.info("nlp_scheduler stopped.")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once",
        action="store_true",
        help="run one batch if anything is pending and exit (for cron)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="ignore interval gate in continuous mode",
    )
    parser.add_argument(
        "--until-empty",
        action="store_true",
        help="repeat batches until pending queue is empty",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_BATCH,
        help=f"rows per batch (default: {DEFAULT_BATCH})",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error("--limit must be positive")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if args.once or args.force or args.until_empty:
        summary = run_cycle(
            once=args.once,
            force=args.force,
            batch_size=args.limit,
            until_empty=args.until_empty,
        )
        return 1 if summary.get("failed") else 0

    run_continuous()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
