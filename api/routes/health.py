"""Health check route: GET /health (no auth required)"""

import logging
from fastapi import APIRouter
from api.dependencies import get_pg, get_redis
from api.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Returns platform health. No API key required."""
    pg_status    = "ok"
    redis_status = "ok"
    latest_gpr   = None
    latest_sig   = None

    # PostgreSQL check
    try:
        conn = get_pg()
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(index_date) AS d FROM gpr_index")
            row = cur.fetchone()
            latest_gpr = row["d"] if row else None
    except Exception as e:
        pg_status = f"error: {e}"
        logger.error(f"Health PG failure: {e}")

    # Redis check
    try:
        r = get_redis()
        r.ping()
    except Exception as e:
        redis_status = f"error: {e}"
        logger.error(f"Health Redis failure: {e}")

    # Latest signal date from Redis
    try:
        import json
        raw = get_redis().get("volatility_signal:latest")
        if raw:
            data = json.loads(raw)
            from datetime import date
            latest_sig = date.fromisoformat(data.get("inference_date", ""))
    except Exception:
        pass

    overall = "ok" if pg_status == "ok" and redis_status == "ok" else "degraded"
    return HealthResponse(
        status               = overall,
        postgres             = pg_status,
        redis                = redis_status,
        latest_gpr_date      = latest_gpr,
        latest_signal_date   = latest_sig,
    )
