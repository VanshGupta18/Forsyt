"""Portfolio analyser route: POST /portfolio/analyse"""

import json
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from api.auth import require_api_key
from api.dependencies import get_pg, get_redis
from api.schemas import Holding, PortfolioAnalyseResponse, SectorExposure

logger = logging.getLogger(__name__)
router = APIRouter()

# Fallback sector map embedded in-process (overridden by DB at runtime)
BUILTIN_SECTOR_MAP = {
    "RELIANCE": "Energy",  "ONGC": "Energy",       "COALINDIA": "Energy",
    "HDFCBANK": "Banking", "ICICIBANK": "Banking",  "SBIN": "Banking",
    "KOTAKBANK": "Banking","AXISBANK": "Banking",   "INDUSINDBK": "Banking",
    "INFY": "IT",          "TCS": "IT",             "WIPRO": "IT",
    "HCLTECH": "IT",       "TECHM": "IT",
    "DRREDDY": "Pharma",   "SUNPHARMA": "Pharma",   "CIPLA": "Pharma",
    "DIVISLAB": "Pharma",  "BIOCON": "Pharma",
    "TATASTEEL": "Metal",  "HINDALCO": "Metal",     "JSWSTEEL": "Metal",
    "BHARTIARTL": "Telecom", "IDEA": "Telecom",
    "LT": "Infrastructure","ULTRACEMCO": "Infrastructure",
}


def _get_sector_map(conn) -> dict:
    """Merge DB ticker→sector map over built-in fallback."""
    mapping = dict(BUILTIN_SECTOR_MAP)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT ticker, sector FROM ticker_sector_map")
            for row in cur.fetchall():
                mapping[row["ticker"].upper()] = row["sector"]
    except Exception:
        pass  # DB table may not exist yet, fallback is fine
    return mapping


def _get_gpr_betas(conn) -> dict:
    """Return sector → gpr_beta dict from DB."""
    betas = {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT sector, gpr_beta, computed_date FROM sector_gpr_betas "
                        "ORDER BY computed_date DESC")
            seen = set()
            for row in cur.fetchall():
                if row["sector"] not in seen:
                    betas[row["sector"]] = float(row["gpr_beta"] or 0)
                    seen.add(row["sector"])
    except Exception:
        pass
    return betas


@router.post("/analyse", response_model=PortfolioAnalyseResponse)
async def analyse_portfolio(
    holdings: List[Holding],
    _: str = Depends(require_api_key),
):
    """
    Analyse a portfolio's geopolitical risk exposure.
    - Maps tickers to sectors
    - Looks up OLS-estimated GPR β per sector
    - Returns weighted portfolio GPR risk score
    """
    if not holdings:
        raise HTTPException(status_code=400, detail="holdings list is empty")

    total_weight = sum(h.weight for h in holdings)
    if abs(total_weight - 1.0) > 0.02:
        raise HTTPException(
            status_code=422,
            detail=f"Weights must sum to 1.0 (got {total_weight:.4f})"
        )

    conn = get_pg()
    r    = get_redis()

    sector_map  = _get_sector_map(conn)
    betas       = _get_gpr_betas(conn)

    # Get latest GPR value
    latest_gpr  = None
    gpr_date    = None
    raw         = r.get("india_gpr:latest")
    if raw:
        data      = json.loads(raw)
        latest_gpr = data.get("normalized_gpr")
        gpr_date  = data.get("date")

    # Map tickers → sectors
    sector_weights: dict[str, float] = {}
    unrecognised: List[str] = []
    for holding in holdings:
        t = holding.ticker.upper()
        sector = sector_map.get(t)
        if not sector:
            unrecognised.append(t)
            continue
        sector_weights[sector] = sector_weights.get(sector, 0.0) + holding.weight

    # Build sector breakdown
    breakdown: List[SectorExposure] = []
    portfolio_score = 0.0
    for sector, weight in sorted(sector_weights.items()):
        beta = betas.get(sector)
        risk_contribution = None
        if beta is not None and latest_gpr is not None:
            risk_contribution = weight * beta * latest_gpr
            portfolio_score  += risk_contribution
        breakdown.append(SectorExposure(
            sector             = sector,
            total_weight       = round(weight, 6),
            gpr_beta           = beta,
            risk_contribution  = round(risk_contribution, 6) if risk_contribution else None,
        ))

    # Map score to signal (threshold: z-score > 0 → HIGH_VOL)
    signal = "HIGH_VOL" if portfolio_score > 0 else "LOW_VOL"

    return PortfolioAnalyseResponse(
        portfolio_gpr_score   = round(portfolio_score, 6),
        signal                = signal,
        high_vol_probability  = None,  # full ML inference not called here
        sector_breakdown      = breakdown,
        unrecognised_tickers  = unrecognised,
        gpr_date              = gpr_date,
    )
