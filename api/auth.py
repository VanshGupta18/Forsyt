"""
API key authentication via SHA-256 hash comparison.
Pass key as:  Authorization: Bearer <key>
or as query param: ?api_key=<key>
"""

import os
import hashlib
import logging
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

_security = HTTPBearer(auto_error=False)

# Store SHA-256(key) in env, never the raw key
VALID_KEY_HASH = os.getenv("API_KEY_HASH", "")
DEV_MODE       = os.getenv("DEV_MODE", "false").lower() == "true"


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def require_api_key(
    credentials: HTTPAuthorizationCredentials = Security(_security),
    api_key: str = None,  # type: ignore — injected by FastAPI query param
) -> str:
    """
    FastAPI dependency.  Returns the raw key if valid, raises 401 otherwise.
    In DEV_MODE, always passes through (no auth check).
    """
    if DEV_MODE:
        logger.debug("DEV_MODE: auth bypassed")
        return "dev"

    raw = None
    if credentials and credentials.credentials:
        raw = credentials.credentials
    elif api_key:
        raw = api_key

    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if _hash(raw) != VALID_KEY_HASH:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return raw
