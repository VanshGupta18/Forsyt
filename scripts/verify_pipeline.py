"""
End-to-end pipeline verification.
Run after setup to confirm all components are healthy.

Usage:
    python scripts/verify_pipeline.py
"""

import os
import sys
import json
import logging
import datetime
import requests
import psycopg2
import redis

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

PG_DSN     = os.getenv("PG_DSN",      "postgresql://india_ai:secret@localhost:5432/india_ai_gpr")
REDIS_HOST = os.getenv("REDIS_HOST",  "localhost")
API_URL    = os.getenv("API_URL",     "http://localhost:8000")
API_KEY    = os.getenv("API_KEY",     "dev_key")

PASS_SYMBOL = "✅"
FAIL_SYMBOL = "❌"
results = []


def check(name: str, fn):
    try:
        fn()
        logger.info(f"{PASS_SYMBOL} {name}")
        results.append((name, True))
    except Exception as e:
        logger.error(f"{FAIL_SYMBOL} {name}: {e}")
        results.append((name, False))


def check_postgres():
    conn = psycopg2.connect(PG_DSN)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM gpr_index")
        n = cur.fetchone()[0]
    conn.close()
    assert n >= 0, "Could not query gpr_index"


def check_redis():
    r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    assert r.ping(), "Redis PING failed"
    r.close()


def check_api_health():
    resp = requests.get(f"{API_URL}/health", timeout=10)
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert data["status"] in ("ok", "degraded"), f"Unexpected status: {data['status']}"


def check_gpr_endpoint():
    resp = requests.get(
        f"{API_URL}/gpr/latest",
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=10,
    )
    assert resp.status_code in (200, 404), f"HTTP {resp.status_code}"


def check_signal_endpoint():
    resp = requests.get(
        f"{API_URL}/signals/latest",
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=10,
    )
    assert resp.status_code in (200, 404), f"HTTP {resp.status_code}"


def check_portfolio_endpoint():
    payload = [
        {"ticker": "INFY",     "weight": 0.30},
        {"ticker": "HDFCBANK", "weight": 0.40},
        {"ticker": "RELIANCE", "weight": 0.30},
    ]
    resp = requests.post(
        f"{API_URL}/portfolio/analyse",
        json=payload,
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=10,
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "sector_breakdown" in data


def check_raw_articles_table():
    conn = psycopg2.connect(PG_DSN)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM raw_articles")
        n = cur.fetchone()[0]
    conn.close()
    logger.info(f"  raw_articles rows: {n}")


def check_structured_events_table():
    conn = psycopg2.connect(PG_DSN)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM structured_events")
        n = cur.fetchone()[0]
    conn.close()
    logger.info(f"  structured_events rows: {n}")


def main():
    print("\n===  India AI-GPR Platform — Pipeline Verification  ===\n")

    check("PostgreSQL connectivity",         check_postgres)
    check("Redis connectivity",              check_redis)
    check("API /health endpoint",            check_api_health)
    check("API /gpr/latest endpoint",        check_gpr_endpoint)
    check("API /signals/latest endpoint",    check_signal_endpoint)
    check("API /portfolio/analyse endpoint", check_portfolio_endpoint)
    check("raw_articles table",              check_raw_articles_table)
    check("structured_events table",         check_structured_events_table)

    passed = sum(1 for _, ok in results if ok)
    total  = len(results)
    print(f"\n===  Results: {passed}/{total} checks passed  ===\n")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
