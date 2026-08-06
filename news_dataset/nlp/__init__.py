"""NLP field extractors for scraped news articles."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from .locations import extract_locations
from .themes import extract_themes
from .tone import extract_gcam, extract_tone

__all__ = [
    "extract_gcam",
    "extract_locations",
    "extract_themes",
    "extract_tone",
]
