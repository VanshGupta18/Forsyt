"""GPR index routes: /gpr/latest and /gpr/history"""

import json
import logging
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from api.auth import require_api_key
from api.dependencies import get_pg, get_redis
from api.schemas import GPRLatestResponse, GPRHistoryResponse, GPRPoint

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_HISTORY_DAYS = 5 * 365  # 5 years


@router.get("/latest", response_model=GPRLatestResponse)
async def get_gpr_latest(_ = Depends(require_api_key)):
    """Return the most recent GPR index value. Tries Redis first, falls back to PostgreSQL."""
    r = get_redis()
    raw = r.get("india_gpr:latest")
    if raw:
        data = json.loads(raw)
        data["source"] = "redis"
        return GPRLatestResponse(**data)

    # Fallback to PostgreSQL
    conn = get_pg()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT index_date, raw_gpr, normalized_gpr, data_quality_flag, created_at
            FROM gpr_index
            WHERE normalized_gpr IS NOT NULL
            ORDER BY index_date DESC
            LIMIT 1
        """)
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="No GPR data available yet")

    return GPRLatestResponse(
        date             = row["index_date"],
        normalized_gpr   = row["normalized_gpr"],
        raw_gpr          = row["raw_gpr"],
        data_quality_flag= row["data_quality_flag"],
        source           = "postgres",
        updated_at       = row["created_at"],
    )


@router.get("/history", response_model=GPRHistoryResponse)
async def get_gpr_history(
    from_date: date = Query(default=date.today() - timedelta(days=90)),
    to_date:   date = Query(default=date.today()),
    _          = Depends(require_api_key),
):
    """Return GPR time series. Maximum window is 5 years."""
    if (to_date - from_date).days > MAX_HISTORY_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Date range exceeds maximum of {MAX_HISTORY_DAYS} days"
        )
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="from_date must be <= to_date")

    conn = get_pg()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT index_date, raw_gpr, normalized_gpr, data_quality_flag,
                   event_count
            FROM gpr_index
            WHERE index_date BETWEEN %s AND %s
            ORDER BY index_date
        """, (from_date, to_date))
        rows = cur.fetchall()

    series = [
        GPRPoint(
            date               = r["index_date"],
            raw_gpr            = r["raw_gpr"],
            normalized_gpr     = r["normalized_gpr"],
            data_quality_flag  = r["data_quality_flag"],
            event_count        = r["event_count"] or 0,
        ) for r in rows
    ]
    return GPRHistoryResponse(
        from_date=from_date, to_date=to_date,
        count=len(series), series=series
    )
