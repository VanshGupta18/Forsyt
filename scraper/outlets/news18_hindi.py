"""News18 Hindi outlet — LD+JSON primary."""

from __future__ import annotations
from typing import Optional
from .base import BaseOutlet, extract_ld_json, ld_time


class News18Hindi(BaseOutlet):
    code = "N18"
    rss_url = "https://hindi.news18.com/rss/khabar/nation/nation.xml"
    source_name = "News18 Hindi"

    def _parse_html(self, url: str, soup) -> tuple[Optional[str], Optional[str]]:
        ld = extract_ld_json(soup)
        if ld:
            content = ld.get("articleBody", "").strip() or None
            return content, ld_time(ld)

        # Fallback: article-body div
        for cls in ["article-body", "content-wrapper", "story-content"]:
            div = soup.find("div", {"class": cls})
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
