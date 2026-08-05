"""
Scheduler for the Indian geopolitical/defence/foreign-policy RSS pipeline.

Each invocation checks which tier(s) are due (Tier 1 every 5-10 min, Tier 2
every 10-15 min — tracked via per-feed last-attempt timestamps in the DB) and
only fetches those. This lets a single `--once` call be driven by a fixed-rate
cron (e.g. every 5 minutes) while still respecting each tier's own cadence —
the same stateless-invocation pattern scheduler.py/GitHub Actions already use
for the main scraper.
"""

import time
import signal
import logging
from datetime import datetime, timedelta, timezone

try:
    from news_dataset.ingestion.geo_pipeline import (
        TIER1_FEEDS, TIER2_FEEDS, FEEDS_BY_CODE, TIER_INTERVALS,
        fetch_tier, find_duplicate, DEDUP_WINDOW,
    )
    from news_dataset.db import (
        insert_geo_article, get_recent_geo_articles, upsert_geo_feed_health,
        get_geo_feed_health, log_geo_cycle_stats, record_geo_seen_links,
    )
except ModuleNotFoundError as exc:
    if exc.name != "news_dataset":
        raise
    from ingestion.geo_pipeline import (
        TIER1_FEEDS, TIER2_FEEDS, FEEDS_BY_CODE, TIER_INTERVALS,
        fetch_tier, find_duplicate, DEDUP_WINDOW,
    )
    from db import (
        insert_geo_article, get_recent_geo_articles, upsert_geo_feed_health,
        get_geo_feed_health, log_geo_cycle_stats, record_geo_seen_links,
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

POLL_TICK = 60  # continuous-mode check interval; actual tier cadence enforced via tier_due()


def _parse_ts(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def tier_due(tier, health, now):
    """A tier is due if any of its feeds hasn't been attempted within its interval."""
    interval = TIER_INTERVALS[tier]
    feeds = TIER1_FEEDS if tier == 1 else TIER2_FEEDS
    for f in feeds:
        h = health.get(f["source_code"])
        last_attempt = _parse_ts(h.get("last_attempt")) if h else None
        if last_attempt is None or (now - last_attempt) >= timedelta(seconds=interval):
            return True
    return False


def stale_feeds(health, now):
    """Feeds with no successful fetch in 2x their tier's polling interval."""
    stale = []
    for code, feed_cfg in FEEDS_BY_CODE.items():
        interval = TIER_INTERVALS[feed_cfg["tier"]]
        h = health.get(code)
        last_success = _parse_ts(h.get("last_success")) if h else None
        if last_success is None or (now - last_success) > timedelta(seconds=2 * interval):
            stale.append(code)
    return stale


def run_cycle(force_tiers=None):
    """Fetch due tiers, filter, dedup, ingest, and log stats. Returns summary dict."""
    now = datetime.now(timezone.utc)
    health = get_geo_feed_health()
    due_tiers = force_tiers or [t for t in (1, 2) if tier_due(t, health, now)]

    if not due_tiers:
        logger.info("geo_scheduler: no tier due yet")
        return {"due_tiers": [], "ingested": 0, "fetched": 0}

    logger.info(f"geo_scheduler: cycle starting for tier(s) {due_tiers}")

    per_source_stats = {}
    all_candidates = []
    all_seen = []

    for tier in due_tiers:
        results = fetch_tier(tier)
        for source_code, (candidates, seen, fetched_count, error) in results.items():
            upsert_geo_feed_health(source_code, success=(error is None), error=error, now=now)
            discarded = fetched_count - len(candidates)
            per_source_stats[source_code] = {
                "tier": tier, "fetched": fetched_count, "ingested": 0, "discarded": discarded,
            }
            all_candidates.extend(candidates)
            all_seen.extend(seen)

    record_geo_seen_links(all_seen, now)

    # Earliest-first so the first occurrence of a story becomes canonical.
    all_candidates.sort(key=lambda c: c["published_at"] or now)

    total_ingested = 0
    total_duplicates = 0

    for candidate in all_candidates:
        published_dt = candidate["published_at"] or now
        since = published_dt - DEDUP_WINDOW
        recent = get_recent_geo_articles(since)
        dup_id = find_duplicate(candidate["title"], published_dt, recent)

        new_id = insert_geo_article({
            "source": candidate["source"],
            "source_code": candidate["source_code"],
            "tier": candidate["tier"],
            "confidence": candidate["confidence"],
            "matched_keywords": candidate["matched_keywords"],
            "title": candidate["title"],
            "link": candidate["link"],
            "published_at": candidate["published_at"],
            "published_at_raw": candidate.get("published_at_raw", ""),
            "ingested_at": now,
            "description": candidate["description"],
            "duplicate_of": dup_id,
        })

        per_source_stats[candidate["source_code"]]["ingested"] += 1
        total_ingested += 1
        if dup_id is not None:
            total_duplicates += 1
        if new_id is None:
            logger.debug(f"geo_scheduler: link already ingested, skipped insert: {candidate['link']}")

    for source_code, s in per_source_stats.items():
        log_geo_cycle_stats(now, s["tier"], source_code, s["fetched"], s["ingested"], s["discarded"])

    total_fetched = sum(s["fetched"] for s in per_source_stats.values())
    overall_yield = (total_ingested / total_fetched * 100) if total_fetched else 0.0

    logger.info("Per-source yield (fetched / ingested / discarded):")
    for source_code in sorted(per_source_stats):
        s = per_source_stats[source_code]
        y = (s["ingested"] / s["fetched"] * 100) if s["fetched"] else 0.0
        logger.info(
            f"  [T{s['tier']}] {source_code:6s}: {s['fetched']:>4d} fetched, "
            f"{s['ingested']:>4d} ingested, {s['discarded']:>4d} discarded ({y:.0f}% yield)"
        )
    logger.info(
        f"Cycle totals: {total_fetched} fetched, {total_ingested} ingested "
        f"({overall_yield:.1f}% yield), {total_duplicates} fuzzy duplicates flagged"
    )

    fresh_health = get_geo_feed_health()
    stale = stale_feeds(fresh_health, now)
    if stale:
        logger.warning(f"STALE FEEDS (no success in 2x poll interval): {', '.join(stale)}")

    return {
        "due_tiers": due_tiers,
        "fetched": total_fetched,
        "ingested": total_ingested,
        "duplicates": total_duplicates,
        "yield_pct": overall_yield,
        "stale_feeds": stale,
        "per_source": per_source_stats,
    }


def run_continuous():
    logger.info(
        f"Starting geo pipeline scheduler (Tier 1 ~{TIER_INTERVALS[1]//60}min, "
        f"Tier 2 ~{TIER_INTERVALS[2]//60}min, checked every {POLL_TICK}s)"
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
            logger.exception("geo_scheduler: cycle failed")
        for _ in range(POLL_TICK):
            if not running:
                break
            time.sleep(1)

    logger.info("geo_scheduler stopped.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Indian geopolitics RSS ingestion scheduler")
    parser.add_argument("--once", action="store_true", help="Run a single due-tier cycle and exit")
    parser.add_argument("--tier1", action="store_true", help="Force-fetch Tier 1 regardless of cadence")
    parser.add_argument("--tier2", action="store_true", help="Force-fetch Tier 2 regardless of cadence")
    args = parser.parse_args()

    forced = [t for t, flag in ((1, args.tier1), (2, args.tier2)) if flag] or None

    if args.once or forced:
        run_cycle(force_tiers=forced)
    else:
        run_continuous()
