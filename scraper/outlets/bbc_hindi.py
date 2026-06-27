"""BBC Hindi outlet — uses <main> tag; strips tracking query params."""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from .base import BaseOutlet, rss_time_str


class BBCHindi(BaseOutlet):
    code = "BBC"
    rss_url = "https://www.bbc.com/hindi/index.xml"
    source_name = "BBC Hindi"

    def _parse_html(self, url: str, soup) -> tuple[Optional[str], Optional[str]]:
        content = None
        time_str = None

        # Primary: <main> tag (BBC Hindi structure)
        main = soup.find("main")
        if main:
            content = " ".join(p.get_text(strip=True) for p in main.find_all("p") if p.get_text(strip=True))

        # Fallback: <article>
        if not content:
            article = soup.find("article")
            if article:
                content = " ".join(p.get_text(strip=True) for p in article.find_all("p") if p.get_text(strip=True))

        # Time from <time datetime="...">
        time_el = soup.find("time")
        if time_el and time_el.get("datetime"):
            try:
                dt = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
                time_str = dt.strftime("%b %d, %Y, %H:%M")
            except Exception:
                time_str = time_el.get_text(strip=True)

        return content or None, time_str

    async def fetch_rss(self, session) -> list[dict]:
        """Strip tracking query params from BBC links."""
        results = await super().fetch_rss(session)
        for item in results:
            item["link"] = item["link"].split("?")[0]
        return results

    async def parse(self, *, url=None, html=None, session=None, rss_meta=None):
        if url:
            url = url.split("?")[0]
        result = await super().parse(url=url, html=html, session=session, rss_meta=rss_meta)
        if result:
            result["language"] = "hi"
        return result
