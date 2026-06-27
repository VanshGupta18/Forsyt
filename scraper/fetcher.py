"""Async HTTP helpers — aiohttp ClientSession with per-host concurrency limits.

Usage:
  async with make_session() as session:
      html = await safe_get(session, url, host="thehindu.com")
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT   = aiohttp.ClientTimeout(total=20, connect=8)
MAX_RETRIES       = 2
BACKOFF_BASE      = 1.5   # seconds

# Per-host semaphore: limits parallel requests to each news site
_HOST_SEMAPHORES: dict[str, asyncio.Semaphore] = {}
DEFAULT_HOST_CONCURRENCY = 3


def _get_semaphore(host: str, max_concurrent: int = DEFAULT_HOST_CONCURRENCY) -> asyncio.Semaphore:
    if host not in _HOST_SEMAPHORES:
        _HOST_SEMAPHORES[host] = asyncio.Semaphore(max_concurrent)
    return _HOST_SEMAPHORES[host]


@asynccontextmanager
async def make_session():
    """Context manager returning a pre-configured aiohttp ClientSession."""
    connector = aiohttp.TCPConnector(limit=64, ttl_dns_cache=300)
    headers   = {"User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"}
    async with aiohttp.ClientSession(
        connector=connector,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    ) as session:
        yield session


async def safe_get(
    session: aiohttp.ClientSession,
    url: str,
    host: Optional[str] = None,
    max_concurrent: int = DEFAULT_HOST_CONCURRENCY,
    retries: int = MAX_RETRIES,
) -> Optional[str]:
    """Fetch URL, return text or None. Honours per-host semaphore + retry."""
    if host is None:
        # Extract host from URL for semaphore key
        try:
            from urllib.parse import urlparse  # noqa: PLC0415
            host = urlparse(url).netloc or url[:30]
        except Exception:
            host = "unknown"

    sem = _get_semaphore(host, max_concurrent)

    async with sem:
        for attempt in range(retries + 1):
            try:
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status == 200:
                        return await resp.text(errors="replace")
                    if resp.status in (403, 404, 410):
                        # Non-retryable client errors
                        logger.debug(f"HTTP {resp.status} (non-retryable): {url}")
                        return None
                    logger.debug(f"HTTP {resp.status} attempt {attempt+1}: {url}")
            except asyncio.TimeoutError:
                logger.debug(f"Timeout attempt {attempt+1}: {url}")
            except aiohttp.ClientError as exc:
                logger.debug(f"ClientError attempt {attempt+1}: {url} — {exc}")

            if attempt < retries:
                await asyncio.sleep(BACKOFF_BASE ** (attempt + 1))

    logger.debug(f"All {retries+1} attempts failed: {url}")
    return None
