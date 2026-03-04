# Module 4 — API Gateway
## Step-by-Step Build Guide

---

## What This Module Does
Exposes all platform data through a production-grade FastAPI REST API. Sits behind an Nginx reverse proxy with TLS. Serves cached data from Redis (hot path, < 5ms) with PostgreSQL fallback. Includes API key authentication, rate limiting, and Prometheus instrumentation.

---

## Prerequisites
- Modules 1, 2, and 3 must be operational (data must exist in Redis / PostgreSQL)
- Python packages:

```bash
pip install \
  fastapi uvicorn[standard] pydantic \
  psycopg2-binary redis \
  slowapi \
  prometheus-fastapi-instrumentator \
  python-dotenv httpx
```

---

## Step 1 — Response Schemas (`api/schemas.py`)

All API responses are typed with Pydantic. Never return raw database rows.

```python
# api/schemas.py

from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime


# ── Shared ───────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


# ── GPR Index ─────────────────────────────────────────────────────────────────

class GPRPoint(BaseModel):
    """Single GPR data point."""
    date: date
    normalized_gpr: float
    smoothed_gpr: Optional[float] = None
    data_quality: str       # "OK", "BLACKOUT", "CARRIED_FORWARD"


class GPRLatestResponse(BaseModel):
    index_date: date
    normalized_gpr: float
    smoothed_gpr: Optional[float]
    percentile_rank: Optional[float]    # 0–100, where 100 = highest risk ever
    data_quality: str
    retrieved_from: str                 # "cache" or "database"
    cached_at: Optional[datetime] = None


class GPRHistoryResponse(BaseModel):
    start_date: date
    end_date: date
    count: int
    series: List[GPRPoint]


# ── ML Volatility Signal ──────────────────────────────────────────────────────

class ShapDriver(BaseModel):
    """One SHAP explanation entry."""
    feature: str
    shap_value: float
    feature_value: float


class VolatilitySignalResponse(BaseModel):
    prediction_date: date
    regime: str                        # "HIGH_VOL" or "NORMAL"
    probability_high_vol: float        # 0.0 – 1.0
    top_drivers: List[ShapDriver]      # Always exactly 3 entries
    model_version: str
    predicted_at: datetime
    retrieved_from: str                # "cache" or "database"


# ── Events ───────────────────────────────────────────────────────────────────

class EventInDB(BaseModel):
    event_id: int
    source_url: str
    headline: Optional[str] = None
    event_type: str
    severity: float
    india_exposure: float
    confidence: float
    actors: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    summary: Optional[str] = None
    published_at: Optional[datetime] = None
    extracted_at: datetime


class EventsResponse(BaseModel):
    query_date: date
    count: int
    events: List[EventInDB]


# ── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str        # "ok" or "degraded"
    postgres: str      # "ok" or "error"
    redis: str         # "ok" or "error"
    latest_gpr_date: Optional[date] = None
    latest_signal_date: Optional[date] = None
```

---

## Step 2 — Auth Middleware (`api/auth.py`)

```python
# api/auth.py

import os
import hashlib
import logging
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# Header name clients must use: Authorization: Bearer <key>
# Also accept X-API-Key header for convenience
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _load_valid_keys() -> set:
    """
    Load API keys from environment variable.
    INDIA_GPR_API_KEYS should be a comma-separated list of SHA-256 hashed keys.
    Storing hashes, not plaintext — even if env is exposed, keys are safe.
    """
    raw = os.environ.get("INDIA_GPR_API_KEYS", "")
    if not raw:
        # Dev mode: allow a default insecure key
        if os.environ.get("APP_ENV") == "development":
            logger.warning("No API keys configured — running in DEV mode with permissive auth")
            return {"dev-key-insecure"}
        raise ValueError("INDIA_GPR_API_KEYS environment variable is required in production")
    return set(raw.strip().split(","))


VALID_KEY_HASHES = _load_valid_keys()


async def require_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Dependency that verifies the API key in X-API-Key header.
    Returns the key hash on success; raises 403 on failure.
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing X-API-Key header"
        )
    
    # Compare SHA-256 hash of submitted key against stored hashes
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    if os.environ.get("APP_ENV") == "development" and api_key == "dev-key-insecure":
        return api_key   # Dev passthrough
    
    if key_hash not in VALID_KEY_HASHES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
    
    return key_hash
```

---

## Step 3 — Shared DB/Redis Connection Helpers (`api/dependencies.py`)

```python
# api/dependencies.py

import os
import json
import psycopg2
import psycopg2.extras
import redis as redis_lib
from psycopg2.extras import RealDictCursor

# Module-level connection pools (created once at startup)
_pg_conn  = None
_redis    = None


def get_pg():
    """Get or create PostgreSQL connection (module-level singleton)."""
    global _pg_conn
    if _pg_conn is None or _pg_conn.closed:
        _pg_conn = psycopg2.connect(
            host=os.environ['POSTGRES_HOST'],
            dbname=os.environ['POSTGRES_DB'],
            user=os.environ['POSTGRES_USER'],
            password=os.environ['POSTGRES_PASSWORD'],
            cursor_factory=RealDictCursor
        )
    return _pg_conn


def get_redis():
    """Get or create Redis connection."""
    global _redis
    if _redis is None:
        _redis = redis_lib.Redis(
            host=os.environ['REDIS_HOST'],
            port=int(os.environ.get('REDIS_PORT', 6379)),
            decode_responses=True
        )
    return _redis
```

---

## Step 4 — Route: GPR Index (`api/routes/gpr.py`)

```python
# api/routes/gpr.py

import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from api.schemas import GPRLatestResponse, GPRHistoryResponse, GPRPoint
from api.auth import require_api_key
from api.dependencies import get_pg, get_redis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gpr", tags=["GPR Index"])


@router.get(
    "/latest",
    response_model=GPRLatestResponse,
    summary="Get the most recent GPR index value",
    description=(
        "Returns today's India AI-GPR index. Served from Redis cache "
        "(< 5ms). Cache refreshed daily at ~20:30 IST after market close."
    )
)
async def get_gpr_latest(
    _key: str = Depends(require_api_key)
):
    r  = get_redis()
    pg = get_pg()
    
    # Try Redis cache first
    cached = r.get("india_gpr:latest")
    if cached:
        data = json.loads(cached)
        data["retrieved_from"] = "cache"
        return GPRLatestResponse(**data)
    
    # Fallback to PostgreSQL
    logger.info("Cache miss on india_gpr:latest — querying PostgreSQL")
    cur = pg.cursor()
    cur.execute("""
        SELECT 
            index_date,
            normalized_gpr,
            smoothed_gpr,
            data_quality_flag AS data_quality,
            PERCENT_RANK() OVER (ORDER BY normalized_gpr) * 100 AS percentile_rank
        FROM gpr_index
        WHERE normalized_gpr IS NOT NULL
        ORDER BY index_date DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    
    if row is None:
        raise HTTPException(status_code=503, detail="No GPR data available — check ingestion pipeline")
    
    return GPRLatestResponse(
        index_date     = row['index_date'],
        normalized_gpr = float(row['normalized_gpr']),
        smoothed_gpr   = float(row['smoothed_gpr']) if row['smoothed_gpr'] else None,
        percentile_rank = float(row['percentile_rank']) if row['percentile_rank'] else None,
        data_quality   = row['data_quality'] or "OK",
        retrieved_from = "database"
    )


@router.get(
    "/history",
    response_model=GPRHistoryResponse,
    summary="Get GPR time series for a date range"
)
async def get_gpr_history(
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end:   date = Query(default=None, description="End date (YYYY-MM-DD). Defaults to today."),
    _key: str = Depends(require_api_key)
):
    if end is None:
        end = date.today()
    
    if start > end:
        raise HTTPException(status_code=400, detail="start must be before end")
    
    if (end - start).days > 365 * 5:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 5 years per request")
    
    pg = get_pg()
    cur = pg.cursor()
    cur.execute("""
        SELECT 
            index_date         AS date,
            normalized_gpr,
            smoothed_gpr,
            COALESCE(data_quality_flag, 'OK') AS data_quality
        FROM gpr_index
        WHERE index_date BETWEEN %s AND %s
          AND normalized_gpr IS NOT NULL
        ORDER BY index_date ASC
    """, (start, end))
    
    rows = cur.fetchall()
    
    return GPRHistoryResponse(
        start_date = start,
        end_date   = end,
        count      = len(rows),
        series     = [
            GPRPoint(
                date           = r['date'],
                normalized_gpr = float(r['normalized_gpr']),
                smoothed_gpr   = float(r['smoothed_gpr']) if r['smoothed_gpr'] else None,
                data_quality   = r['data_quality']
            )
            for r in rows
        ]
    )
```

---

## Step 5 — Route: Volatility Signal (`api/routes/signals.py`)

```python
# api/routes/signals.py

import json
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from api.schemas import VolatilitySignalResponse, ShapDriver
from api.auth import require_api_key
from api.dependencies import get_pg, get_redis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/signals", tags=["Volatility Signals"])


@router.get(
    "/latest",
    response_model=VolatilitySignalResponse,
    summary="Get today's ML volatility regime prediction",
    description=(
        "Returns the current Nifty 50 volatility regime prediction "
        "(HIGH_VOL or NORMAL) with probability and top-3 SHAP drivers. "
        "Served from Redis cache (< 5ms)."
    )
)
async def get_latest_signal(
    _key: str = Depends(require_api_key)
):
    r  = get_redis()
    pg = get_pg()
    
    # Try Redis first
    cached = r.get("volatility_signal:latest")
    if cached:
        data = json.loads(cached)
        data['retrieved_from'] = 'cache'
        # Coerce top_drivers to proper Pydantic models
        data['top_drivers'] = [ShapDriver(**d) for d in data['top_drivers']]
        return VolatilitySignalResponse(**data)
    
    # Fallback to database
    logger.info("Cache miss on volatility_signal:latest")
    cur = pg.cursor()
    cur.execute("""
        SELECT prediction_date, regime, prob_high_vol,
               top_drivers, model_version, predicted_at
        FROM ml_predictions
        ORDER BY prediction_date DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    
    if row is None:
        raise HTTPException(
            status_code=503,
            detail="No ML predictions available — check ML inference pipeline"
        )
    
    drivers = [ShapDriver(**d) for d in row['top_drivers']]
    
    return VolatilitySignalResponse(
        prediction_date     = row['prediction_date'],
        regime              = row['regime'],
        probability_high_vol = float(row['prob_high_vol']),
        top_drivers         = drivers,
        model_version       = row['model_version'],
        predicted_at        = row['predicted_at'],
        retrieved_from      = 'database'
    )
```

---

## Step 6 — Route: Events (`api/routes/events.py`)

```python
# api/routes/events.py

import logging
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from api.schemas import EventsResponse, EventInDB
from api.auth import require_api_key
from api.dependencies import get_pg

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["Geopolitical Events"])


@router.get(
    "/",
    response_model=EventsResponse,
    summary="Get extracted geopolitical events for a date"
)
async def get_events_for_date(
    query_date: date = Query(
        default=None, 
        description="Date to fetch events for (YYYY-MM-DD). Defaults to today."
    ),
    min_severity: float = Query(
        default=0.0, ge=0.0, le=1.0,
        description="Minimum severity score filter (0.0–1.0)"
    ),
    min_confidence: float = Query(
        default=0.5, ge=0.0, le=1.0,
        description="Minimum confidence score filter (0.0–1.0)"
    ),
    _key: str = Depends(require_api_key)
):
    if query_date is None:
        query_date = date.today()
    
    pg = get_pg()
    cur = pg.cursor()
    cur.execute("""
        SELECT 
            e.event_id,
            a.source_url,
            a.headline,
            e.event_type,
            e.severity,
            e.india_exposure,
            e.confidence,
            e.actors,
            e.locations,
            e.summary,
            a.published_at,
            e.extracted_at
        FROM structured_events e
        JOIN raw_articles a ON e.article_id = a.article_id
        WHERE a.published_at::date = %s
          AND e.severity    >= %s
          AND e.confidence  >= %s
        ORDER BY e.severity DESC, e.confidence DESC
        LIMIT 100
    """, (query_date, min_severity, min_confidence))
    
    rows = cur.fetchall()
    
    return EventsResponse(
        query_date = query_date,
        count      = len(rows),
        events     = [EventInDB(**dict(r)) for r in rows]
    )
```

---

## Step 7 — Health Route (`api/routes/health.py`)

```python
# api/routes/health.py

from fastapi import APIRouter
from api.schemas import HealthResponse
from api.dependencies import get_pg, get_redis
from datetime import date

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check (no auth required)"
)
async def health_check():
    pg_status    = "ok"
    redis_status = "ok"
    latest_gpr   = None
    latest_signal = None
    
    try:
        pg = get_pg()
        cur = pg.cursor()
        cur.execute("SELECT MAX(index_date) FROM gpr_index")
        row = cur.fetchone()
        if row:
            latest_gpr = row['max']
    except Exception as e:
        pg_status = f"error: {str(e)}"
    
    try:
        r = get_redis()
        r.ping()
        import json
        cached = r.get("volatility_signal:latest")
        if cached:
            data = json.loads(cached)
            latest_signal = data.get('prediction_date')
    except Exception as e:
        redis_status = f"error: {str(e)}"
    
    overall = "ok" if (pg_status == "ok" and redis_status == "ok") else "degraded"
    
    return HealthResponse(
        status             = overall,
        postgres           = pg_status,
        redis              = redis_status,
        latest_gpr_date    = latest_gpr,
        latest_signal_date = latest_signal
    )
```

---

## Step 8 — FastAPI App Factory (`api/main.py`)

```python
# api/main.py

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator

from api.routes import gpr, signals, events, health
from api.dependencies import get_pg, get_redis

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger("api.main")


# ── Rate Limiter ─────────────────────────────────────────────────────────────
# 60 requests per minute per IP — generous for a data API
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


# ── Startup / Shutdown ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm DB and Redis connections on startup."""
    logger.info("API Gateway starting — warming connections...")
    try:
        pg = get_pg()
        pg.cursor().execute("SELECT 1")
        logger.info("PostgreSQL connection: OK")
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")
    
    try:
        r = get_redis()
        r.ping()
        logger.info("Redis connection: OK")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
    
    yield
    
    logger.info("API Gateway shutting down")


# ── App Factory ──────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="India AI-GPR Platform API",
        description=(
            "Real-time India Geopolitical Risk Index and Nifty 50 "
            "volatility regime prediction API. "
            "GPR index updated daily at 20:30 IST. "
            "Authentication: X-API-Key header required."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # CORS (adjust origins for production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],          # Restrict to your domains in prod
        allow_methods=["GET"],
        allow_headers=["*"]
    )
    
    # Generic error handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(exc)}
        )
    
    # Register routes
    app.include_router(health.router)
    app.include_router(gpr.router)
    app.include_router(signals.router)
    app.include_router(events.router)
    
    # Prometheus metrics at /metrics
    Instrumentator().instrument(app).expose(app)
    
    return app


app = create_app()
```

---

## Step 9 — Dockerfile (`api/Dockerfile`)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY api/ ./api/

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

```text
# requirements-api.txt
fastapi==0.111.0
uvicorn[standard]==0.29.0
pydantic==2.7.1
psycopg2-binary==2.9.9
redis==5.0.4
slowapi==0.1.9
prometheus-fastapi-instrumentator==6.4.0
python-dotenv==1.0.1
```

---

## Step 10 — Nginx Reverse Proxy (`nginx/nginx.conf`)

```nginx
# nginx/nginx.conf

worker_processes auto;
events { worker_connections 1024; }

http {
    # ── Rate limiting at Nginx level (defense in depth) ─────────────────────
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=60r/m;

    # ── Upstream FastAPI ─────────────────────────────────────────────────────
    upstream fastapi_upstream {
        server api_gateway:8000;
        keepalive 32;
    }

    server {
        listen 443 ssl;
        server_name api.indiagpr.io;

        ssl_certificate     /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000" always;
        add_header X-Content-Type-Options nosniff;
        add_header X-Frame-Options DENY;

        location / {
            limit_req zone=api_limit burst=20 nodelay;
            
            proxy_pass http://fastapi_upstream;
            proxy_set_header Host              $host;
            proxy_set_header X-Real-IP         $remote_addr;
            proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 30s;
            proxy_connect_timeout 5s;
        }
    }

    # Redirect HTTP → HTTPS
    server {
        listen 80;
        return 301 https://$host$request_uri;
    }
}
```

---

## Step 11 — Run It

```bash
# Start (from project root)
docker compose up --build api_gateway nginx

# Test all endpoints
curl -H "X-API-Key: dev-key-insecure" http://localhost:8000/health

curl -H "X-API-Key: dev-key-insecure" http://localhost:8000/gpr/latest
curl -H "X-API-Key: dev-key-insecure" \
     "http://localhost:8000/gpr/history?start=2024-01-01&end=2024-06-30"

curl -H "X-API-Key: dev-key-insecure" http://localhost:8000/signals/latest
curl -H "X-API-Key: dev-key-insecure" \
     "http://localhost:8000/events/?query_date=2024-10-04&min_severity=0.6"

# Interactive docs
open http://localhost:8000/docs
```

---

## Verification Checklist

- [ ] `GET /health` returns `{"status": "ok"}` (no auth required)
- [ ] `GET /gpr/latest` without API key returns `403 Forbidden`
- [ ] `GET /gpr/latest` with valid key returns `normalized_gpr` value and correct `retrieved_from` field
- [ ] `GET /signals/latest` returns `regime` as either `"HIGH_VOL"` or `"NORMAL"`, never null
- [ ] `top_drivers` array has exactly 3 entries with non-null SHAP values
- [ ] `GET /gpr/history?start=2020-01-01&end=2024-12-31` returns series with correct date ordering
- [ ] Rate limit: send 70 rapid requests → 61st request returns `429 Too Many Requests`
- [ ] Prometheus metrics available at `http://localhost:8000/metrics`
- [ ] Nginx proxies correctly to FastAPI when running via Docker Compose

---

## Common Errors & Fixes

| Error | Cause | Fix |
|---|---|---|
| `422 Unprocessable Entity` on `/gpr/latest` | Schema mismatch (cached Redis JSON format changed) | Clear Redis key and let it regenerate: `redis-cli DEL india_gpr:latest` |
| `503` on `/signals/latest` | Module 3 has not run inference yet | Trigger manually: `python ml_inference/run_daily.py` |
| `Connection refused` to PostgreSQL | pg container not yet healthy | Add `depends_on: postgres: condition: service_healthy` in Docker Compose |
| `RateLimitExceeded` unexpectedly | Multiple services sharing one IP through proxy | Use API key as rate limit key instead of IP: `key_func=lambda r: r.headers.get('X-API-Key')` |
| CORS error from browser | Origin not in allowed list | Update `allow_origins` in `main.py` `CORSMiddleware` config |
