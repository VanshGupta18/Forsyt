"""On-demand og:image resolution for news links — in-memory cache only, no DB."""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from urllib.parse import urljoin, urlparse

import requests

from news_dataset.api.cache import _MISSING, cache_get, cache_set
from news_dataset.ingestion.feed_utils import HEADERS

logger = logging.getLogger(__name__)

_CACHE_TTL = 6 * 3600
# This fetches a URL supplied by the caller (/api/news/image?link=...), so it is
# an SSRF sink: without these limits it will happily fetch cloud instance
# metadata (169.254.169.254), localhost, or anything on the private network the
# server sits in, and report back what it found.
_MAX_BYTES = 512_000
_MAX_REDIRECTS = 3
_ALLOWED_PORTS = {80, 443}

_OG_IMAGE = re.compile(
    r'<meta[^>]+(?:property=["\']og:image["\']|name=["\']twitter:image["\'])[^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_OG_IMAGE_ALT = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property=["\']og:image["\']|name=["\']twitter:image["\'])',
    re.IGNORECASE,
)


def _is_blocked_address(host: str) -> bool:
    """True if `host` resolves to anything that isn't a public internet address.

    Checks every address the name resolves to, not just the first: a hostname
    can legitimately return several, and only needs one internal answer to be
    dangerous. An unresolvable host is treated as blocked — if we can't tell
    where it points, we don't fetch it.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True
    addresses = {info[4][0] for info in infos}
    if not addresses:
        return True
    for raw in addresses:
        try:
            addr = ipaddress.ip_address(raw)
        except ValueError:
            return True
        # is_private already covers loopback and link-local (169.254.0.0/16,
        # i.e. the cloud metadata endpoint); the rest are spelled out so this
        # stays obvious to read.
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
            or addr.is_unspecified
        ):
            return True
    return False


def _is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        return False
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    # Restricting to the web ports keeps this from being used to probe internal
    # services listening on odd ports.
    if port not in _ALLOWED_PORTS:
        return False
    return not _is_blocked_address(parsed.hostname)


def _extract_image(html: str) -> str | None:
    for pattern in (_OG_IMAGE, _OG_IMAGE_ALT):
        match = pattern.search(html)
        if match:
            return match.group(1).strip()
    return None


def resolve_news_image(link: str) -> str | None:
    if not _is_safe_url(link):
        return None
    cache_key = f"link_preview:{link}"
    cached = cache_get(cache_key, ttl_seconds=_CACHE_TTL)
    if cached is not _MISSING:
        return cached
    image: str | None = None
    try:
        resp, final_url = _fetch_html(link)
        if resp is not None:
            body = _read_capped(resp)
            if 'text/html' in (resp.headers.get('content-type') or '').lower() or body.lstrip().startswith('<'):
                image = _extract_image(body)
                if image and image.startswith('//'):
                    image = f'https:{image}'
                elif image and image.startswith('/'):
                    parsed = urlparse(final_url)
                    image = f'{parsed.scheme}://{parsed.netloc}{image}'
    except Exception as exc:
        logger.debug('link_preview failed for %s: %s', link, exc)
    cache_set(cache_key, image)
    return image


def _fetch_html(link: str) -> tuple[requests.Response | None, str]:
    """Fetch `link`, re-validating every redirect hop.

    requests' own allow_redirects would follow a public URL to a private one
    without us ever seeing the intermediate target, so redirects are followed
    by hand and each destination goes back through _is_safe_url().
    """
    url = link
    for _ in range(_MAX_REDIRECTS + 1):
        resp = requests.get(
            url,
            headers=HEADERS,
            timeout=4,
            allow_redirects=False,
            stream=True,  # headers first; the body is read under a cap below
        )
        if resp.is_redirect or resp.is_permanent_redirect:
            location = resp.headers.get('location') or ''
            resp.close()
            if not location:
                return None, url
            url = urljoin(url, location)
            if not _is_safe_url(url):
                logger.debug('link_preview refused redirect to %s', url)
                return None, url
            continue
        resp.raise_for_status()
        return resp, url
    logger.debug('link_preview hit redirect limit for %s', link)
    return None, url


def _read_capped(resp: requests.Response) -> str:
    """Read at most _MAX_BYTES of the body.

    Without a cap, a link to a large file would be pulled entirely into memory
    before the content-type check ever ran.
    """
    chunks: list[bytes] = []
    total = 0
    for chunk in resp.iter_content(8192):
        chunks.append(chunk)
        total += len(chunk)
        if total >= _MAX_BYTES:
            break
    resp.close()
    return b''.join(chunks).decode(resp.encoding or 'utf-8', errors='replace')[:120_000]
