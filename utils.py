"""
Utility functions for reading data from the database.
"""

from db import get_articles, get_stats, get_total_count


def read_data_db(source):
    """Read articles from SQLite database, used by the Flask API."""
    return get_articles(source=source)
