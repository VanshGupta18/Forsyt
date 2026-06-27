"""Outlet registry — maps short codes to outlet classes.

All outlets implement BaseOutlet and expose:
  async def fetch_rss(session) -> list[dict]          # live path
  async def parse(*, url, html, session) -> dict|None # both paths
"""

from __future__ import annotations

from .india_today import IndiaToday
from .the_hindu import TheHindu
from .times_of_india import TimesOfIndia
from .indian_express import IndianExpress
from .ndtv import NDTV

OUTLETS: dict[str, type] = {
    "IT":   IndiaToday,
    "TH":   TheHindu,
    "TOI":  TimesOfIndia,
    "TIE":  IndianExpress,
    "NDTV": NDTV,
}


def get_parser(code: str):
    """Return the outlet class for the given code (case-insensitive), or None."""
    return OUTLETS.get(code.upper())


def all_outlets():
    """Return a list of all outlet *instances*."""
    return [cls() for cls in OUTLETS.values()]
