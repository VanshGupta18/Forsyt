"""
Utility functions for reading data from the database.
"""

from db import get_geo_articles, get_geo_cycle_stats, get_total_count

def read_data_db(tier=None):
    """Read articles from SQLite database, used by the Flask API."""
    return get_geo_articles(tier=tier)
