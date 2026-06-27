from __future__ import annotations
import re
from typing import Optional
from .base import BaseOutlet, extract_ld_json, ld_time, p_text


class IndianExpress(BaseOutlet):
    code = "TIE"
    rss_url = "https://indianexpress.com/section/india/feed/"
    source_name = "Indian Express"

    def _parse_html(self, url: str, soup) -> tuple[Optional[str], Optional[str]]:
        # Primary: LD+JSON
        ld = extract_ld_json(soup)
        content = ld.get("articleBody", "").strip() if ld else ""
        time_str = ld_time(ld) if ld else None

        # Fallback: HTML selectors
        if not content:
            for selector in [
                {"id": "pcl-full-content"},
                {"itemprop": "articleBody"},
                {"class": re.compile(r"full-details|story_details")},
            ]:
                div = soup.find("div", selector)
                if div:
                    content = p_text(div)
                    if content:
                        break

        if not time_str:
            time_el = soup.find("span", {"itemprop": "dateModified"}) or \
                      soup.find("span", class_=re.compile(r"date|time|update", re.I))
            if time_el:
                time_str = re.sub(
                    r"Updated:|IST|AM|PM", "",
                    time_el.get_text(strip=True), flags=re.IGNORECASE,
                ).strip()

        return content or None, time_str
