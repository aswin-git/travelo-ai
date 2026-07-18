"""
Redis cache layer for external API calls (SerpAPI, etc.).

Gracefully falls back to direct API calls when Redis is unavailable.
In production, connects to GCP Memorystore. Locally, works without Redis.
"""

import hashlib
import json
import time
from typing import Any, Dict, Optional

from serpapi import GoogleSearch

from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Redis connection (lazy singleton)
# ---------------------------------------------------------------------------
_redis_client = None
_redis_checked = False


def get_redis():
    """Return a Redis client or None if unavailable."""
    global _redis_client, _redis_checked

    if _redis_checked:
        return _redis_client

    _redis_checked = True
    redis_url = settings.REDIS_URL
    if not redis_url:
        logger.info("REDIS_URL not set — caching disabled, all API calls go direct")
        return None

    try:
        import redis
        _redis_client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
        )
        # Test connection
        _redis_client.ping()
        logger.info(f"Redis connected: {redis_url}")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis unavailable ({e}) — falling back to direct API calls")
        _redis_client = None
        return None


# ---------------------------------------------------------------------------
# Cache key generation
# ---------------------------------------------------------------------------
def make_cache_key(prefix: str, params: Dict[str, Any]) -> str:
    """Build a deterministic cache key from a prefix and params dict.

    Format: travelo:{prefix}:{md5(sorted_params)}
    Excludes api_key from the hash (same query, different keys = same cache).
    """
    filtered = {k: v for k, v in sorted(params.items()) if k != "api_key"}
    raw = json.dumps(filtered, sort_keys=True, default=str)
    digest = hashlib.md5(raw.encode()).hexdigest()
    return f"travelo:{prefix}:{digest}"


# ---------------------------------------------------------------------------
# Core get/set
# ---------------------------------------------------------------------------
def cache_get(key: str) -> Optional[dict]:
    """Retrieve cached data. Returns None on miss or error."""
    r = get_redis()
    if not r:
        return None
    try:
        data = r.get(key)
        if data:
            logger.info(f"CACHE HIT: {key}")
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
        return None


def cache_set(key: str, data: Any, ttl_seconds: int = 3600):
    """Store data in cache with TTL. Silently fails if Redis unavailable."""
    r = get_redis()
    if not r:
        return
    try:
        r.setex(key, ttl_seconds, json.dumps(data, default=str))
        logger.debug(f"CACHE SET: {key} (TTL={ttl_seconds}s)")
    except Exception as e:
        logger.warning(f"Cache write error: {e}")


# ---------------------------------------------------------------------------
# All-in-one: cached SerpAPI call
# ---------------------------------------------------------------------------

# TTL presets (seconds)
TTL_1H = 3600
TTL_2H = 7200
TTL_6H = 21600
TTL_12H = 43200


def cached_serpapi_call(
    prefix: str,
    params: Dict[str, Any],
    ttl: int = TTL_6H,
) -> dict:
    """Execute a SerpAPI call with Redis caching.

    1. Check cache for existing result
    2. On miss: call SerpAPI, store result, return
    3. On Redis failure: call SerpAPI directly (no crash)

    Args:
        prefix: Cache key namespace (e.g. 'hotels', 'attractions')
        params: Full SerpAPI params dict (api_key included)
        ttl: Cache TTL in seconds

    Returns:
        SerpAPI response dict
    """
    key = make_cache_key(prefix, params)

    # Try cache first
    cached = cache_get(key)
    if cached is not None:
        return cached

    # Cache miss — call SerpAPI
    start = time.time()
    search = GoogleSearch(params)
    results = search.get_dict()
    elapsed = time.time() - start
    logger.info(f"SerpAPI call [{prefix}] took {elapsed:.2f}s (CACHE MISS)")

    # Store in cache
    cache_set(key, results, ttl)

    return results
