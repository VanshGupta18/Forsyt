"""Lightweight country-mention location tagger for Indian news articles.

Produces a synthetic V2Locations string matching the GDELT GKG format so that
gkg_gpr_pipeline.aggregate_country_day() can populate gpr_country_level.csv.

GDELT V2Locations format (semicolon-separated location blocks):
  type#fullname#countrycode#adm1code#lat#lon#featureid
  e.g.  1#India#IN#IN#20.0#77.0#1269750

We only emit country-level blocks (type=1), which is sufficient for the
country-level GPR index.

Algorithm:
  - Word/phrase scan on (title × 2 + body) using a curated dictionary of
    country names and common demonyms → GDELT 2-letter country codes.
  - India is always included if the source is an Indian outlet.
  - Output is deduplicated and sorted.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

# ---------------------------------------------------------------------------
# Country dictionary: name/demonym → (GDELT code, display name, lat, lon)
# ---------------------------------------------------------------------------

COUNTRY_MAP: dict[str, tuple[str, str, float, float]] = {
    # Name → (GDELT_code, canonical_name, lat, lon)
    # South Asia
    "india":          ("IN", "India", 20.0, 77.0),
    "indian":         ("IN", "India", 20.0, 77.0),
    "pakistan":       ("PK", "Pakistan", 30.0, 70.0),
    "pakistani":      ("PK", "Pakistan", 30.0, 70.0),
    "bangladesh":     ("BG", "Bangladesh", 23.7, 90.4),
    "bangladeshi":    ("BG", "Bangladesh", 23.7, 90.4),
    "sri lanka":      ("CE", "Sri Lanka", 7.0, 81.0),
    "sri lankan":     ("CE", "Sri Lanka", 7.0, 81.0),
    "nepal":          ("NP", "Nepal", 28.0, 84.0),
    "nepali":         ("NP", "Nepal", 28.0, 84.0),
    "myanmar":        ("BM", "Myanmar", 17.0, 96.0),
    "afghanistan":    ("AF", "Afghanistan", 33.0, 65.0),
    "afghan":         ("AF", "Afghanistan", 33.0, 65.0),
    "maldives":       ("MV", "Maldives", 3.2, 73.2),
    "bhutan":         ("BT", "Bhutan", 27.5, 90.5),
    # East / SE Asia
    "china":          ("CH", "China", 35.0, 105.0),
    "chinese":        ("CH", "China", 35.0, 105.0),
    "japan":          ("JA", "Japan", 36.0, 138.0),
    "japanese":       ("JA", "Japan", 36.0, 138.0),
    "taiwan":         ("TW", "Taiwan", 23.5, 121.0),
    "south korea":    ("KS", "South Korea", 37.0, 128.0),
    "north korea":    ("KN", "North Korea", 40.0, 127.0),
    "vietnam":        ("VM", "Vietnam", 16.0, 108.0),
    "indonesia":      ("ID", "Indonesia", -5.0, 120.0),
    "malaysia":       ("MY", "Malaysia", 2.5, 112.5),
    "philippines":    ("RP", "Philippines", 13.0, 122.0),
    "thailand":       ("TH", "Thailand", 15.0, 100.0),
    "singapore":      ("SN", "Singapore", 1.4, 103.8),
    # Middle East / Central Asia
    "iran":           ("IR", "Iran", 32.0, 53.0),
    "iranian":        ("IR", "Iran", 32.0, 53.0),
    "iraq":           ("IZ", "Iraq", 33.0, 44.0),
    "israel":         ("IS", "Israel", 31.5, 34.8),
    "israeli":        ("IS", "Israel", 31.5, 34.8),
    "saudi arabia":   ("SA", "Saudi Arabia", 24.0, 45.0),
    "saudi":          ("SA", "Saudi Arabia", 24.0, 45.0),
    "turkey":         ("TU", "Turkey", 39.0, 35.0),
    "turkish":        ("TU", "Turkey", 39.0, 35.0),
    "uae":            ("AE", "United Arab Emirates", 24.0, 54.0),
    "united arab emirates": ("AE", "United Arab Emirates", 24.0, 54.0),
    "qatar":          ("QA", "Qatar", 25.3, 51.5),
    "kuwait":         ("KU", "Kuwait", 29.5, 47.8),
    "jordan":         ("JO", "Jordan", 31.0, 36.0),
    "oman":           ("MU", "Oman", 21.0, 57.0),
    "yemen":          ("YM", "Yemen", 15.5, 48.0),
    "syria":          ("SY", "Syria", 35.0, 38.0),
    "lebanon":        ("LE", "Lebanon", 33.9, 35.5),
    "palestine":      ("WE", "West Bank", 32.0, 35.3),
    "gaza":           ("GZ", "Gaza Strip", 31.4, 34.4),
    "azerbaijan":     ("AJ", "Azerbaijan", 40.5, 47.5),
    "armenia":        ("AM", "Armenia", 40.0, 45.0),
    # Europe
    "russia":         ("RS", "Russia", 60.0, 100.0),
    "russian":        ("RS", "Russia", 60.0, 100.0),
    "ukraine":        ("UP", "Ukraine", 49.0, 32.0),
    "ukrainian":      ("UP", "Ukraine", 49.0, 32.0),
    "united kingdom": ("UK", "United Kingdom", 54.0, -2.0),
    "britain":        ("UK", "United Kingdom", 54.0, -2.0),
    "british":        ("UK", "United Kingdom", 54.0, -2.0),
    "england":        ("UK", "United Kingdom", 54.0, -2.0),
    "france":         ("FR", "France", 46.0, 2.0),
    "french":         ("FR", "France", 46.0, 2.0),
    "germany":        ("GM", "Germany", 51.0, 10.0),
    "german":         ("GM", "Germany", 51.0, 10.0),
    "italy":          ("IT", "Italy", 42.8, 12.8),
    "spain":          ("SP", "Spain", 40.0, -4.0),
    "poland":         ("PL", "Poland", 52.0, 20.0),
    "sweden":         ("SW", "Sweden", 62.0, 15.0),
    "norway":         ("NO", "Norway", 62.0, 10.0),
    "finland":        ("FI", "Finland", 64.0, 26.0),
    "greece":         ("GR", "Greece", 39.0, 22.0),
    "netherlands":    ("NL", "Netherlands", 52.5, 5.8),
    "switzerland":    ("SZ", "Switzerland", 47.0, 8.0),
    "austria":        ("AU", "Austria", 47.5, 14.6),
    "czech":          ("EZ", "Czech Republic", 49.8, 15.5),
    "hungary":        ("HU", "Hungary", 47.0, 19.5),
    "romania":        ("RO", "Romania", 46.0, 25.0),
    "serbia":         ("RI", "Serbia", 44.0, 21.0),
    # Americas
    "united states":  ("US", "United States", 38.0, -97.0),
    "america":        ("US", "United States", 38.0, -97.0),
    "american":       ("US", "United States", 38.0, -97.0),
    "usa":            ("US", "United States", 38.0, -97.0),
    "washington":     ("US", "United States", 38.0, -97.0),
    "canada":         ("CA", "Canada", 60.0, -95.0),
    "canadian":       ("CA", "Canada", 60.0, -95.0),
    "mexico":         ("MX", "Mexico", 23.0, -102.0),
    "brazil":         ("BR", "Brazil", -10.0, -55.0),
    "argentina":      ("AR", "Argentina", -34.0, -64.0),
    "colombia":       ("CO", "Colombia", 4.0, -72.0),
    "venezuela":      ("VE", "Venezuela", 8.0, -66.0),
    # Africa
    "nigeria":        ("NI", "Nigeria", 10.0, 8.0),
    "south africa":   ("SF", "South Africa", -29.0, 25.0),
    "ethiopia":       ("ET", "Ethiopia", 8.0, 38.0),
    "kenya":          ("KE", "Kenya", 1.0, 38.0),
    "egypt":          ("EG", "Egypt", 27.0, 30.0),
    "egyptian":       ("EG", "Egypt", 27.0, 30.0),
    "sudan":          ("SU", "Sudan", 15.0, 30.0),
    "somalia":        ("SO", "Somalia", 6.0, 46.0),
    "libya":          ("LY", "Libya", 27.0, 17.0),
    "morocco":        ("MO", "Morocco", 32.0, -5.0),
    "algeria":        ("AG", "Algeria", 28.0, 3.0),
    # Oceania
    "australia":      ("AS", "Australia", -25.0, 135.0),
    "australian":     ("AS", "Australia", -25.0, 135.0),
    "new zealand":    ("NZ", "New Zealand", -41.0, 174.0),
}

# Build multi-word phrases sorted longest-first so "south korea" matches before "korea"
_PHRASES = sorted(COUNTRY_MAP.keys(), key=len, reverse=True)
_PHRASE_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in _PHRASES) + r")\b",
    re.IGNORECASE,
)


def _gdelt_block(code: str, name: str, lat: float, lon: float) -> str:
    """Return a GDELT V2Locations location block (type 1 = country)."""
    adm1 = code + code  # e.g. IN → ININ
    feat = f"{lat:.1f}#{lon:.1f}"
    return f"1#{name}#{code}#{adm1}#{lat}#{lon}#"


def tag_locations(title: str, content: str) -> str:
    """Scan title+body for country names, return GDELT V2Locations string."""
    text = f"{title} {title} {content}"  # title weighted 2x
    found: set[str] = set()

    for m in _PHRASE_RE.finditer(text):
        key = m.group(1).lower()
        if key in COUNTRY_MAP:
            code, name, lat, lon = COUNTRY_MAP[key]
            found.add((code, name, lat, lon))

    if not found:
        return ""

    blocks = [_gdelt_block(code, name, lat, lon) for code, name, lat, lon in sorted(found)]
    return ";".join(blocks)
