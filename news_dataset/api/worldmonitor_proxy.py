"""Server-side proxy to the WorldMonitor developer API.

Why a proxy and not a direct browser fetch:
  * the API key (X-WorldMonitor-Key) must stay server-side, never shipped to
    the browser;
  * WorldMonitor blocks default User-Agents, and browser CORS would block us
    anyway;
  * the upstream feeds update slowly, so a short server cache spares their API.

Set WORLDMONITOR_API_KEY in the backend env. Without it, routes return 503 so
the frontend can fall back to the static overlays.

Only an allowlisted set of RPCs is forwarded — this is NOT an open proxy.
"""
from __future__ import annotations

import logging
import os

import requests
from flask import Flask, jsonify, request

from news_dataset.api.cache import _MISSING, cache_get, cache_set

logger = logging.getLogger(__name__)

WM_BASE = "https://api.worldmonitor.app/api"
WM_UA = "FORSYT-Corridor-Map/1.0 (+https://github.com/VanshGupta18/Forsyt)"
CACHE_TTL_SECONDS = 60

# domain/rpc pairs we're willing to forward, keyed by the short id the
# frontend layer uses. Extend as we add layers.
ALLOWED_RPCS: dict[str, str] = {
    "military-flights": "military/v1/list-military-flights",
    "military-bases": "military/v1/list-military-bases",
    "vessels": "maritime/v1/get-vessel-snapshot",
    "cable-health": "infrastructure/v1/get-cable-health",
    "airport-flights": "aviation/v1/list-airport-flights",
    "conflict-events": "conflict/v1/events",
}


def _fetch(rpc_path: str, params: dict) -> tuple[dict | list, int]:
    key = os.environ.get("WORLDMONITOR_API_KEY", "").strip()
    if not key:
        return {"error": "WORLDMONITOR_API_KEY not set", "code": "no_key"}, 503

    cache_key = f"wm:{rpc_path}:{sorted(params.items())}"
    hit = cache_get(cache_key, ttl_seconds=CACHE_TTL_SECONDS)
    if hit is not _MISSING:
        return hit, 200

    try:
        resp = requests.get(
            f"{WM_BASE}/{rpc_path}",
            params=params,
            headers={"User-Agent": WM_UA, "X-WorldMonitor-Key": key},
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.warning("worldmonitor fetch failed: %s", exc)
        return {"error": str(exc), "code": "upstream_unreachable"}, 502

    if resp.status_code != 200:
        # surface upstream auth/quota errors verbatim so the UI can explain them
        body = _safe_json(resp)
        return {"error": "upstream_error", "status": resp.status_code, "body": body}, resp.status_code

    data = _safe_json(resp)
    cache_set(cache_key, data)
    return data, 200


def _safe_json(resp: requests.Response):
    try:
        return resp.json()
    except ValueError:
        return {"raw": resp.text[:500]}


def register_worldmonitor(app: Flask) -> None:
    @app.get("/api/worldmonitor/<layer>")
    def api_worldmonitor(layer: str):
        rpc_path = ALLOWED_RPCS.get(layer)
        if not rpc_path:
            return jsonify({"error": "unknown layer", "allowed": sorted(ALLOWED_RPCS)}), 404
        # pass through only simple query params (e.g. bbox, limit)
        params = {k: v for k, v in request.args.items()}
        data, status = _fetch(rpc_path, params)
        return jsonify(data), status
