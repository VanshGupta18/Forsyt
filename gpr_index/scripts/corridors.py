"""Shared corridor registry and pure GDELT V2Locations tagger.

Country codes and ADM1 values use GDELT's FIPS 10-4 conventions, not ISO.
Exposure values are fractions of the relevant Indian import/trade denominator;
zero means no current, quantified throughput through that corridor.
"""

from __future__ import annotations

import re
from typing import NamedTuple, TypedDict


class PlaceSpec(TypedDict):
    aliases: tuple[str, ...]
    lat: float
    lon: float
    countrycode: str
    adm1: str
    corridors: tuple[str, ...]


class CorridorSpec(TypedDict):
    name: str
    countries: frozenset[str]
    bounds: tuple[float, float, float, float] | None
    adm1: frozenset[str]
    energy_exposure: float
    goods_exposure: float
    exposure_source: str


# Public gazetteer imported by news_dataset/nlp/locations.py. Keys are canonical
# fullnames suitable for emitting type=4 V2Locations blocks.
CORRIDOR_PLACES: dict[str, PlaceSpec] = {
    "Strait of Hormuz": {
        "aliases": ("Strait of Hormuz", "Hormuz Strait", "Hormuz"),
        "lat": 26.5667, "lon": 56.2500, "countrycode": "MU", "adm1": "",
        "corridors": ("strait_of_hormuz",),
    },
    "Red Sea": {
        "aliases": ("Red Sea", "Houthi"),
        "lat": 20.0, "lon": 38.0, "countrycode": "", "adm1": "",
        "corridors": ("red_sea_suez",),
    },
    "Bab el-Mandeb": {
        "aliases": ("Bab el-Mandeb", "Bab al-Mandab", "Bab al Mandab"),
        "lat": 12.5833, "lon": 43.3333, "countrycode": "YM", "adm1": "",
        "corridors": ("red_sea_suez",),
    },
    "Suez Canal": {
        "aliases": ("Suez Canal", "Suez"),
        "lat": 30.4550, "lon": 32.3500, "countrycode": "EG", "adm1": "",
        "corridors": ("red_sea_suez",),
    },
    "Strait of Malacca": {
        "aliases": ("Strait of Malacca", "Malacca Strait", "Malacca"),
        "lat": 2.5000, "lon": 101.0000, "countrycode": "MY", "adm1": "",
        "corridors": ("strait_of_malacca",),
    },
    "Cape of Good Hope": {
        "aliases": ("Cape of Good Hope", "Cape Route"),
        "lat": -34.3568, "lon": 18.4740, "countrycode": "SF", "adm1": "",
        "corridors": ("cape_of_good_hope",),
    },
    "Danish Straits": {
        "aliases": ("Danish Straits", "Danish Strait", "Oresund", "Øresund", "Great Belt"),
        "lat": 55.7500, "lon": 12.7500, "countrycode": "DA", "adm1": "",
        "corridors": ("danish_straits_baltic",),
    },
    "Baltic Sea": {
        "aliases": ("Baltic Sea",),
        "lat": 57.0000, "lon": 19.0000, "countrycode": "", "adm1": "",
        "corridors": ("danish_straits_baltic",),
    },
    "Taiwan Strait": {
        "aliases": ("Taiwan Strait", "Formosa Strait"),
        "lat": 24.0000, "lon": 119.5000, "countrycode": "TW", "adm1": "",
        "corridors": ("taiwan_south_china_sea",),
    },
    "South China Sea": {
        "aliases": ("South China Sea", "Spratly Islands", "Paracel Islands"),
        "lat": 12.0000, "lon": 114.0000, "countrycode": "", "adm1": "",
        "corridors": ("taiwan_south_china_sea",),
    },
    "Ladakh": {
        "aliases": ("Ladakh", "Galwan Valley", "Pangong Tso", "Demchok"),
        "lat": 34.1526, "lon": 77.5771, "countrycode": "IN", "adm1": "IN30",
        "corridors": ("india_china_lac",),
    },
    "Attari-Wagah": {
        "aliases": ("Attari-Wagah", "Attari Wagah", "Wagah Border", "Attari Border"),
        "lat": 31.6048, "lon": 74.5720, "countrycode": "IN", "adm1": "IN23",
        "corridors": ("india_pakistan_attari",),
    },
    "Petrapole": {
        "aliases": ("Petrapole", "Benapole"),
        "lat": 23.0500, "lon": 88.8300, "countrycode": "IN", "adm1": "IN28",
        "corridors": ("india_bangladesh_petrapole",),
    },
    "Raxaul-Birgunj": {
        "aliases": ("Raxaul", "Birgunj", "Raxaul-Birgunj"),
        "lat": 26.9833, "lon": 84.8500, "countrycode": "IN", "adm1": "IN34",
        "corridors": ("india_nepal_raxaul",),
    },
    "India-Middle East-Europe Economic Corridor": {
        "aliases": ("India-Middle East-Europe Economic Corridor", "IMEC corridor"),
        "lat": 25.2048, "lon": 55.2708, "countrycode": "AE", "adm1": "",
        "corridors": ("imec",),
    },
    "International North-South Transport Corridor": {
        "aliases": ("International North-South Transport Corridor", "INSTC corridor"),
        "lat": 27.1833, "lon": 56.2667, "countrycode": "IR", "adm1": "",
        "corridors": ("instc_chabahar",),
    },
    "Chabahar": {
        "aliases": ("Chabahar", "Chabahar Port"),
        "lat": 25.2919, "lon": 60.6430, "countrycode": "IR", "adm1": "IR04",
        "corridors": ("instc_chabahar",),
    },
}


CORRIDORS: dict[str, CorridorSpec] = {
    "strait_of_hormuz": {
        "name": "Strait of Hormuz",
        "countries": frozenset({"IR", "MU", "AE", "QA", "SA", "BA"}),
        "bounds": (26.0, 27.2, 55.5, 57.2), "adm1": frozenset(),
        "energy_exposure": 0.336, "goods_exposure": 0.0,
        "exposure_source": "https://www.businessupturn.com/nation/india-cut-its-hormuz-dependence-from-61-to-33-before-the-war-began-this-chart-shows-how-foresighted-that-decision-was/",
    },
    "red_sea_suez": {
        "name": "Red Sea / Bab el-Mandeb / Suez",
        "countries": frozenset({"EG", "YM", "DJ", "ER", "SU", "SA"}),
        "bounds": (12.0, 31.5, 32.0, 44.0), "adm1": frozenset(),
        "energy_exposure": 0.271, "goods_exposure": 0.35,
        "exposure_source": (
            "energy: https://www.businessupturn.com/nation/india-cut-its-hormuz-dependence-from-61-to-33-before-the-war-began-this-chart-shows-how-foresighted-that-decision-was/; "
            "goods: https://www.icra.in/Rating/DownloadResearchSummaryReport?id=5494"
        ),
    },
    "strait_of_malacca": {
        "name": "Strait of Malacca",
        "countries": frozenset({"MY", "SN", "ID"}),
        "bounds": (0.5, 6.5, 98.0, 104.5), "adm1": frozenset(),
        "energy_exposure": 0.0, "goods_exposure": 0.55,
        "exposure_source": "https://www.mea.gov.in/lok-sabha.htm?dtl%2F35118%2Fquestion+no+4832+indian+trade+through+south+china+sea=",
    },
    "cape_of_good_hope": {
        "name": "Cape of Good Hope",
        "countries": frozenset({"SF"}),
        "bounds": (-36.0, -32.0, 16.0, 21.0), "adm1": frozenset(),
        "energy_exposure": 0.136, "goods_exposure": 0.0,
        "exposure_source": "https://www.businessupturn.com/nation/india-cut-its-hormuz-dependence-from-61-to-33-before-the-war-began-this-chart-shows-how-foresighted-that-decision-was/",
    },
    "danish_straits_baltic": {
        "name": "Danish Straits / Baltic",
        "countries": frozenset({"DA", "SW", "FI", "EN", "LG", "LH", "RS"}),
        "bounds": (54.0, 58.5, 8.0, 16.5), "adm1": frozenset(),
        "energy_exposure": 0.176, "goods_exposure": 0.0,
        "exposure_source": "https://www.businessupturn.com/nation/india-cut-its-hormuz-dependence-from-61-to-33-before-the-war-began-this-chart-shows-how-foresighted-that-decision-was/",
    },
    "taiwan_south_china_sea": {
        "name": "Taiwan Strait / South China Sea",
        "countries": frozenset({"CH", "TW", "VM", "RP", "BX"}),
        "bounds": (3.0, 26.5, 105.0, 122.5), "adm1": frozenset(),
        "energy_exposure": 0.0, "goods_exposure": 0.55,
        "exposure_source": "https://www.mea.gov.in/lok-sabha.htm?dtl%2F35118%2Fquestion+no+4832+indian+trade+through+south+china+sea=",
    },
    "india_china_lac": {
        "name": "India-China LAC (Ladakh)",
        "countries": frozenset({"IN", "CH"}), "bounds": None,
        "adm1": frozenset({"IN30", "CH14", "CH29"}),
        "energy_exposure": 0.0, "goods_exposure": 0.0,
        "exposure_source": "https://www.mea.gov.in/press-releases.htm?dtl/37455/",
    },
    "india_pakistan_attari": {
        "name": "India-Pakistan (Attari-Wagah)",
        "countries": frozenset({"IN", "PK"}), "bounds": None,
        "adm1": frozenset({"IN23", "PK04"}),
        "energy_exposure": 0.0, "goods_exposure": 0.0,
        "exposure_source": "https://www.commerce.gov.in/international-trade/trade-agreements/india-pakistan-trade-relations/",
    },
    "india_bangladesh_petrapole": {
        "name": "India-Bangladesh (Petrapole)",
        "countries": frozenset({"IN", "BG"}), "bounds": None,
        "adm1": frozenset({"IN28", "BG82"}),
        "energy_exposure": 0.0, "goods_exposure": 0.0,
        "exposure_source": "https://www.lpai.gov.in/en/icp-petrapole",
    },
    "india_nepal_raxaul": {
        "name": "India-Nepal (Raxaul-Birgunj)",
        "countries": frozenset({"IN", "NP"}), "bounds": None,
        "adm1": frozenset({"IN34", "NP2"}),
        "energy_exposure": 0.0, "goods_exposure": 0.0,
        "exposure_source": "https://www.mea.gov.in/Portal/ForeignRelation/India-Nepal_2024.pdf",
    },
    "imec": {
        "name": "India-Middle East-Europe Economic Corridor",
        # India itself is deliberately excluded: an India-wide mention is not
        # evidence that the article concerns this specific proposed route.
        "countries": frozenset({"AE", "SA", "JO", "IS", "GR", "IT"}),
        "bounds": None, "adm1": frozenset(),
        "energy_exposure": 0.0, "goods_exposure": 0.0,
        "exposure_source": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2122269",
    },
    "instc_chabahar": {
        "name": "INSTC / Chabahar",
        "countries": frozenset({"IR", "AJ", "RS", "KZ", "TX"}),
        "bounds": None, "adm1": frozenset(),
        "energy_exposure": 0.0, "goods_exposure": 0.0,
        "exposure_source": "https://www.mea.gov.in/press-releases.htm?dtl/37867/",
    },
}


class _Location(NamedTuple):
    fullname: str
    country: str
    adm1: str
    lat: float | None
    lon: float | None


def _parse_locations(v2locations: str) -> list[_Location]:
    locations: list[_Location] = []
    for entry in v2locations.split(";"):
        parts = entry.split("#")
        if len(parts) < 6:
            continue
        try:
            lat = float(parts[4])
            lon = float(parts[5])
        except (TypeError, ValueError):
            lat = lon = None
        locations.append(
            _Location(parts[1], parts[2].upper(), parts[3].upper(), lat, lon)
        )
    return locations


def _name_matches(fullname: str, corridor: str) -> bool:
    for place in CORRIDOR_PLACES.values():
        if corridor not in place["corridors"]:
            continue
        for alias in place["aliases"]:
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", fullname, re.IGNORECASE):
                return True
    return False


def tag_corridors(v2locations: str) -> list[str]:
    """Return corridor IDs matched by a GDELT-format V2Locations string."""
    if not isinstance(v2locations, str) or not v2locations:
        return []

    locations = _parse_locations(v2locations)
    matches: list[str] = []
    for corridor_id, spec in CORRIDORS.items():
        matched = False
        for location in locations:
            if _name_matches(location.fullname, corridor_id):
                matched = True
                break

            if location.country in spec["countries"]:
                if not spec["adm1"] or location.adm1 in spec["adm1"]:
                    matched = True
                    break

            bounds = spec["bounds"]
            if bounds and location.lat is not None and location.lon is not None:
                min_lat, max_lat, min_lon, max_lon = bounds
                if min_lat <= location.lat <= max_lat and min_lon <= location.lon <= max_lon:
                    matched = True
                    break

        if matched:
            matches.append(corridor_id)
    return matches


CORRIDOR_CATEGORIES: dict[str, str] = {
    "strait_of_hormuz": "sea",
    "red_sea_suez": "sea",
    "strait_of_malacca": "sea",
    "cape_of_good_hope": "sea",
    "danish_straits_baltic": "sea",
    "taiwan_south_china_sea": "sea",
    "india_china_lac": "land",
    "india_pakistan_attari": "land",
    "india_bangladesh_petrapole": "land",
    "india_nepal_raxaul": "land",
    "imec": "strategic",
    "instc_chabahar": "strategic",
}

_INDIA_LATLON = (20.5937, 78.9629)

# Map paths and centroids for dashboard geo viz (lat, lon waypoints).
CORRIDOR_GEO: dict[str, dict] = {
    "strait_of_hormuz": {
        "category": "sea",
        "centroid": {"lat": 26.5667, "lon": 56.25},
        "waypoints": [[26.0, 52.0], [26.5667, 56.25], [25.5, 58.5]],
    },
    "red_sea_suez": {
        "category": "sea",
        "centroid": {"lat": 20.0, "lon": 38.0},
        "waypoints": [[12.5833, 43.3333], [20.0, 38.0], [30.455, 32.35]],
    },
    "strait_of_malacca": {
        "category": "sea",
        "centroid": {"lat": 2.5, "lon": 101.0},
        "waypoints": [[5.5, 98.5], [2.5, 101.0], [1.3, 103.9]],
    },
    "cape_of_good_hope": {
        "category": "sea",
        "centroid": {"lat": -34.3568, "lon": 18.474},
        "waypoints": [[-20.0, 5.0], [-34.3568, 18.474], [-15.0, 42.0]],
    },
    "danish_straits_baltic": {
        "category": "sea",
        "centroid": {"lat": 55.75, "lon": 12.75},
        "waypoints": [[55.75, 12.75], [57.0, 19.0]],
    },
    "taiwan_south_china_sea": {
        "category": "sea",
        "centroid": {"lat": 12.0, "lon": 114.0},
        "waypoints": [[2.5, 101.0], [12.0, 114.0], [24.0, 119.5]],
    },
    "india_china_lac": {
        "category": "land",
        "centroid": {"lat": 34.1526, "lon": 77.5771},
        "waypoints": [[28.0, 77.0], [34.1526, 77.5771]],
    },
    "india_pakistan_attari": {
        "category": "land",
        "centroid": {"lat": 31.6048, "lon": 74.572},
        "waypoints": [[31.63, 74.87], [31.6048, 74.572]],
    },
    "india_bangladesh_petrapole": {
        "category": "land",
        "centroid": {"lat": 23.05, "lon": 88.83},
        "waypoints": [[22.5, 88.2], [23.05, 88.83]],
    },
    "india_nepal_raxaul": {
        "category": "land",
        "centroid": {"lat": 26.9833, "lon": 84.85},
        "waypoints": [[26.8, 84.7], [26.9833, 84.85]],
    },
    "imec": {
        "category": "strategic",
        "centroid": {"lat": 25.2048, "lon": 55.2708},
        "waypoints": [list(_INDIA_LATLON), [25.2048, 55.2708]],
    },
    "instc_chabahar": {
        "category": "strategic",
        "centroid": {"lat": 25.2919, "lon": 60.643},
        "waypoints": [list(_INDIA_LATLON), [25.2919, 60.643]],
    },
}


def corridor_metadata() -> dict[str, dict]:
    """Static corridor registry for API / dashboard (category + exposure weights)."""
    result: dict[str, dict] = {}
    for corridor_id, spec in CORRIDORS.items():
        geo = CORRIDOR_GEO.get(corridor_id, {})
        entry = {
            "id": corridor_id,
            "name": spec["name"],
            "category": geo.get("category") or CORRIDOR_CATEGORIES.get(corridor_id, "sea"),
            "energy_exposure": spec["energy_exposure"],
            "goods_exposure": spec["goods_exposure"],
            "exposure_source": spec["exposure_source"],
        }
        if geo.get("centroid"):
            entry["centroid"] = geo["centroid"]
        if geo.get("waypoints"):
            entry["waypoints"] = geo["waypoints"]
        result[corridor_id] = entry
    return result
