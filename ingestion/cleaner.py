"""
HTML cleaning and text normalization pipeline.
Prepares raw article text for LLM extraction.
"""

import re
import unicodedata
import logging
from typing import Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MAX_TOKENS = 1500       # GPT-4o-mini context budget
MIN_WORD_COUNT = 100    # Reject stub pages / paywalled articles
AVG_CHARS_PER_TOKEN = 4 # Conservative estimate for token truncation


def clean_article(html_or_text: str) -> Optional[str]:
    """
    Full cleaning pipeline:
    1. Strip any remaining HTML tags
    2. NFKC Unicode normalization
    3. Remove boilerplate patterns
    4. Collapse whitespace
    5. Truncate to MAX_TOKENS
    6. Reject if < MIN_WORD_COUNT

    Returns cleaned text, or None if article should be discarded.
    """
    if not html_or_text or not html_or_text.strip():
        return None

    text = html_or_text

    # Strip HTML if any residual tags remain
    if "<" in text and ">" in text:
        soup = BeautifulSoup(text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "aside", "form", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)

    # NFKC normalization: converts ﬁ → fi, ™ → TM, etc.
    text = unicodedata.normalize("NFKC", text)

    # Remove boilerplate patterns
    text = _remove_boilerplate(text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Reject stubs and paywalled pages
    word_count = len(text.split())
    if word_count < MIN_WORD_COUNT:
        logger.debug(f"Article rejected: {word_count} words (min {MIN_WORD_COUNT})")
        return None

    # Truncate to token budget
    max_chars = MAX_TOKENS * AVG_CHARS_PER_TOKEN
    if len(text) > max_chars:
        text = text[:max_chars]
        # Cut at word boundary
        last_space = text.rfind(" ")
        if last_space > max_chars * 0.9:
            text = text[:last_space]

    return text


def extract_headline(html_or_text: str) -> Optional[str]:
    """
    Extract the article headline from HTML (prefers <h1> tag).
    Falls back to first sentence of text.
    """
    if not html_or_text:
        return None

    if "<" in html_or_text:
        soup = BeautifulSoup(html_or_text, "html.parser")
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)[:255]

        title = soup.find("title")
        if title:
            return title.get_text(strip=True)[:255]

    # Fallback: first sentence
    sentences = html_or_text.strip().split(".")
    if sentences:
        return sentences[0].strip()[:255]

    return None


def _remove_boilerplate(text: str) -> str:
    """Remove common boilerplate patterns from news articles."""
    boilerplate_patterns = [
        r"Subscribe to our newsletter.*?$",
        r"Click here to read.*?$",
        r"Read more:.*?$",
        r"Also read:.*?$",
        r"Advertisement.*?Advertisement",
        r"Share this article.*?$",
        r"Follow us on (Twitter|Facebook|Instagram).*?$",
        r"Copyright \d{4}.*?$",
        r"All rights reserved.*?$",
        r"Terms of (use|service).*?$",
        r"Privacy policy.*?$",
        r"\[.*?Subscribe.*?\]",
        r"Cookie.*?settings",
    ]
    for pattern in boilerplate_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)
    return text
