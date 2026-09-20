"""TTL cache for hot API reads.

Two backends behind one interface, chosen by FORSYT_CACHE_BACKEND:

    memory   (default) — an in-process dict. Correct only for a single
               worker, which is why news_dataset/gunicorn.conf.py pins
               workers=1: with two workers each holds its own copy and a
               client's consecutive requests see different cached states.
    dynamodb — a shared table, so the cache survives across workers (and
               across processes generally). This is the seam that lets
               workers>1 become a config change rather than a rewrite.

Nothing changes unless you opt in: with FORSYT_CACHE_BACKEND unset this file
behaves exactly as it always did, and boto3 is never imported.

The DynamoDB table is declared in template.yaml (repo root) so it can be
validated with `sam validate` and created against LocalStack without an AWS
account — see docker-compose.yml's localstack service.

Failure policy: a DynamoDB error is logged and treated as a cache miss, never
raised. A missing cache costs a recomputation; a raised one costs the request.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

_MISSING = object()

# --- memory backend --------------------------------------------------------
_store: dict[str, tuple[float, Any]] = {}

# --- dynamodb backend ------------------------------------------------------
TABLE_NAME = os.environ.get("FORSYT_CACHE_TABLE", "forsyt-api-cache")
# Every row shares one partition so cache_invalidate_prefix() can be a Query
# with begins_with() on the sort key instead of a full table scan. One hot
# partition is the wrong shape at scale; at this project's scale (a handful of
# keys, <10 concurrent users — see gunicorn.conf.py) it is the right trade.
_PARTITION = "forsyt"
# Native DynamoDB TTL only garbage-collects; correctness comes from the
# written_at check in _dynamo_get(), because ttl_seconds is supplied per read.
_ROW_LIFETIME_SECONDS = 86_400

_table: Any = None


def backend() -> str:
    return os.environ.get("FORSYT_CACHE_BACKEND", "memory").strip().lower()


def _get_table() -> Any:
    global _table
    if _table is None:
        import boto3

        kwargs: dict[str, Any] = {}
        # Set by docker-compose.yml to reach LocalStack; unset against real AWS.
        endpoint = os.environ.get("AWS_ENDPOINT_URL", "").strip()
        if endpoint:
            kwargs["endpoint_url"] = endpoint
        _table = boto3.resource("dynamodb", **kwargs).Table(TABLE_NAME)
    return _table


def ensure_table() -> bool:
    """Create the cache table if absent. For local/LocalStack use — production
    should get the table from template.yaml, not from application code. Returns
    True if the table exists afterwards.
    """
    import boto3

    kwargs: dict[str, Any] = {}
    endpoint = os.environ.get("AWS_ENDPOINT_URL", "").strip()
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    client = boto3.client("dynamodb", **kwargs)
    existing = client.list_tables().get("TableNames", [])
    if TABLE_NAME in existing:
        return True
    client.create_table(
        TableName=TABLE_NAME,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "scope", "AttributeType": "S"},
            {"AttributeName": "cache_key", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "scope", "KeyType": "HASH"},
            {"AttributeName": "cache_key", "KeyType": "RANGE"},
        ],
    )
    client.get_waiter("table_exists").wait(TableName=TABLE_NAME)
    return True


def _dynamo_get(key: str, ttl_seconds: float) -> Any:
    try:
        item = _get_table().get_item(Key={"scope": _PARTITION, "cache_key": key}).get("Item")
    except Exception as exc:  # noqa: BLE001 - a broken cache must not break the read
        logger.warning("cache get failed for %s: %s", key, exc)
        return _MISSING
    if not item:
        return _MISSING
    if time.time() - float(item.get("written_at", 0)) >= ttl_seconds:
        return _MISSING
    try:
        return json.loads(item["value"])
    except (KeyError, ValueError):
        return _MISSING


def _dynamo_set(key: str, value: Any) -> None:
    try:
        # default=str because some cached payloads carry datetimes from DB rows.
        # Unlike the memory backend, this round-trips them as strings — which is
        # what jsonify() would have produced for the client anyway.
        encoded = json.dumps(value, default=str)
    except (TypeError, ValueError) as exc:
        logger.warning("cache set skipped for %s (not serialisable): %s", key, exc)
        return
    now = int(time.time())
    try:
        _get_table().put_item(
            Item={
                "scope": _PARTITION,
                "cache_key": key,
                "value": encoded,
                "written_at": now,
                "expires_at": now + _ROW_LIFETIME_SECONDS,
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache set failed for %s: %s", key, exc)


def _dynamo_invalidate_prefix(prefix: str) -> None:
    try:
        from boto3.dynamodb.conditions import Key

        table = _get_table()
        items = table.query(
            KeyConditionExpression=Key("scope").eq(_PARTITION) & Key("cache_key").begins_with(prefix),
            ProjectionExpression="cache_key",
        ).get("Items", [])
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"scope": _PARTITION, "cache_key": item["cache_key"]})
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache invalidate failed for %s*: %s", prefix, exc)


# --- public interface ------------------------------------------------------
def cache_get(key: str, *, ttl_seconds: float) -> Any:
    if backend() == "dynamodb":
        return _dynamo_get(key, ttl_seconds)
    entry = _store.get(key)
    if entry is None:
        return _MISSING
    if time.monotonic() - entry[0] >= ttl_seconds:
        del _store[key]
        return _MISSING
    return entry[1]


def cache_set(key: str, value: Any) -> None:
    if backend() == "dynamodb":
        _dynamo_set(key, value)
        return
    _store[key] = (time.monotonic(), value)


def cache_invalidate_prefix(prefix: str) -> None:
    if backend() == "dynamodb":
        _dynamo_invalidate_prefix(prefix)
        return
    for key in [k for k in _store if k.startswith(prefix)]:
        del _store[key]
