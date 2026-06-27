from __future__ import annotations
import re
from typing import Optional
from .base import BaseOutlet, p_text


class TheHindu(BaseOutlet):
    code = "TH"
    rss_url = "https://www.thehindu.com/latest-news/feeder/default.rss"
    source_name = "The Hindu"

    def _parse_html(self, url: str, soup) -> tuple[Optional[str], Optional[str]]:
        content_div = None
        for selector in [
            {"class": "articlebodycontent"},
            {"itemprop": "articleBody"},
            {"class": re.compile(r"article-body|paywall")},
        ]:
            content_div = soup.find("div", selector)
            if content_div:
                break

        if content_div is None:
            return None, None

        content = p_text(content_div)

        time_str = None
        time_el = soup.find("span", class_=re.compile(r"date|time|update|publish", re.I))
        if time_el:
            time_str = re.sub(
                r"Updated:|Published:|IST|AM|PM", "",
                time_el.get_text(strip=True), flags=re.IGNORECASE,
            ).strip()

        return content or None, time_str
