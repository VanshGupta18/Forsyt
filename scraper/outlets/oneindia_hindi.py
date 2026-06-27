"""OneIndia Hindi outlet — LD+JSON primary, article-body fallback."""

from __future__ import annotations
from typing import Optional
from .base import BaseOutlet, extract_ld_json, ld_time, p_text


class OneIndiaHindi(BaseOutlet):
    code = "OI"
    rss_url = "https://hindi.oneindia.com/rss/feeds/oneindia-hindi-fb.xml"
    source_name = "OneIndia Hindi"

    def _parse_html(self, url: str, soup) -> tuple[Optional[str], Optional[str]]:
        ld = extract_ld_json(soup)
        if ld:
            content = ld.get("articleBody", "").strip() or None
            return content, ld_time(ld)

        import re
        div = soup.find("div", {"class": re.compile(r"article.?body", re.I)})
        if div:
            content = p_text(div)
            if content:
                return content, None

        return None, None

    async def parse(self, *, url=None, html=None, session=None, rss_meta=None):
        result = await super().parse(url=url, html=html, session=session, rss_meta=rss_meta)
        if result:
            result["language"] = "hi"
        return result
