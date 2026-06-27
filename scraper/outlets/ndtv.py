"""NDTV outlet.

NDTV blocks server-side article fetches (403). Content is taken from the
RSS feed summary/content field instead. For backfill (html=), we try LD+JSON
then fall back to the article body div.
"""

from __future__ import annotations
from typing import Optional
from bs4 import BeautifulSoup
from .base import BaseOutlet, extract_ld_json, ld_time, p_text, rss_time_str


class NDTV(BaseOutlet):
    code = "NDTV"
    rss_url = "https://feeds.feedburner.com/ndtvnews-top-stories"
    source_name = "NDTV"

    def _parse_html(self, url: str, soup) -> tuple[Optional[str], Optional[str]]:
        """Used for backfill (Wayback cached pages)."""
        ld = extract_ld_json(soup)
        content = ld.get("articleBody", "").strip() if ld else ""
        time_str = ld_time(ld) if ld else None

        if not content:
            for selector in [
                {"itemprop": "articleBody"},
                {"class": "ins_storybody"},
                {"class": "story__content"},
            ]:
                div = soup.find("div", selector)
                if div:
                    content = p_text(div)
                    if content:
                        break

        return content or None, time_str

    async def fetch_rss(self, session) -> list[dict]:
        """Override: also extract content from the RSS summary (avoids article fetch)."""
        import feedparser  # noqa: PLC0415
        import asyncio    # noqa: PLC0415

        loop = asyncio.get_event_loop()
        try:
            feed = await loop.run_in_executor(None, feedparser.parse, self.rss_url)
        except Exception:
            return []

        results = []
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link  = entry.get("link", "").strip().split("#")[0]
            if not title or not link:
                continue

            rss_t = rss_time_str(entry)

            # Extract content from RSS (avoids blocked article pages)
            content = ""
            raw_content = getattr(entry, "content", None)
            if raw_content:
                content = max((c.get("value", "") for c in raw_content), key=len, default="")
            if not content:
                content = getattr(entry, "summary", "")
            if content:
                content = BeautifulSoup(content, "lxml").get_text(strip=True)

            if content:
                results.append({
                    "title":        title,
                    "link":         link,
                    "rss_time":     rss_t,
                    "_rss_content": content,   # pre-extracted, skip article fetch
                })
        return results

    async def parse(self, *, url=None, html=None, session=None, rss_meta=None) -> Optional[dict]:
        """For live path: use pre-extracted RSS content. For backfill: use HTML."""
        if rss_meta and rss_meta.get("_rss_content"):
            return {
                "title":    rss_meta.get("title", ""),
                "content":  rss_meta["_rss_content"],
                "source":   self.code,
                "link":     url or rss_meta.get("link", ""),
                "time":     rss_meta.get("rss_time"),
                "language": "en",
            }
        # Backfill: delegate to HTML path
        return await super().parse(url=url, html=html, session=session, rss_meta=rss_meta)
