"""Batch NLP extraction for canonical geopolitical news articles.

Beginner note — what does "NLP extraction" mean here, end to end?
    "NLP" = Natural Language Processing, i.e. having code read text and pull
    structured information out of it. For every article, this module runs
    four independent extractors and writes their outputs onto that article's
    database row:
      - extract_themes()  (nlp/themes.py)   -> which conflict "themes" apply
                                                (e.g. ARMEDCONFLICT), using AI
                                                embeddings
      - extract_tone()    (nlp/tone.py)     -> how negative/emotionally
                                                charged the wording is, using
                                                simple word-list counting
      - extract_gcam()    (nlp/tone.py)     -> a GDELT-style breakdown of
                                                which KIND of conflict
                                                language appears
      - extract_locations() (nlp/locations.py) -> which countries/places are
                                                mentioned
    run() below is the loop that fetches a batch of un-tagged articles from
    Postgres, calls all four extractors on each one, and saves the results —
    this is what nlp/scheduler.py runs hourly in production.
"""

import argparse
import logging
from datetime import date, datetime, time, timedelta, timezone

from news_dataset.db import count_articles_pending_nlp, get_articles_pending_nlp, update_article_nlp
from news_dataset.nlp.locations import extract_locations
from news_dataset.nlp.version import EXTRACTOR_VERSION
from news_dataset.nlp.themes import extract_themes
from news_dataset.nlp.tone import extract_gcam, extract_tone


NLP_MODEL_VERSION = EXTRACTOR_VERSION

logger = logging.getLogger(__name__)


def _day(value):
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


def _date_bounds(args):
    if args.date:
        start = datetime.combine(args.date, time.min, tzinfo=timezone.utc)
        return start, start + timedelta(days=1)
    start = (
        datetime.combine(args.start, time.min, tzinfo=timezone.utc)
        if args.start
        else None
    )
    end = (
        datetime.combine(
            args.end + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )
        if args.end
        else None
    )
    return start, end


def run(limit=500, start=None, end=None, reprocess=False, until_empty=False):
    """Fetch a batch of articles missing NLP tags, run the 4 extractors, save results.

    Beginner walk-through of one batch:
      1. Ask the database for up to `limit` articles that either have never
         been tagged, or were tagged by an older version of the extractors
         (see nlp/version.py's EXTRACTOR_VERSION) — unless `reprocess=True`,
         which re-tags everything regardless of version.
      2. For each article, combine title+content into one text blob and run
         all four extractors on it (see module docstring above).
      3. Save the results back onto that article's row via update_article_nlp().
      4. If `until_empty=True`, keep repeating steps 1-3 with fresh batches
         until nothing is left pending (used by one-off backfill scripts);
         otherwise stop after one batch (used by the hourly cron job).
    A single article failing (e.g. a weird encoding) is caught and logged,
    not allowed to crash the whole batch.
    """
    total_updated = total_failed = 0
    while True:
        articles = get_articles_pending_nlp(
            limit=limit,
            model_version=NLP_MODEL_VERSION,
            start=start,
            end=end,
            reprocess=reprocess,
        )
        if not articles:
            break
        updated = failed = 0
        for article in articles:
            try:
                title = article["title"] or ""
                body = article["content"] or ""
                text = f"{title}\n{body}".strip()
                tone_neg, tone_polarity = extract_tone(text)
                update_article_nlp(
                    article["id"],
                    {
                        "nlp_themes": ";".join(extract_themes(title, body)),
                        "nlp_tone_neg": tone_neg,
                        "nlp_tone_polarity": tone_polarity,
                        "nlp_gcam": extract_gcam(text),
                        "nlp_locations": extract_locations(title, body),
                        "nlp_model_version": NLP_MODEL_VERSION,
                        "nlp_extracted_at": datetime.now(timezone.utc),
                    },
                )
                updated += 1
            except Exception:
                failed += 1
                logger.exception("NLP extraction failed for article %s", article["id"])
        total_updated += updated
        total_failed += failed
        logger.info("batch: %s updated, %s failed (running total %s/%s)", updated, failed, total_updated, total_failed)
        if not until_empty:
            break
        pending = count_articles_pending_nlp(NLP_MODEL_VERSION, start=start, end=end, reprocess=reprocess)
        logger.info("pending NLP articles: %s", pending)
        if pending == 0 or updated == 0:
            break
    return total_updated, total_failed


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=_day, help="process one UTC day (YYYY-MM-DD)")
    parser.add_argument("--start", type=_day, help="first UTC day to process")
    parser.add_argument("--end", type=_day, help="last UTC day to process, inclusive")
    parser.add_argument("--limit", type=int, default=500, help="maximum rows per batch (default: 500)")
    parser.add_argument(
        "--until-empty",
        action="store_true",
        help="repeat batches until no tier articles remain pending NLP",
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="include rows already extracted with the current model version",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.date and (args.start or args.end):
        parser.error("--date cannot be combined with --start or --end")
    if args.start and args.end and args.start > args.end:
        parser.error("--start cannot be after --end")
    if args.limit <= 0:
        parser.error("--limit must be positive")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    start, end = _date_bounds(args)
    updated, failed = run(
        limit=args.limit,
        start=start,
        end=end,
        reprocess=args.reprocess,
        until_empty=args.until_empty,
    )
    logger.info("NLP extraction complete: %s updated, %s failed", updated, failed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
