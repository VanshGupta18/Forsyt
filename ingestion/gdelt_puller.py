"""
GDELT GKG API client.
Pulls India-tagged conflict news every 15 minutes.
"""

import os
import time
import hashlib
import logging
import requests
import datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

logger = logging.getLogger(__name__)

GDELT_GKG_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# CAMEO codes 14-20: protest → use of conventional force
CAMEO_CONFLICT_CODES = ["14", "15", "16", "17", "18", "19", "20"]

GDELT_PARAMS = {
    "query": 'sourcelang:english India (conflict OR attack OR military OR tension OR border)',
    "mode": "artlist",
    "maxrecords": "250",
    "format": "json",
    "timespan": "20min",     # overridden dynamically per call
    "sort": "DateDesc",
}


def normalize_url(url: str) -> str:
    """
    Strip UTM parameters, trailing slashes, and protocol variants
    to produce a canonical URL for hashing.
    """
    parsed = urlparse(url.strip().rstrip("/"))
    # Remove tracking params
    blocked_params = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                      "utm_content", "ref", "fbclid", "gclid"}
    qs = parse_qs(parsed.query, keep_blank_values=False)
    filtered_qs = {k: v for k, v in qs.items() if k not in blocked_params}
    clean_query = urlencode(filtered_qs, doseq=True)
    canonical = parsed._replace(scheme="https", query=clean_query, fragment="")
    return urlunparse(canonical).lower()


def url_hash(url: str) -> str:
    """Return SHA-256 hex digest of normalized URL."""
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()


def fetch_gdelt_articles(minutes_back: int = 20) -> List[Dict]:
    """
    Fetch India-tagged conflict articles from GDELT GKG for the last N minutes.

    Returns a list of dicts with: url, url_hash, headline, publish_ts, gdelt_event_id
    """
    params = GDELT_PARAMS.copy()
    params["timespan"] = f"{minutes_back}min"

    logger.info(f"Querying GDELT (last {minutes_back} min)...")

    try:
        resp = requests.get(GDELT_GKG_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error(f"GDELT API request failed: {e}")
        return []
    except ValueError as e:
        logger.error(f"GDELT response not valid JSON: {e}")
        return []

    articles = data.get("articles", [])
    logger.info(f"GDELT returned {len(articles)} article records")

    results = []
    for art in articles:
        raw_url = art.get("url", "").strip()
        if not raw_url:
            continue

        results.append({
            "url":            raw_url,
            "url_hash":       url_hash(raw_url),
            "headline":       art.get("title", "").strip(),
            "publish_ts":     _parse_gdelt_datestring(art.get("seendate", "")),
            "gdelt_event_id": art.get("id", ""),
            "source_domain":  urlparse(raw_url).netloc,
        })

    return results


def fetch_article_text(url: str, timeout: int = 10) -> Optional[str]:
    """
    Fetch and parse raw HTML from an article URL.
    Returns cleaned plain text, or None on failure.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; IndiaGPR-Bot/1.0; "
            "+https://github.com/your-org/india-ai-gpr)"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "header", "footer",
                         "aside", "form", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)

        # Collapse whitespace
        import re
        text = re.sub(r"\s+", " ", text).strip()

        return text if text else None

    except Exception as e:
        logger.warning(f"Failed to fetch article text from {url}: {e}")
        return None


def _parse_gdelt_datestring(datestr: str) -> Optional[str]:
    """Parse GDELT date format 'YYYYMMDDTHHMMSSZ' → ISO 8601 string."""
    if not datestr:
        return None
    try:
        dt = datetime.datetime.strptime(datestr, "%Y%m%dT%H%M%SZ")
        return dt.isoformat() + "Z"
    except ValueError:
        return None
