"""
Shared FastAPI dependencies: PostgreSQL and Redis connection helpers.
Connections are created once per process (module-level singletons).
"""

import os
import logging
import psycopg2
import redis
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

PG_DSN     = os.getenv("PG_DSN",     "postgresql://india_ai:secret@localhost:5432/india_ai_gpr")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Module-level singletons — one connection per FastAPI worker process
_pg_conn:    psycopg2.extensions.connection = None
_redis_conn: redis.Redis = None


def get_pg() -> psycopg2.extensions.connection:
    """Return a live PostgreSQL connection, reconnecting if closed."""
    global _pg_conn
    if _pg_conn is None or _pg_conn.closed:
        logger.info("Opening PostgreSQL connection")
        _pg_conn = psycopg2.connect(PG_DSN, cursor_factory=RealDictCursor)
    return _pg_conn


def get_redis() -> redis.Redis:
    """Return a live Redis client, reconnecting if needed."""
    global _redis_conn
    if _redis_conn is None:
        logger.info("Opening Redis connection")
        _redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT,
                                  decode_responses=True)
    return _redis_conn


def close_all():
    """Called on app shutdown."""
    global _pg_conn, _redis_conn
    if _pg_conn and not _pg_conn.closed:
        _pg_conn.close()
    if _redis_conn:
        _redis_conn.close()
