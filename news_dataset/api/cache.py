"""In-process TTL cache for hot API reads (single-worker gunicorn)."""

from __future__ import annotations

import time
from typing import Any

_store: dict[str, tuple[float, Any]] = {}
_MISSING = object()


def cache_get(key: str, *, ttl_seconds: float) -> Any:
    entry = _store.get(key)
    if entry is None:
        return _MISSING
    if time.monotonic() - entry[0] >= ttl_seconds:
        del _store[key]
        return _MISSING
    return entry[1]


def cache_set(key: str, value: Any) -> None:
    _store[key] = (time.monotonic(), value)


def cache_invalidate_prefix(prefix: str) -> None:
    for key in [k for k in _store if k.startswith(prefix)]:
        del _store[k]
