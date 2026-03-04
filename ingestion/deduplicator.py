"""
Two-layer deduplication:
  Layer 1: SHA-256 URL hash (exact URL dedup via Redis SETNX)
  Layer 2: MinHash LSH (near-duplicate / syndicated article detection)
"""

import hashlib
import logging
import redis
import os
from typing import Optional
from datasketch import MinHash, MinHashLSH

logger = logging.getLogger(__name__)

# MinHash parameters
NUM_PERM       = 128     # Number of hash permutations
JACCARD_THRESH = 0.80    # Similarity threshold for near-duplicate
SHINGLE_SIZE   = 5       # n-gram shingle word count

# Redis TTLs
URL_DEDUP_TTL_SECONDS      = 7 * 24 * 3600    # 7 days
MINHASH_DEDUP_TTL_SECONDS  = 48 * 3600        # 48 hours

# Redis instance (module-level singleton)
_redis: Optional[redis.Redis] = None
_lsh: Optional[MinHashLSH] = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
            decode_responses=True
        )
    return _redis


def _get_lsh() -> MinHashLSH:
    """In-process LSH index. Note: does not persist across restarts."""
    global _lsh
    if _lsh is None:
        _lsh = MinHashLSH(threshold=JACCARD_THRESH, num_perm=NUM_PERM)
    return _lsh


def is_duplicate_url(url_hash: str) -> bool:
    """
    Layer 1: Check if URL was seen in the last 7 days.
    Uses Redis SETNX (set-if-not-exists) for atomic check-and-mark.
    Returns True if duplicate (should be discarded).
    """
    r = _get_redis()
    key = f"dedup:url:{url_hash}"
    # SETNX returns 1 if key was set (new), 0 if already existed (duplicate)
    was_new = r.setnx(key, "1")
    if was_new:
        r.expire(key, URL_DEDUP_TTL_SECONDS)
        return False   # Not a duplicate
    return True        # Already seen


def get_minhash(text: str) -> MinHash:
    """Compute MinHash signature from word shingles."""
    m = MinHash(num_perm=NUM_PERM)
    words = text.lower().split()
    shingles = {
        " ".join(words[i:i + SHINGLE_SIZE])
        for i in range(max(1, len(words) - SHINGLE_SIZE + 1))
    }
    for shingle in shingles:
        m.update(shingle.encode("utf-8"))
    return m


def is_near_duplicate(url_hash: str, text: str) -> bool:
    """
    Layer 2: Check if article text is near-duplicate of a recently seen article.
    Uses in-process MinHashLSH index.
    Returns True if near-duplicate (should be discarded).
    """
    lsh = _get_lsh()
    m = get_minhash(text)

    try:
        result = lsh.query(m)
        if result:
            logger.debug(f"Near-duplicate detected for {url_hash[:16]}... (similar to {result[0]})")
            return True

        # Not a duplicate — add to LSH index
        lsh.insert(url_hash, m)
        return False

    except Exception as e:
        # If LSH query fails (e.g., key already inserted), treat as non-duplicate to be safe
        logger.warning(f"LSH query error for {url_hash[:16]}: {e}")
        return False


def should_process(url_hash: str, text: str) -> bool:
    """
    Combined check: returns True if article should be processed (not a duplicate).
    Layer 1 runs first (fast, O(1)); Layer 2 only runs if Layer 1 passes.
    """
    if is_duplicate_url(url_hash):
        logger.debug(f"Layer-1 dedup: URL hash {url_hash[:16]}... already seen")
        return False

    if is_near_duplicate(url_hash, text):
        logger.debug(f"Layer-2 dedup: near-duplicate text for {url_hash[:16]}...")
        return False

    return True
