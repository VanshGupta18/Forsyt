"""BaseOutlet ABC — shared parsing helpers + unified parse() interface.

Every outlet subclass must set:
  code: str          e.g. "TH"
  rss_url: str
  source_name: str   e.g. "The Hindu"

And implement:
  _parse_html(url, soup) -> tuple[str|None, str|None]
    Returns (content, time_str) extracted from a BeautifulSoup tree.
    For outlets that use RSS summary directly (NDTV), can override parse() instead.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def extract_ld_json(soup) -> Optional[dict]:
    """Return first LD+JSON block containing an articleBody."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict) and "articleBody" in data:
                return data
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "articleBody" in item:
                        return item
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def ld_time(ld: dict) -> Optional[str]:
    raw = ld.get("dateModified") or ld.get("datePublished")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y, %H:%M")
    except Exception:
        return raw


def p_text(tag) -> str:
    return " ".join(p.get_text(strip=True) for p in tag.find_all("p") if p.get_text(strip=True))


def rss_time_str(entry) -> Optional[str]:
    """Extract formatted time string from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime(*parsed[:6]).strftime("%B %d, %Y %H:%M")
            except Exception:
                pass
    return None


def make_soup(html: str):
    from bs4 import BeautifulSoup  # noqa: PLC0415
    return BeautifulSoup(html, "lxml")


# ---------------------------------------------------------------------------
# BaseOutlet
# ---------------------------------------------------------------------------

class BaseOutlet(ABC):
    code: str = ""
    rss_url: str = ""
    source_name: str = ""

    # Concurrency limit: max parallel requests to this host
    max_concurrent: int = 3

    @abstractmethod
    def _parse_html(self, url: str, soup) -> tuple[Optional[str], Optional[str]]:
        """Extract (content, time_str) from a BeautifulSoup tree."""

    # ------------------------------------------------------------------
    # RSS feed fetch (live path)
    # ------------------------------------------------------------------

    async def fetch_rss(self, session) -> list[dict]:
        """Fetch RSS, return list of {title, link, rss_time} dicts."""
        import feedparser  # noqa: PLC0415
        import asyncio  # noqa: PLC0415

        loop = asyncio.get_event_loop()
        try:
            # feedparser is sync; run in executor to avoid blocking event loop
            feed = await loop.run_in_executor(None, feedparser.parse, self.rss_url)
        except Exception as exc:
            logger.warning(f"[{self.code}] RSS fetch failed: {exc}")
            return []

        results = []
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link  = entry.get("link", "").strip()
            if title and link:
                results.append({
                    "title":    title,
                    "link":     link,
                    "rss_time": rss_time_str(entry),
                })
        return results

    # ------------------------------------------------------------------
    # Article parse (live + backfill unified)
    # ------------------------------------------------------------------

    async def parse(
        self,
        *,
        url: Optional[str] = None,
        html: Optional[str] = None,
        session=None,
        rss_meta: Optional[dict] = None,
    ) -> Optional[dict]:
        """Parse one article.

        Backfill: pass html= (pre-fetched cached HTML).
        Live:     pass url= + session=; fetches the HTML automatically.
        """
        if html is None and url is not None and session is not None:
            html = await self._fetch_html(url, session)
        if html is None:
            return None

        try:
            soup = make_soup(html)
        except Exception as exc:
            logger.debug(f"[{self.code}] BeautifulSoup failed for {url}: {exc}")
            return None

        content, time_str = self._parse_html(url or "", soup)
        if not content:
            return None

        title = rss_meta.get("title", "") if rss_meta else ""
        if not title:
            h1 = soup.find("h1") or soup.find("title")
            title = h1.get_text(strip=True) if h1 else ""

        return {
            "title":    title,
            "content":  content,
            "source":   self.code,
            "link":     url or "",
            "time":     time_str or (rss_meta.get("rss_time") if rss_meta else None),
            "language": "en",
        }

    async def _fetch_html(self, url: str, session) -> Optional[str]:
        try:
            async with session.get(
                url,
                headers={"User-Agent": BROWSER_UA},
                timeout=20,
                allow_redirects=True,
            ) as resp:
                if resp.status == 200:
                    return await resp.text(errors="replace")
                logger.debug(f"[{self.code}] HTTP {resp.status} for {url}")
                return None
        except Exception as exc:
            logger.debug(f"[{self.code}] Fetch error {url}: {exc}")
            return None
