"""Amar Ujala outlet — Hindi, LD+JSON primary."""

from __future__ import annotations
from typing import Optional
from .base import BaseOutlet, extract_ld_json, ld_time


class AmarUjala(BaseOutlet):
    code = "AU"
    rss_url = "https://www.amarujala.com/rss/breaking-news.xml"
    source_name = "Amar Ujala"

    def _parse_html(self, url: str, soup) -> tuple[Optional[str], Optional[str]]:
        ld = extract_ld_json(soup)
        if ld:
            content = ld.get("articleBody", "").strip() or None
            return content, ld_time(ld)

        # Fallback: main article div
        for selector in [
            {"class": "article-content"},
            {"class": "news-detail"},
            {"itemprop": "articleBody"},
        ]:
            div = soup.find("div", selector)
            if div:
                text = " ".join(p.get_text(strip=True) for p in div.find_all("p") if p.get_text(strip=True))
                if text:
                    return text, None

        return None, None

    async def parse(self, *, url=None, html=None, session=None, rss_meta=None):
        result = await super().parse(url=url, html=html, session=session, rss_meta=rss_meta)
        if result:
            result["language"] = "hi"
        return result
