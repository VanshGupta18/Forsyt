"""Free, open country context for the country card: reference facts + macro.

All from the World Bank open API (no key), plus a flag emoji derived from the
ISO2 code with no network call at all:
- Facts:  capital, region, income level, population, flag.
- Macro:  GDP growth, CPI inflation, unemployment.

Both are best-effort and cached hard: any network/parse error returns None so the
card renders without them. Keyed by ISO2 (from countries.py). Not India-relative
— pure context alongside the bilateral score.
"""
from __future__ import annotations

import logging

import requests

from news_dataset.api.cache import _MISSING, cache_get, cache_set

logger = logging.getLogger(__name__)
TTL = 24 * 3600  # reference/macro data changes slowly
TIMEOUT = 6

# World Bank indicator codes -> field name
_WB_INDICATORS = {
    "gdp_growth_pct": "NY.GDP.MKTP.KD.ZG",
    "inflation_pct": "FP.CPI.TOTL.ZG",
    "unemployment_pct": "SL.UEM.TOTL.ZS",
}


def _get(url: str, **kw):
    r = requests.get(url, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r.json()


def _flag_emoji(iso2: str) -> str | None:
    """Regional-indicator flag emoji from an ISO2 code — pure, no network."""
    if not iso2 or len(iso2) != 2 or not iso2.isalpha():
        return None
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso2.upper())


def country_facts(iso2: str) -> dict | None:
    key = f"facts:{iso2}"
    hit = cache_get(key, ttl_seconds=TTL)
    if hit is not _MISSING:
        return hit
    facts: dict = {"flag": _flag_emoji(iso2)}  # flag always works (no network)
    try:
        data = _get(f"https://api.worldbank.org/v2/country/{iso2}?format=json")
        c = data[1][0] if isinstance(data, list) and len(data) > 1 and data[1] else {}
        facts["capital"] = c.get("capitalCity") or None
        facts["region"] = (c.get("region") or {}).get("value")
        facts["income_level"] = (c.get("incomeLevel") or {}).get("value")
    except Exception:
        logger.warning("country_facts metadata failed for %s", iso2, exc_info=True)
    try:
        pop = _get(
            f"https://api.worldbank.org/v2/country/{iso2}/indicator/SP.POP.TOTL"
            "?format=json&mrv=1"
        )
        rows = pop[1] if isinstance(pop, list) and len(pop) > 1 else []
        facts["population"] = rows[0].get("value") if rows else None
    except Exception:
        logger.warning("country_facts population failed for %s", iso2, exc_info=True)
    cache_set(key, facts)
    return facts


_PORTWATCH = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/"
    "PortWatch_ports_database/FeatureServer/0/query"
)
_OWID_ENERGY = "https://ourworldindata.org/grapher/share-elec-by-source.csv"
_ENERGY_SOURCES = ["Coal", "Gas", "Hydropower", "Solar", "Wind", "Oil", "Nuclear",
                   "Other renewables", "Bioenergy"]


def country_ports(iso3: str) -> list[dict] | None:
    """Top maritime ports (by vessel count) for a country, from IMF PortWatch."""
    key = f"ports:{iso3}"
    hit = cache_get(key, ttl_seconds=TTL)
    if hit is not _MISSING:
        return hit
    ports = None
    try:
        data = _get(_PORTWATCH, params={
            "where": f"ISO3='{iso3}'", "outFields":
            "portname,vessel_count_total,vessel_count_tanker,vessel_count_container,"
            "share_country_maritime_import,share_country_maritime_export,industry_top1",
            "f": "json", "returnGeometry": "false",
            "orderByFields": "vessel_count_total DESC", "resultRecordCount": 6,
        })
        feats = data.get("features", [])
        ports = [
            {
                "name": a.get("portname"),
                "vessels": a.get("vessel_count_total"),
                "tankers": a.get("vessel_count_tanker"),
                "containers": a.get("vessel_count_container"),
                "import_share": _pct(a.get("share_country_maritime_import")),
                "export_share": _pct(a.get("share_country_maritime_export")),
                "top_industry": a.get("industry_top1"),
            }
            for f in feats if (a := f.get("attributes"))
        ] or None
    except Exception:
        logger.warning("country_ports failed for %s", iso3, exc_info=True)
    cache_set(key, ports)
    return ports


def _pct(v):
    # PortWatch share fields are already percentages (e.g. 9.67 = 9.67%).
    try:
        return round(float(v), 1) if v is not None else None
    except (TypeError, ValueError):
        return None


# Module-level cache of the full OWID energy frame (all countries, ~560KB).
_OWID_CACHE: dict = {}


def country_energy(iso3: str) -> dict | None:
    """Latest electricity generation mix (% by source) for a country, from OWID/Ember."""
    key = f"energy:{iso3}"
    hit = cache_get(key, ttl_seconds=TTL)
    if hit is not _MISSING:
        return hit
    energy = None
    try:
        import io

        import pandas as pd
        if "df" not in _OWID_CACHE or (_OWID_CACHE.get("t", 0) < __import__("time").time() - TTL):
            r = requests.get(_OWID_ENERGY, timeout=15, headers={"User-Agent": "forsyt"})
            r.raise_for_status()
            _OWID_CACHE["df"] = pd.read_csv(io.StringIO(r.text))
            _OWID_CACHE["t"] = __import__("time").time()
        df = _OWID_CACHE["df"]
        rows = df[df["Code"] == iso3]
        if not rows.empty:
            latest = rows.sort_values("Year").iloc[-1]
            mix = {s: round(float(latest[s]), 1) for s in _ENERGY_SOURCES
                   if s in latest and pd.notna(latest[s])}
            fossil = sum(mix.get(s, 0) for s in ("Coal", "Gas", "Oil"))
            renew = sum(mix.get(s, 0) for s in ("Hydropower", "Solar", "Wind",
                                                "Other renewables", "Bioenergy"))
            energy = {
                "year": int(latest["Year"]),
                "mix": mix,
                "fossil_pct": round(fossil, 1),
                "renewable_pct": round(renew, 1),
                "nuclear_pct": mix.get("Nuclear", 0.0),
            }
    except Exception:
        logger.warning("country_energy failed for %s", iso3, exc_info=True)
    cache_set(key, energy)
    return energy


def country_macro(iso2: str) -> dict | None:
    key = f"macro:{iso2}"
    hit = cache_get(key, ttl_seconds=TTL)
    if hit is not _MISSING:
        return hit
    macro: dict = {}
    for field, code in _WB_INDICATORS.items():
        try:
            data = _get(
                f"https://api.worldbank.org/v2/country/{iso2}/indicator/{code}"
                "?format=json&mrv=1"
            )
            rows = data[1] if isinstance(data, list) and len(data) > 1 else []
            val = rows[0].get("value") if rows else None
            if val is not None:
                macro[field] = round(float(val), 1)
                macro[f"{field}_year"] = rows[0].get("date")
        except Exception:
            logger.warning("world bank %s failed for %s", code, iso2, exc_info=True)
    macro = macro or None
    cache_set(key, macro)
    return macro
