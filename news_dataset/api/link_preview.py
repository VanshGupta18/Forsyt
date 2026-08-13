"""On-demand og:image resolution for news links — in-memory cache only, no DB."""

from __future__ import annotations

import logging
import re
import time
from collections import OrderedDict
from urllib.parse import urlparse

import requests

from news_dataset.ingestion.feed_utils import HEADERS

logger = logging.getLogger(__name__)

_CACHE_MAX = 500
_CACHE_TTL = 6 * 3600
_cache: OrderedDict[str, tuple[float, str | None]] = OrderedDict()

_OG_IMAGE = re.compile(
    r'<meta[^>]+(?:property=["\']og:image["\']|name=["\']twitter:image["\'])[^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_OG_IMAGE_ALT = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property=["\']og:image["\']|name=["\']twitter:image["\'])',
    re.IGNORECASE,
)


def _is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return parsed.scheme in ('http', 'https') and bool(parsed.netloc)


def _cache_get(url: str) -> str | None | ...:
    entry = _cache.get(url)
    if not entry:
        return ...
    ts, image = entry
    if time.time() - ts > _CACHE_TTL:
        _cache.pop(url, None)
        return ...
    _cache.move_to_end(url)
    return image


def _cache_set(url: str, image: str | None) -> None:
    _cache[url] = (time.time(), image)
    _cache.move_to_end(url)
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)


def _extract_image(html: str) -> str | None:
    for pattern in (_OG_IMAGE, _OG_IMAGE_ALT):
        match = pattern.search(html)
        if match:
            return match.group(1).strip()
    return None


def resolve_news_image(link: str) -> str | None:
    if not _is_safe_url(link):
        return None
    cached = _cache_get(link)
    if cached is not ...:
        return cached
    image: str | None = None
    try:
        resp = requests.get(link, headers=HEADERS, timeout=4, allow_redirects=True)
        resp.raise_for_status()
        if 'text/html' in (resp.headers.get('content-type') or '').lower() or resp.text.lstrip().startswith('<'):
            image = _extract_image(resp.text[:120_000])
            if image and image.startswith('//'):
                image = f'https:{image}'
            elif image and image.startswith('/'):
                parsed = urlparse(link)
                image = f'{parsed.scheme}://{parsed.netloc}{image}'
    except Exception as exc:
        logger.debug('link_preview failed for %s: %s', link, exc)
    _cache_set(link, image)
    return image
