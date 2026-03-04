"""Events route: GET /events/"""

import logging
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from api.auth import require_api_key
from api.dependencies import get_pg
from api.schemas import EventsResponse, EventInDB

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=EventsResponse)
async def list_events(
    query_date:     Optional[date]  = Query(default=None),
    min_severity:   float           = Query(default=0.0, ge=0.0, le=1.0),
    min_confidence: float           = Query(default=0.0, ge=0.0, le=1.0),
    limit:          int             = Query(default=50,  ge=1, le=500),
    _               = Depends(require_api_key),
):
    """
    Return structured GPR events.
    Filterable by date, minimum severity, and minimum confidence.
    """
    conn = get_pg()
    params = [min_severity, min_confidence]
    sql = """
        SELECT id AS event_id, article_id, event_type,
               severity, india_exposure, confidence,
               event_date, raw_text, created_at
        FROM structured_events
        WHERE severity   >= %s
          AND confidence >= %s
    """
    if query_date:
        sql += " AND event_date = %s"
        params.append(query_date)

    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    events = [EventInDB(**dict(r)) for r in rows]
    return EventsResponse(query_date=query_date, count=len(events), events=events)
