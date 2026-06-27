"""Utility functions for reading data — port of origin/news_scraper utils.py."""

from __future__ import annotations

from .db import get_articles, get_stats, get_total_count  # noqa: F401


def read_data_db(source: str) -> list[dict]:
    """Read articles from SQLite, used by the Flask API."""
    return get_articles(source=source)
