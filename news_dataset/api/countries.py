"""The 15 high-relevance countries for India-relative country cards.

FIPS 10-4 codes — that is what the GKG pipeline and gpr_bilateral_daily.csv use
(traps: CH=China, RS=Russia, CE=Sri Lanka, BM=Myanmar, SN=Singapore).
`iso2` is only for frontend flag emojis (FIPS != ISO). `corridors` links a
country to the trade/energy corridors it sits on.
"""
from __future__ import annotations

# fips -> (name, iso2, iso3, corridors). iso2 = flag emoji + World Bank; iso3 = PortWatch + OWID energy.
COUNTRIES: dict[str, dict] = {
    "CH": {"name": "China",         "iso2": "CN", "iso3": "CHN", "corridors": ["india_china_lac", "taiwan_south_china_sea"]},
    "PK": {"name": "Pakistan",      "iso2": "PK", "iso3": "PAK", "corridors": ["india_pakistan_attari"]},
    "US": {"name": "United States", "iso2": "US", "iso3": "USA", "corridors": []},
    "RS": {"name": "Russia",        "iso2": "RU", "iso3": "RUS", "corridors": ["instc_chabahar"]},
    "IR": {"name": "Iran",          "iso2": "IR", "iso3": "IRN", "corridors": ["instc_chabahar", "strait_of_hormuz"]},
    "SA": {"name": "Saudi Arabia",  "iso2": "SA", "iso3": "SAU", "corridors": ["strait_of_hormuz", "imec"]},
    "AE": {"name": "UAE",           "iso2": "AE", "iso3": "ARE", "corridors": ["strait_of_hormuz", "imec"]},
    "BG": {"name": "Bangladesh",    "iso2": "BD", "iso3": "BGD", "corridors": ["india_bangladesh_petrapole"]},
    "CE": {"name": "Sri Lanka",     "iso2": "LK", "iso3": "LKA", "corridors": ["cape_of_good_hope"]},
    "NP": {"name": "Nepal",         "iso2": "NP", "iso3": "NPL", "corridors": ["india_nepal_raxaul"]},
    "BM": {"name": "Myanmar",       "iso2": "MM", "iso3": "MMR", "corridors": ["strait_of_malacca"]},
    "AF": {"name": "Afghanistan",   "iso2": "AF", "iso3": "AFG", "corridors": ["instc_chabahar"]},
    "IS": {"name": "Israel",        "iso2": "IL", "iso3": "ISR", "corridors": ["imec", "red_sea_suez"]},
    "QA": {"name": "Qatar",         "iso2": "QA", "iso3": "QAT", "corridors": ["strait_of_hormuz"]},
    "SN": {"name": "Singapore",     "iso2": "SG", "iso3": "SGP", "corridors": ["strait_of_malacca"]},
}

FIPS_CODES = list(COUNTRIES)


def country_meta(fips: str) -> dict | None:
    fips = (fips or "").upper()
    meta = COUNTRIES.get(fips)
    return {"fips": fips, **meta} if meta else None
