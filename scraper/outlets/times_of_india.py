from __future__ import annotations
import re
from typing import Optional
from .base import BaseOutlet, extract_ld_json, ld_time, p_text


class TimesOfIndia(BaseOutlet):
    code = "TOI"
    rss_url = "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"
    source_name = "Times of India"

    def _parse_html(self, url: str, soup) -> tuple[Optional[str], Optional[str]]:
        # Primary: LD+JSON
        ld = extract_ld_json(soup)
        content = ld.get("articleBody", "").strip() if ld else ""
        time_str = ld_time(ld) if ld else None

        # Fallback: HTML selectors
        if not content:
            for selector in [
                {"itemprop": "articleBody"},
                {"class": re.compile(r"ga-headlines|article-body|story-content")},
                {"class": "Normal"},
            ]:
                div = soup.find("div", selector)
                if div:
                    content = p_text(div)
                    if content:
                        break

        if not content:
            arttextxml = soup.find("arttextxml")
            if arttextxml:
                content = arttextxml.get_text(strip=True)

        if not time_str:
            time_el = soup.find("div", class_=re.compile(r"byline|xf8Pm|publish", re.I))
            if time_el:
                span = time_el.find("span")
                if span:
                    time_str = re.sub(
                        r"Updated:|IST|AM|PM", "",
                        span.get_text(strip=True), flags=re.IGNORECASE,
                    ).strip()

        return content or None, time_str
