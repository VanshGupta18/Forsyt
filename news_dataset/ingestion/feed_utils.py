import requests
import feedparser
from datetime import datetime
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # A bare User-Agent with no other browser-typical headers is itself a bot signal
    # some CDN/WAF layers (CloudFront, Cloudflare) key on, independent of UA string —
    # seen causing persistent 0-entry responses for TIE specifically from shared
    # GitHub Actions runner IPs while the same URL works fine from residential IPs.
    "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9",
}


def safe_get(url, timeout=15):
    """Safely fetch a URL with error handling."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def parse_feed(url, retries=2, backoff=3):
    """Parse an RSS feed with a browser User-Agent and retry on transient failures.

    feedparser's default User-Agent gets rate-limited/blocked by some sites more
    readily than a browser UA (seen intermittently on Live Hindustan from shared
    GitHub Actions runner IPs), and a single network hiccup would otherwise drop
    that source's articles for the whole run.
    """
    last_exc = None
    for attempt in range(retries + 1):
        try:
            feed = feedparser.parse(url, request_headers=HEADERS)
            if feed.entries:
                return feed
            last_exc = feed.bozo_exception if feed.bozo else None
        except Exception as e:
            last_exc = e

        if attempt < retries:
            time.sleep(backoff)

    logger.warning(
        "parse_feed: no entries from %s after %d attempts: %s",
        url, retries + 1, last_exc,
    )
    return feedparser.parse("", request_headers=HEADERS)


def parse_rss_time(entry):
    """Extract and format time from an RSS feed entry."""
    time_str = None
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6])
            time_str = dt.strftime("%B %d, %Y %H:%M")
        except Exception:
            pass
    if not time_str and hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            dt = datetime(*entry.updated_parsed[:6])
            time_str = dt.strftime("%B %d, %Y %H:%M")
        except Exception:
            pass
    return time_str
