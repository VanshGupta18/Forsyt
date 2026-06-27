"""Read / write the news series state file.

Tracks:
  anchor_date      — first calendar day with exported scraper articles (never overwritten)
  last_processed   — most recent day successfully preprocessed
  source           — "scraper" (only supported value)

File: data/india_archive/series_state.json
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT   = Path(__file__).parent.parent
STATE_PATH  = REPO_ROOT / "data" / "india_archive" / "series_state.json"


def _load() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception as exc:
            logger.warning(f"[series_state] Could not read {STATE_PATH}: {exc}")
    return {}


def _save(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def get_anchor() -> str | None:
    """Return anchor_date string (YYYY-MM-DD) or None if not yet set."""
    return _load().get("anchor_date")


def get_last_processed() -> str | None:
    """Return last_processed string (YYYY-MM-DD) or None."""
    return _load().get("last_processed")


def set_anchor(day: str | date) -> None:
    """Set anchor_date on first call only (never overwritten)."""
    state = _load()
    if "anchor_date" not in state:
        state["anchor_date"] = str(day)
        state["source"] = "scraper"
        _save(state)
        logger.info(f"[series_state] anchor_date set to {day}")


def update_last_processed(day: str | date) -> None:
    """Update last_processed to day."""
    state = _load()
    state["last_processed"] = str(day)
    _save(state)


def summary() -> dict:
    return _load()
