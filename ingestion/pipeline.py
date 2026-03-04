"""
Ingestion pipeline orchestrator.
Combines: GDELT pull → clean → dedup → FinBERT → GPT → PostgreSQL insert.
Called every 15 minutes by scheduler.py.
"""

import os
import json
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime
from typing import Dict

from ingestion.gdelt_puller import fetch_gdelt_articles, fetch_article_text
from ingestion.cleaner import clean_article, extract_headline
from ingestion.deduplicator import should_process
from extraction.finbert_classifier import should_extract
from extraction.gpt_extractor import extract_event, PROMPT_VERSION

logger = logging.getLogger(__name__)


def _get_db_conn():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"]
    )


def run_ingestion_cycle(minutes_back: int = 20) -> Dict:
    """
    Full ingestion cycle:
    1. Fetch URLs from GDELT
    2. For each URL: fetch HTML → clean → dedup → FinBERT → GPT → insert

    Returns stats dict for monitoring.
    """
    stats = {
        "articles_fetched":    0,
        "after_url_dedup":     0,
        "after_minhash_dedup": 0,
        "finbert_passed":      0,
        "events_extracted":    0,
        "dlq_failures":        0,
        "errors":              0,
    }

    logger.info(f"=== Ingestion cycle starting (last {minutes_back} min) ===")

    # Step 1: Get article URLs from GDELT
    articles = fetch_gdelt_articles(minutes_back=minutes_back)
    stats["articles_fetched"] = len(articles)
    logger.info(f"GDELT: {len(articles)} articles fetched")

    if not articles:
        logger.warning("No articles from GDELT — API may be down or no India news in window")
        return stats

    conn = _get_db_conn()
    cur  = conn.cursor()

    for art in articles:
        url      = art["url"]
        url_hash = art["url_hash"]

        try:
            # Step 2: Layer-1 URL dedup (fast, no HTML fetch yet)
            # We do a lightweight check here — deduplicator.should_process also does layer 2
            from ingestion.deduplicator import is_duplicate_url
            if is_duplicate_url(url_hash):
                continue
            stats["after_url_dedup"] += 1

            # Step 3: Fetch article HTML
            raw_text = fetch_article_text(url)
            if not raw_text:
                continue

            # Step 4: Clean
            clean_text = clean_article(raw_text)
            if not clean_text:
                continue

            # Step 5: Layer-2 near-duplicate check
            from ingestion.deduplicator import is_near_duplicate
            if is_near_duplicate(url_hash, clean_text):
                continue
            stats["after_minhash_dedup"] += 1

            # Insert raw article to PostgreSQL
            headline = art.get("headline") or extract_headline(raw_text) or ""
            cur.execute("""
                INSERT INTO raw_articles
                    (url_hash, url, headline, body_text, source_domain, publish_ts, gdelt_event_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url_hash) DO NOTHING
                RETURNING id
            """, (
                url_hash,
                url[:2048],
                headline[:500],
                clean_text,
                art.get("source_domain", ""),
                art.get("publish_ts"),
                art.get("gdelt_event_id", ""),
            ))
            result = cur.fetchone()
            if result is None:
                # Conflict — already in DB
                continue
            article_id = result[0]

            # Step 6: FinBERT Stage 1 filter
            proceed, finbert_label, finbert_conf = should_extract(clean_text)
            if not proceed:
                logger.debug(f"FinBERT rejected: {finbert_label} ({finbert_conf:.2f}) | {url[:60]}")
                continue
            stats["finbert_passed"] += 1

            # Step 7: GPT-4o-mini Stage 2 extraction
            event = extract_event(clean_text, article_id=article_id)

            if event is None:
                # Route to dead letter queue
                cur.execute("""
                    INSERT INTO dead_letter_queue (raw_article_id, failure_reason, retry_count)
                    VALUES (%s, 'GPT extraction failed after 3 retries', 0)
                """, (article_id,))
                stats["dlq_failures"] += 1
                logger.warning(f"Article {article_id} → DLQ (GPT failure)")
            else:
                # Insert structured event
                from datetime import date
                cur.execute("""
                    INSERT INTO structured_events
                        (raw_article_id, event_type, severity, india_exposure, confidence,
                         actors, locations, event_date, prompt_version, finbert_label)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s)
                """, (
                    article_id,
                    event.event_type,
                    event.severity,
                    event.india_exposure,
                    event.confidence,
                    json.dumps(event.actors),
                    json.dumps(event.locations),
                    art.get("publish_ts", str(date.today()))[:10],
                    PROMPT_VERSION,
                    finbert_label,
                ))
                stats["events_extracted"] += 1

            conn.commit()

        except Exception as e:
            conn.rollback()
            stats["errors"] += 1
            logger.error(f"Error processing {url[:60]}: {e}", exc_info=True)

    conn.close()

    logger.info(
        f"=== Cycle complete: fetched={stats['articles_fetched']} "
        f"deduped={stats['after_minhash_dedup']} "
        f"finbert_pass={stats['finbert_passed']} "
        f"extracted={stats['events_extracted']} "
        f"dlq={stats['dlq_failures']} errors={stats['errors']} ==="
    )
    return stats
