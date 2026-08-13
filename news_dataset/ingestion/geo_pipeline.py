"""
Indian geopolitical / defence / foreign-policy RSS ingestion pipeline.

Polls two tiers of feeds:
  Tier 1 — dedicated geopolitics/defence sources: ingested unfiltered.
  Tier 2 — mainstream general-news sources: ingested only when title+description
           match the geopolitics keyword list.

Fuzzy title dedup (SequenceMatcher ratio >= DEDUP_THRESHOLD) within a rolling
time window keeps the earliest instance of a story as canonical and tags
later instances with duplicate_of=<canonical id>, so they can be excluded
from "final dataset" reads while remaining in the table for auditability.
"""

import html
import re
import sys
import logging
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from news_dataset.ingestion.feed_utils import parse_feed, parse_rss_time

logger = logging.getLogger(__name__)

# ============================================================
# Feed configuration
# ============================================================

TIER1_FEEDS = [
    {"source": "StratNews Global", "source_code": "SNG", "url": "https://stratnewsglobal.com/feed/"},
    {"source": "Bharat Shakti", "source_code": "BS", "url": "https://bharatshakti.in/feed/"},
    {"source": "Gateway House", "source_code": "GH",
     "url": "https://www.gatewayhouse.in/feed/",
     "urls": [
         "https://www.gatewayhouse.in/feed/",
         "https://www.gatewayhouse.in/feed/rss/",
         "https://gatewayhouse.in/feed/",
     ]},
    {"source": "ThePrint Defence", "source_code": "TPD", "url": "https://theprint.in/category/defence/feed/"},
]

TIER2_FEEDS = [
    # Each outlet's World/International section is used instead of its general
    # homepage feed — same 5 outlets as requested, but pre-narrowed to the
    # section where geopolitics/defence keyword matches are denser than on the
    # celebrity/sports/lifestyle-heavy homepage. Measured combined yield across
    # all 9 feeds went from 17% to ~29% in a live test run — still short of the
    # 60-90% target because these section feeds return ~20-200 entries per full
    # snapshot pull against only ~60 Tier-1 items; see scheduler discussion.
    {"source": "India Today", "source_code": "IT", "url": "https://www.indiatoday.in/rss/1206577"},
    # thehindu.com/latest-news/feeder is frozen on The Hindu's side (mostly stale
    # 2023 entries) — same issue scraper.py's TheHindu class already worked around.
    # The /news/international/ feeder is live and world/defence-focused.
    {"source": "The Hindu", "source_code": "TH", "url": "https://www.thehindu.com/news/international/feeder/default.rss"},
    # TOI's own "World"/"Rest of World" category feeds (296589292.cms / 671314.cms)
    # are mislabeled on TOI's side — they serve generic trivia/lifestyle content,
    # not world news — so TOI stays on its homepage top-stories feed and leans
    # more on the keyword filter than the other four Tier 2 sources.
    {"source": "Times of India", "source_code": "TOI", "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"},
    {"source": "NDTV", "source_code": "NDTV", "url": "https://feeds.feedburner.com/ndtvnews-world-news"},
    # Indian Express ("TIE") replaced 2026-08-13: its feed returns a well-formed
    # but empty <rss> specifically to GitHub Actions' shared runner IPs (CDN/WAF
    # bot-block, not a dead feed — works fine from non-CI IPs). Hindustan Times'
    # world feed verified working with 100 entries/cycle, ~8% keyword yield.
    {"source": "Hindustan Times", "source_code": "HT", "url": "https://www.hindustantimes.com/feeds/rss/world-news/rssfeed.xml"},
]

FEEDS_BY_CODE = {f["source_code"]: dict(f, tier=1) for f in TIER1_FEEDS}
FEEDS_BY_CODE.update({f["source_code"]: dict(f, tier=2) for f in TIER2_FEEDS})

# Poll intervals in seconds (midpoints of the requested ranges)
TIER1_INTERVAL = 7 * 60    # every 5-10 min
TIER2_INTERVAL = 12 * 60   # every 10-15 min

TIER_INTERVALS = {1: TIER1_INTERVAL, 2: TIER2_INTERVAL}

# ============================================================
# Keyword filter (Tier 2)
# ============================================================

KEYWORDS = [
    "border", "LAC", "LoC", "China", "Pakistan", "defence ministry", "army", "navy", "air force",
    "missile", "drone strike", "foreign policy", "diplomatic", "embassy", "sanctions", "Quad",
    "SCO", "terrorism", "cross-border", "ceasefire", "bilateral", "MEA", "S-400", "Agni", "BrahMos",
    "national security", "intelligence agency", "RAW", "ISI", "geopolitics", "insurgency",
    "defence deal", "arms deal", "military exercise", "naval exercise", "airspace violation",
    "nuclear", "strategic partnership", "UNSC", "G20", "bilateral talks", "foreign minister",
    "external affairs",
]

_KEYWORD_PATTERNS = [(kw, re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)) for kw in KEYWORDS]

DEDUP_THRESHOLD = 0.85
DEDUP_WINDOW = timedelta(hours=2)


def match_keywords(text):
    """Return the list of keywords (original casing from the list) found in text."""
    if not text:
        return []
    return [kw for kw, pattern in _KEYWORD_PATTERNS if pattern.search(text)]


# ============================================================
# Feed fetching
# ============================================================


def _clean_html(text):
    if not text:
        return ""
    plain = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", plain).strip()


def _entry_description(entry):
    if hasattr(entry, "summary"):
        return _clean_html(entry.summary)
    if hasattr(entry, "description"):
        return _clean_html(entry.description)
    return ""


def _entry_published_dt(entry):
    """Return a timezone-aware UTC datetime for the entry, or None."""
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def fetch_feed(feed_cfg, tier):
    """Fetch one RSS feed and return (candidates, seen, fetched_count, error).

    candidates: list of article dicts (schema fields except id/duplicate_of),
    already keyword-filtered for tier 2. seen contains every valid RSS entry
    before filtering. error is None on success.
    """
    source_code = feed_cfg["source_code"]
    candidates = []
    seen = []
    urls = feed_cfg.get("urls") or [feed_cfg["url"]]
    feed = None
    fetched_count = 0
    last_error = None
    for url in urls:
        try:
            feed = parse_feed(url)
            entries = feed.entries or []
            if entries:
                fetched_count = len(entries)
                break
            last_error = feed.bozo_exception if feed.bozo else "no entries"
        except Exception as e:
            last_error = str(e)
            logger.debug("geo_pipeline: %s feed %s failed: %s", source_code, url, e)
    else:
        logger.info(
            "geo_pipeline: no entries from %s after trying %d feed URL(s): %s",
            source_code, len(urls), last_error,
        )
        return [], [], 0, str(last_error) if last_error else "no entries"

    entries = feed.entries or []

    for entry in entries:
        try:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if not title or not link:
                continue

            published_dt = _entry_published_dt(entry)
            seen.append({
                "link": link,
                "source_code": source_code,
                "tier": tier,
                "published_at": published_dt,
            })

            description = _entry_description(entry)
            matched = []

            if tier == 2:
                matched = match_keywords(f"{title} {description}")
                if not matched:
                    continue

            rss_time = parse_rss_time(entry)

            candidates.append({
                "source": feed_cfg["source"],
                "source_code": source_code,
                "tier": tier,
                "confidence": "high" if tier == 1 else "filtered_match",
                "matched_keywords": matched,
                "title": title,
                "link": link,
                "published_at": published_dt,
                "published_at_raw": rss_time,
                "description": description,
            })
        except Exception as e:
            logger.warning(f"geo_pipeline: error processing entry from {source_code}: {e}")
            continue

    return candidates, seen, fetched_count, None


def fetch_tier(tier):
    """Return source_code -> (candidates, seen, fetched_count, error)."""
    feeds = TIER1_FEEDS if tier == 1 else TIER2_FEEDS
    results = {}
    for feed_cfg in feeds:
        results[feed_cfg["source_code"]] = fetch_feed(feed_cfg, tier)
    return results


# ============================================================
# Dedup
# ============================================================


def _title_similarity(a, b):
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def find_duplicate(candidate_title, candidate_published_dt, recent_articles):
    """Return the id of the earliest matching article within the dedup window, or None.

    recent_articles: iterable of dicts with 'id', 'title', 'published_at' (already
    filtered to duplicate_of IS NULL / canonical entries), sorted ascending by
    published_at so the first match found is the earliest (canonical) one.
    """
    if candidate_published_dt is None:
        return None

    for existing in recent_articles:
        existing_published = existing.get("published_at")
        if existing_published is None:
            continue
        if isinstance(existing_published, str):
            try:
                existing_published = datetime.fromisoformat(existing_published)
            except ValueError:
                continue
        if existing_published.tzinfo is None:
            existing_published = existing_published.replace(tzinfo=timezone.utc)

        if abs(candidate_published_dt - existing_published) > DEDUP_WINDOW:
            continue
        if _title_similarity(candidate_title, existing["title"]) >= DEDUP_THRESHOLD:
            return existing["id"]

    return None
