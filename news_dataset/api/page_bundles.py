"""Page-level API bundles — one JSON response per dashboard.

Each builder fans its independent sources out across a small thread pool
instead of calling them one after another. Every source here is I/O-bound
(Postgres round-trips, yfinance HTTP calls, CSV reads) and releases the GIL
while it waits, so plain threads give real wall-clock parallelism and the
bundle costs roughly its slowest call rather than the sum of all of them.

Threads (not asyncio) are the right tool: this is a synchronous Flask app
already served with `threads = 4` in gunicorn.conf.py, so no part of the
surrounding stack has to change. `db.py` hands out connections from a
ThreadedConnectionPool, and the TTL caches are plain dict get/set, which the
GIL makes atomic — a race there costs at most a duplicate recompute.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable

from news_dataset.api.gpr_service import (
    build_dual_signal_payload,
    get_corridors,
    get_events_feed,
    get_gpr_current,
    get_gpr_history,
    get_gpr_panels,
    get_health_snapshot,
    get_platform_status_slim,
)

logger = logging.getLogger(__name__)
from news_dataset.api.market_service import (
    MARKET_SYMBOL_ORDER,
    compute_indicators,
    fetch_histories_batch,
    fetch_quotes,
)
from news_dataset.api.metrics_service import build_quality_report

DEFAULT_GPR_HISTORY_LIMIT = 250
SPARKLINE_SYMBOLS = list(MARKET_SYMBOL_ORDER)
SPARKLINE_PERIOD = "1mo"
MACRO_CHART_PERIOD = "1y"


def _safe_dual_signal() -> dict | None:
    try:
        return build_dual_signal_payload(refresh=False)
    except Exception:
        logger.exception("dual signal unavailable for page bundle")
        return None


def _safe_gpr_history(limit: int = DEFAULT_GPR_HISTORY_LIMIT) -> list[dict]:
    try:
        return get_gpr_history(limit=limit)
    except Exception:
        logger.exception("gpr history unavailable for page bundle")
        return []


def _gather(**tasks: Callable[[], Any]) -> dict[str, Any]:
    """Run independent, I/O-bound bundle sources concurrently.

    Exceptions are re-raised on `.result()`, and results are collected in
    submission order, so a builder fails exactly where and how it did when
    these calls ran sequentially — the caller in server.py still turns that
    into the same 503. Only the waiting happens in parallel.
    """
    with ThreadPoolExecutor(max_workers=max(len(tasks), 1)) as pool:
        futures = {name: pool.submit(fn) for name, fn in tasks.items()}
        return {name: future.result() for name, future in futures.items()}


def build_home_bundle() -> dict:
    r = _gather(
        health=get_health_snapshot,
        gpr_current=get_gpr_current,
        corridors=get_corridors,
        quotes=partial(fetch_quotes, SPARKLINE_SYMBOLS),
        dual_signal=_safe_dual_signal,
        status=get_platform_status_slim,
        gpr_panels=_safe_gpr_panels,
    )
    panels = r["gpr_panels"] or {}
    return {
        "health": r["health"],
        "gpr_current": r["gpr_current"],
        "corridors": r["corridors"],
        "quotes": r["quotes"],
        "dual_signal": r["dual_signal"],
        "status": r["status"],
        "gpr_panels": panels,
        "oil_gpr": panels.get("oil_gpr"),  # kept for the hero tile
    }


def build_macro_bundle() -> dict:
    # The widest bundle: 8 independent sources, including three separate
    # yfinance round-trips (quotes, 3mo indicators, 1y histories for 5
    # symbols). Sequentially this was the slowest endpoint by a wide margin.
    r = _gather(
        dual_signal=_safe_dual_signal,
        quotes=partial(fetch_quotes, SPARKLINE_SYMBOLS),
        indicators=partial(compute_indicators, "nifty"),
        gpr_current=get_gpr_current,
        gpr_history=_safe_gpr_history,
        corridors=get_corridors,
        market_histories=partial(
            fetch_histories_batch, SPARKLINE_SYMBOLS, period=MACRO_CHART_PERIOD
        ),
        status=get_platform_status_slim,
    )
    return {
        "dual_signal": r["dual_signal"],
        "quotes": r["quotes"],
        "indicators": r["indicators"],
        "gpr_current": r["gpr_current"],
        "gpr_history": {"history": r["gpr_history"]},
        "corridors": r["corridors"],
        "market_histories": r["market_histories"],
        "status": r["status"],
    }


def build_news_bundle(*, limit: int = 50) -> dict:
    r = _gather(
        events=partial(get_events_feed, limit=limit, tagged_only=True),
        gpr_current=get_gpr_current,
        gpr_history=partial(_safe_gpr_history, limit=120),
        status=get_platform_status_slim,
    )
    return {
        "events": r["events"],
        "gpr_current": r["gpr_current"],
        "gpr_history": {"history": r["gpr_history"]},
        "status": r["status"],
    }


def build_corridor_bundle(*, corridor: str | None = None, feed_limit: int = 40) -> dict:
    r = _gather(
        corridors=get_corridors,
        status=get_platform_status_slim,
        events=partial(
            get_events_feed,
            limit=feed_limit,
            corridor=corridor,
            tagged_only=True,
        ),
    )
    return {
        "corridors": r["corridors"],
        "status": r["status"],
        "events": r["events"],
        "selected_corridor": corridor,
    }


def build_portfolio_bundle() -> dict:
    r = _gather(
        gpr_current=get_gpr_current,
        dual_signal=_safe_dual_signal,
        quotes=partial(fetch_quotes, ["nifty", "sensex", "india_vix", "usd_inr"]),
        gpr_history=_safe_gpr_history,
        gpr_panels=_safe_gpr_panels,
    )
    return {
        "gpr_current": r["gpr_current"],
        "dual_signal": r["dual_signal"],
        "quotes": r["quotes"],
        "gpr_history": {"history": r["gpr_history"]},
        "gpr_panels": r["gpr_panels"],
    }


def _safe_gpr_panels() -> dict:
    try:
        return get_gpr_panels()
    except Exception:
        logger.exception("gpr panels unavailable for portfolio bundle")
        return {}


def _safe_platform_status() -> dict | None:
    try:
        return get_platform_status_slim()
    except Exception:
        logger.exception("platform status unavailable for quality bundle")
        return None


def _safe_health_snapshot() -> dict | None:
    try:
        return get_health_snapshot()
    except Exception:
        logger.exception("health snapshot unavailable for quality bundle")
        return None


def build_quality_bundle(*, refresh: bool = False) -> dict:
    # build_quality_report is the expensive one (validation CSVs + a cached
    # walk-forward vol backtest); status/health ride alongside it rather than
    # queueing behind it. Their individual try/except contracts are preserved
    # in the _safe_* wrappers above.
    r = _gather(
        report=partial(build_quality_report, refresh=refresh),
        status=_safe_platform_status,
        health=_safe_health_snapshot,
    )
    report = r["report"]
    report["status"] = r["status"]
    report["health"] = r["health"]
    return report
