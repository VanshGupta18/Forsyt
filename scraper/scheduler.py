"""Async scraper scheduler — 5-min continuous loop.

Each cycle:
  1. For every outlet: fetch RSS in parallel → gather article URLs + metadata
  2. For every URL: fetch article HTML in parallel (per-host semaphore)
  3. For NDTV: content already in RSS, no article fetch
  4. Insert new articles into SQLite (scraper.db)
  5. Call export_news_db.export_day() to append to today's JSONL

Run as:
  python -m scraper schedule [--interval 300]
  python -m scraper once
"""

from __future__ import annotations

import asyncio
import logging
import signal
import time
from typing import Optional

from .db import cleanup_old_articles, get_stats, get_total_count, init_db, insert_articles
from .fetcher import make_session
from .outlets import all_outlets

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL = 5 * 60  # 300 s


async def _run_cycle_async() -> int:
    """One full async scrape cycle. Returns number of new articles inserted."""
    outlets = all_outlets()

    async with make_session() as session:
        # Step 1: fetch all RSS feeds in parallel
        rss_results: list[list[dict]] = await asyncio.gather(
            *[outlet.fetch_rss(session) for outlet in outlets],
            return_exceptions=True,
        )

        # Step 2: build parse tasks
        parse_tasks = []
        task_meta   = []   # (outlet, rss_item)
        for outlet, rss_items in zip(outlets, rss_results):
            if isinstance(rss_items, Exception):
                logger.warning(f"[{outlet.code}] RSS error: {rss_items}")
                continue
            for item in rss_items:
                url = item.get("link", "")
                if not url:
                    continue
                # NDTV: content already in RSS — parse() with rss_meta skips HTML fetch
                if outlet.code == "NDTV":
                    parse_tasks.append(outlet.parse(url=url, rss_meta=item))
                else:
                    parse_tasks.append(outlet.parse(url=url, session=session, rss_meta=item))
                task_meta.append(outlet.code)

        if not parse_tasks:
            return 0

        # Step 3: execute all parse tasks concurrently
        parsed: list = await asyncio.gather(*parse_tasks, return_exceptions=True)

    articles = []
    for result, code in zip(parsed, task_meta):
        if isinstance(result, Exception):
            logger.debug(f"[{code}] parse error: {result}")
            continue
        if result and result.get("title") and result.get("content"):
            articles.append(result)

    inserted = insert_articles(articles) if articles else 0
    return inserted


def run_cycle() -> int:
    """Sync wrapper around the async cycle (for use from non-async contexts)."""
    return asyncio.run(_run_cycle_async())


def _export_today() -> None:
    """Call export_news_db.export_day() — JSONL append, idempotent."""
    try:
        from scripts.export_news_db import export_day  # noqa: PLC0415
        count = export_day(date_str=None)
        if count:
            logger.info(f"[export] {count} new articles appended to india_raw/")
    except Exception as exc:
        logger.error(f"[export] JSONL export failed: {exc}")


async def _continuous_loop(interval: int) -> None:
    logger.info(f"Scraper starting — interval={interval}s / {interval//60}min")
    init_db()

    running = True

    def _stop(sig, frame):  # noqa: ANN001
        nonlocal running
        logger.info("Shutdown signal received …")
        running = False

    signal.signal(signal.SIGINT,  _stop)
    signal.signal(signal.SIGTERM, _stop)

    cycle = 0
    while running:
        cycle += 1
        cycle_start = time.monotonic()
        logger.info(f"\n{'='*50}\nCycle #{cycle}")

        # Cleanup 7-day rolling window
        cleanup_old_articles(keep_days=7)

        # Scrape
        inserted = await _run_cycle_async()
        total = get_total_count()
        elapsed = time.monotonic() - cycle_start
        logger.info(f"Cycle #{cycle}: {inserted} new, {total} total ({elapsed:.1f}s)")

        # Print per-source stats
        for s in get_stats():
            lang = "Hindi" if s["language"] == "hi" else "English"
            logger.info(f"  {s['source']:6s} ({lang:7s}): {s['count']:>5d}")

        # Export to JSONL
        _export_today()

        if not running:
            break

        # Sleep in 1-second ticks so SIGINT is responsive
        sleep_remaining = interval - (time.monotonic() - cycle_start)
        logger.info(f"Next cycle in {max(sleep_remaining, 0):.0f}s …")
        deadline = time.monotonic() + max(sleep_remaining, 0)
        while running and time.monotonic() < deadline:
            await asyncio.sleep(1)

    logger.info("Scraper stopped.")


def run_continuous(interval: int = DEFAULT_INTERVAL) -> None:
    asyncio.run(_continuous_loop(interval))


def run_once() -> None:
    init_db()
    cleanup_old_articles(keep_days=7)
    inserted = run_cycle()
    total = get_total_count()
    logger.info(f"Single cycle: {inserted} new articles, {total} total in DB")
    _export_today()
