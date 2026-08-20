"""Page-level API bundles — one JSON response per dashboard."""

from __future__ import annotations

import logging

from news_dataset.api.gpr_service import (
    build_dual_signal_payload,
    get_corridors,
    get_events_feed,
    get_gpr_current,
    get_gpr_history,
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


def build_home_bundle() -> dict:
    return {
        "health": get_health_snapshot(),
        "gpr_current": get_gpr_current(),
        "corridors": get_corridors(),
        "quotes": fetch_quotes(SPARKLINE_SYMBOLS),
        "dual_signal": _safe_dual_signal(),
        "status": get_platform_status_slim(),
    }


def build_macro_bundle() -> dict:
    corridors = get_corridors()
    return {
        "dual_signal": _safe_dual_signal(),
        "quotes": fetch_quotes(SPARKLINE_SYMBOLS),
        "indicators": compute_indicators("nifty"),
        "gpr_current": get_gpr_current(),
        "gpr_history": {"history": _safe_gpr_history()},
        "corridors": corridors,
        "market_histories": fetch_histories_batch(SPARKLINE_SYMBOLS, period=MACRO_CHART_PERIOD),
        "status": get_platform_status_slim(),
    }


def build_news_bundle(*, limit: int = 50) -> dict:
    return {
        "events": get_events_feed(limit=limit, tagged_only=True),
        "gpr_current": get_gpr_current(),
        "gpr_history": {"history": _safe_gpr_history(limit=120)},
        "status": get_platform_status_slim(),
    }


def build_corridor_bundle(*, corridor: str | None = None, feed_limit: int = 40) -> dict:
    return {
        "corridors": get_corridors(),
        "status": get_platform_status_slim(),
        "events": get_events_feed(
            limit=feed_limit,
            corridor=corridor,
            tagged_only=True,
        ),
        "selected_corridor": corridor,
    }


def build_portfolio_bundle() -> dict:
    return {
        "gpr_current": get_gpr_current(),
        "dual_signal": _safe_dual_signal(),
        "quotes": fetch_quotes(["nifty", "sensex", "india_vix"]),
        "gpr_history": {"history": _safe_gpr_history()},
    }


def build_quality_bundle(*, refresh: bool = False) -> dict:
    report = build_quality_report(refresh=refresh)
    try:
        report["status"] = get_platform_status_slim()
    except Exception:
        logger.exception("platform status unavailable for quality bundle")
        report["status"] = None
    try:
        report["health"] = get_health_snapshot()
    except Exception:
        logger.exception("health snapshot unavailable for quality bundle")
        report["health"] = None
    return report
