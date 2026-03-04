"""
FastAPI application factory.
Mounts all routers, configures rate limiting, CORS, and Prometheus metrics.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator

from api.dependencies import close_all
from api.routes import gpr, signals, events, health, portfolio, corridor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API starting up — connections will be opened on first request")
    yield
    logger.info("API shutting down — closing connections")
    close_all()


def create_app() -> FastAPI:
    app = FastAPI(
        title="India AI-GPR Platform API",
        description=(
            "Real-time Geopolitical Risk Index for India, "
            "ML-based volatility signals, and portfolio exposure analytics."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Prometheus metrics at /metrics
    Instrumentator().instrument(app).expose(app)

    # Routers
    app.include_router(health.router,    tags=["Health"])
    app.include_router(gpr.router,       prefix="/gpr",       tags=["GPR Index"])
    app.include_router(signals.router,   prefix="/signals",   tags=["Signals"])
    app.include_router(events.router,    prefix="/events",    tags=["Events"])
    app.include_router(portfolio.router, prefix="/portfolio", tags=["Portfolio"])
    app.include_router(corridor.router,  prefix="/trade",     tags=["Trade Corridors"])

    @app.exception_handler(Exception)
    async def generic_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled error on {request.url.path}: {exc}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app


app = create_app()
