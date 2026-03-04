"""Volatility signal route: /signals/latest"""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from api.auth import require_api_key
from api.dependencies import get_pg, get_redis
from api.schemas import VolatilitySignalResponse, ShapDriver

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/latest", response_model=VolatilitySignalResponse)
async def get_signal_latest(_ = Depends(require_api_key)):
    """Return the latest ML volatility signal. Tries Redis first."""
    r = get_redis()
    raw = r.get("volatility_signal:latest")
    if raw:
        data = json.loads(raw)
        data.setdefault("source", "redis")
        # Normalise drivers
        data["top_drivers"] = [ShapDriver(**d) for d in data.get("top_drivers", [])]
        return VolatilitySignalResponse(**data)

    # Fallback to PostgreSQL
    conn = get_pg()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT prediction_date, signal, high_vol_probability,
                   model_version, top_features
            FROM ml_predictions
            ORDER BY prediction_date DESC
            LIMIT 1
        """)
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="No signal available yet")

    drivers = [ShapDriver(**d) for d in (row["top_features"] or [])]
    return VolatilitySignalResponse(
        signal               = row["signal"],
        high_vol_probability = row["high_vol_probability"],
        model_version        = row["model_version"],
        inference_date       = row["prediction_date"],
        top_drivers          = drivers,
        source               = "postgres",
    )
