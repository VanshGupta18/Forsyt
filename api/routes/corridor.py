"""
Corridor risk route: GET /corridor-risk
Returns India-specific geopolitical risk for a given trade partner country.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Query
from api.schemas import CorridorRiskResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Static corridor database — updated quarterly via scripts/update_corridors.py
# GPR scores here are India-centric (risk TO India's trade, not global risk of country)
CORRIDOR_DATA = {
    "china": {
        "country": "China", "iso": "CHN",
        "gpr": 2.8, "sanctions": True, "sanctions_type": "Partial (tech/defence)",
        "trade_volume_bn": 136.2, "trade_rank": 1,
        "primary_exports": ["Iron ore", "Cotton", "Organic chemicals"],
        "primary_imports": ["Electronics", "Machinery", "Plastics"],
        "risk_level": "HIGH",
        "risk_drivers": ["LAC border tensions", "Tech decoupling pressure", "QUAD dynamics"],
        "sectors_exposed": ["IT", "Electronics", "Manufacturing"],
        "corridor_note": "India's largest trade partner. Dual-use tech restrictions active. Border incidents cause supply shock spikes.",
    },
    "usa": {
        "country": "USA", "iso": "USA",
        "gpr": 1.2, "sanctions": False, "sanctions_type": "None",
        "trade_volume_bn": 120.0, "trade_rank": 2,
        "primary_exports": ["Pharma", "IT services", "Gems"],
        "primary_imports": ["Aircraft", "Machinery", "Electronic components"],
        "risk_level": "LOW",
        "risk_drivers": ["H-1B visa policy", "Pharma pricing pressure"],
        "sectors_exposed": ["IT", "Pharma"],
        "corridor_note": "Largest export destination. I2U2 and iCET frameworks reduce strategic risk. Main risk is policy/regulatory.",
    },
    "uae": {
        "country": "UAE", "iso": "ARE",
        "gpr": 0.8, "sanctions": False, "sanctions_type": "None",
        "trade_volume_bn": 84.5, "trade_rank": 3,
        "primary_exports": ["Gems", "Machinery", "Food"],
        "primary_imports": ["Gold", "Petroleum products", "Plastics"],
        "risk_level": "LOW",
        "risk_drivers": ["Regional Gulf tensions (indirect)"],
        "sectors_exposed": ["Gems & Jewellery", "Food exports"],
        "corridor_note": "CEPA signed 2022. Stable corridor. Large Indian diaspora creates political stability incentive.",
    },
    "russia": {
        "country": "Russia", "iso": "RUS",
        "gpr": 3.6, "sanctions": True, "sanctions_type": "Western secondary sanctions",
        "trade_volume_bn": 65.7, "trade_rank": 4,
        "primary_exports": ["Pharma", "Tea", "Machinery"],
        "primary_imports": ["Crude oil", "Defence equipment", "Fertilisers"],
        "risk_level": "HIGH",
        "risk_drivers": ["Ukraine war sanctions", "USD payment restrictions", "SWIFT exclusion"],
        "sectors_exposed": ["Energy", "Defence", "Fertilisers"],
        "corridor_note": "India imports ~35% of crude from Russia post-2022. US secondary sanctions create payment risk. Rupee-Rouble mechanism partially active.",
    },
    "saudi arabia": {
        "country": "Saudi Arabia", "iso": "SAU",
        "gpr": 1.4, "sanctions": False, "sanctions_type": "None",
        "trade_volume_bn": 52.8, "trade_rank": 5,
        "primary_exports": ["Rice", "Machinery", "Vehicles"],
        "primary_imports": ["Crude oil", "LPG", "Petrochemicals"],
        "risk_level": "MEDIUM",
        "risk_drivers": ["OPEC+ production cuts", "Yemen conflict spillover", "India-KSA labour issues"],
        "sectors_exposed": ["Energy", "Petrochemicals"],
        "corridor_note": "~18% of India's crude imports. OPEC+ decisions directly affect India's import bill and INR.",
    },
    "iraq": {
        "country": "Iraq", "iso": "IRQ",
        "gpr": 2.4, "sanctions": False, "sanctions_type": "Partial (legacy)",
        "trade_volume_bn": 34.0, "trade_rank": 6,
        "primary_exports": ["Pharma", "Rice"],
        "primary_imports": ["Crude oil"],
        "risk_level": "MEDIUM",
        "risk_drivers": ["Internal instability", "Iran-Iraq proxy dynamics", "Kirkuk field disruptions"],
        "sectors_exposed": ["Energy"],
        "corridor_note": "Second-largest crude supplier. Supply disruptions common but India has diversified sufficiently.",
    },
    "iran": {
        "country": "Iran", "iso": "IRN",
        "gpr": 3.2, "sanctions": True, "sanctions_type": "US secondary sanctions (active)",
        "trade_volume_bn": 8.2, "trade_rank": 12,
        "primary_exports": ["Rice", "Tea"],
        "primary_imports": ["Crude oil (reduced)"],
        "risk_level": "HIGH",
        "risk_drivers": ["US CAATSA sanctions", "Chabahar port exceptions", "Nuclear deal uncertainty"],
        "sectors_exposed": ["Energy", "Connectivity (Chabahar)"],
        "corridor_note": "Chabahar port is strategic for Central Asia access. India navigates sanctions via waivers but risk of snapback is real.",
    },
    "germany": {
        "country": "Germany", "iso": "DEU",
        "gpr": 0.6, "sanctions": False, "sanctions_type": "None",
        "trade_volume_bn": 30.1, "trade_rank": 7,
        "primary_exports": ["Pharma", "Organic chemicals", "Machinery"],
        "primary_imports": ["Machinery", "Chemicals", "Vehicles"],
        "risk_level": "LOW",
        "risk_drivers": ["EU regulatory compliance"],
        "sectors_exposed": ["Auto", "Chemicals"],
        "corridor_note": "India's largest EU trade partner. Germany-India strategic partnership stable. EUDR/CBAM indirect risk for Indian exporters.",
    },
    "pakistan": {
        "country": "Pakistan", "iso": "PAK",
        "gpr": 3.8, "sanctions": False, "sanctions_type": "None",
        "trade_volume_bn": 0.9, "trade_rank": 20,
        "primary_exports": ["Minimal (informal)"],
        "primary_imports": ["Minimal"],
        "risk_level": "HIGH",
        "risk_drivers": ["LoC tensions", "Cross-border terrorism", "Nuclear posturing"],
        "sectors_exposed": ["None (near-zero formal trade)"],
        "corridor_note": "Highest GPR of any partner but near-zero formal trade since 2019 MFN revocation. Risk is geopolitical contagion to markets, not direct supply chain.",
    },
    "bangladesh": {
        "country": "Bangladesh", "iso": "BGD",
        "gpr": 1.3, "sanctions": False, "sanctions_type": "None",
        "trade_volume_bn": 14.0, "trade_rank": 9,
        "primary_exports": ["Cotton", "Machinery", "Vehicles"],
        "primary_imports": ["Garments (re-export)"],
        "risk_level": "LOW",
        "risk_drivers": ["Political transition risk (post-2024 elections)"],
        "sectors_exposed": ["Textiles", "Infrastructure"],
        "corridor_note": "India is Bangladesh's largest import source. Growing connectivity via rail/road. Political instability risk post-Hasina era.",
    },
    "singapore": {
        "country": "Singapore", "iso": "SGP",
        "gpr": 0.4, "sanctions": False, "sanctions_type": "None",
        "trade_volume_bn": 35.6, "trade_rank": 8,
        "primary_exports": ["Refined petroleum", "Pharma", "Gold"],
        "primary_imports": ["Refined petroleum", "Electronic components"],
        "risk_level": "LOW",
        "risk_drivers": ["South China Sea spillover (indirect)"],
        "sectors_exposed": ["Financial services", "Petroleum"],
        "corridor_note": "Financial hub and re-export centre. Extremely stable. South China Sea tensions have minor indirect impact.",
    },
    "australia": {
        "country": "Australia", "iso": "AUS",
        "gpr": 0.5, "sanctions": False, "sanctions_type": "None",
        "trade_volume_bn": 25.1, "trade_rank": 10,
        "primary_exports": ["Pharma", "Gems", "IT services"],
        "primary_imports": ["Coal", "Gold", "Copper ore"],
        "risk_level": "LOW",
        "risk_drivers": ["China-Australia tensions (indirect coal pricing effect)"],
        "sectors_exposed": ["Energy", "Mining"],
        "corridor_note": "Australia-India ECTA signed 2022. Coal and critical minerals corridor growing post-QUAD alignment.",
    },
    "south korea": {
        "country": "South Korea", "iso": "KOR",
        "gpr": 1.1, "sanctions": False, "sanctions_type": "None",
        "trade_volume_bn": 28.3, "trade_rank": 11,
        "primary_exports": ["Petroleum products", "Organic chemicals"],
        "primary_imports": ["Electronics", "Machinery", "Steel"],
        "risk_level": "LOW",
        "risk_drivers": ["North Korea missile tests (market shock risk)"],
        "sectors_exposed": ["Electronics", "Steel"],
        "corridor_note": "CEPA in force. North Korea risk creates episodic market volatility but supply chains stable.",
    },
    "japan": {
        "country": "Japan", "iso": "JPN",
        "gpr": 0.7, "sanctions": False, "sanctions_type": "None",
        "trade_volume_bn": 22.4, "trade_rank": 13,
        "primary_exports": ["Petroleum products", "Gems", "Pharma"],
        "primary_imports": ["Machinery", "Electronic components", "Steel"],
        "risk_level": "LOW",
        "risk_drivers": ["Japan-China East China Sea tension (indirect)"],
        "sectors_exposed": ["Auto", "Electronics"],
        "corridor_note": "Japan is India's third-largest FDI source. Quad partnership deepens strategic bond. Auto sector deeply integrated.",
    },
    "nepal": {
        "country": "Nepal", "iso": "NPL",
        "gpr": 0.9, "sanctions": False, "sanctions_type": "None",
        "trade_volume_bn": 8.1, "trade_rank": 15,
        "primary_exports": ["Petroleum", "Vehicles", "Machinery"],
        "primary_imports": ["Cardamom", "Polyester yarn"],
        "risk_level": "LOW",
        "risk_drivers": ["China BRI presence in Nepal", "Periodic border trade disruptions"],
        "sectors_exposed": ["Energy (hydropower)"],
        "corridor_note": "Open border — unique trade relationship. India supplies nearly all petroleum. China influence via BRI is key geopolitical variable.",
    },
}

# Sector → exposed countries mapping (for reverse lookup)
SECTOR_EXPOSURE = {
    "Energy":       ["russia", "saudi arabia", "iraq", "iran"],
    "IT":           ["usa", "china"],
    "Pharma":       ["usa", "germany"],
    "Electronics":  ["china", "south korea", "japan"],
    "Defence":      ["russia"],
    "Fertilisers":  ["russia"],
    "Auto":         ["germany", "japan", "south korea"],
    "Textiles":     ["bangladesh", "china"],
    "Mining":       ["australia"],
}


@router.get("/corridor-risk", response_model=CorridorRiskResponse)
async def get_corridor_risk(
    country: str = Query(..., description="Country name, e.g. 'Russia'"),
):
    """
    Return India-centric geopolitical risk for a specific trade corridor.
    No auth required — public endpoint for broad adoption.
    """
    key = country.lower().strip()
    data = CORRIDOR_DATA.get(key)
    if not data:
        # Fuzzy match — find closest
        matches = [k for k in CORRIDOR_DATA if key in k or k in key]
        if matches:
            data = CORRIDOR_DATA[matches[0]]
        else:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=404,
                detail=f"Country '{country}' not found. Available: {list(CORRIDOR_DATA.keys())}"
            )
    return CorridorRiskResponse(**data)


@router.get("/corridor-risk/all")
async def get_all_corridors():
    """Return summary list of all tracked corridors (no auth required)."""
    return [
        {
            "country":          v["country"],
            "iso":              v["iso"],
            "gpr":              v["gpr"],
            "risk_level":       v["risk_level"],
            "sanctions":        v["sanctions"],
            "trade_volume_bn":  v["trade_volume_bn"],
            "trade_rank":       v["trade_rank"],
        }
        for v in sorted(CORRIDOR_DATA.values(), key=lambda x: x["trade_rank"])
    ]


@router.get("/corridor-risk/by-sector")
async def get_corridors_by_sector(
    sector: str = Query(..., description="e.g. 'Energy', 'IT', 'Pharma'"),
):
    """Return all corridors that expose a given sector."""
    sector_key = sector.strip().title()
    countries  = SECTOR_EXPOSURE.get(sector_key, [])
    if not countries:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f"Sector '{sector}' not found. Available: {list(SECTOR_EXPOSURE.keys())}"
        )
    return {
        "sector":   sector_key,
        "corridors": [
            {
                "country":    CORRIDOR_DATA[c]["country"],
                "gpr":        CORRIDOR_DATA[c]["gpr"],
                "risk_level": CORRIDOR_DATA[c]["risk_level"],
                "sanctions":  CORRIDOR_DATA[c]["sanctions"],
            }
            for c in countries if c in CORRIDOR_DATA
        ],
    }
