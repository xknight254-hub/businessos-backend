"""Rate limiting for BusinessOS (M2.3).

Backend-agnostic fixed-window counter:
- ``MemoryRateLimitStore``: process-local. Default when Redis absent.
- ``RedisRateLimitStore``: shared across workers when ``REDIS_URL`` reachable.

``RateLimitMiddleware`` enforces per-key limits on configured route prefixes
(auth, payments by default). Key = client IP (and user id when authed).
On exceed -> 429 with ``Retry-After``.

Like the token store, the backend auto-selects Redis if reachable, else
memory. Zero-infra deployable; production-ready via ``REDIS_URL``.
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("businessos.ratelimit")


class RateLimitStore:
    async def incr(self, key: str, window: int, limit: int):
        raise NotImplementedError


class MemoryRateLimitStore(RateLimitStore):
    def __init__(self) -> None:
        self._buckets: dict[str, tuple[float, int]] = {}

    async def incr(self, key: str, window: int, limit: int):
        now = time.time()
        ts, count = self._buckets.get(key, (now, 0))
        if now - ts > window:
            ts, count = now, 0
        count += 1
        self._buckets[key] = (ts, count)
        return count, max(0, int(ts + window - now))


class RedisRateLimitStore(RateLimitStore):
    def __init__(self, redis) -> None:
        self._redis = redis

    async def incr(self, key: str, window: int, limit: int):
        # INCR + EXPIRE atomically via pipeline; count = current hits
        pipe = self._redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        result = await pipe.execute()
        count = result[0]
        ttl = await self._redis.ttl(key)
        return count, max(0, ttl)


_store: Optional[RateLimitStore] = None
_warn_logged = False


async def get_ratelimit_store() -> RateLimitStore:
    global _store, _warn_logged
    if _store is not None:
        return _store
    redis_url = getattr(settings, "REDIS_URL", "")
    if redis_url:
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(redis_url, socket_connect_timeout=1.0)
            await asyncio.wait_for(client.ping(), timeout=1.0)
            _store = RedisRateLimitStore(client)
            logger.info("ratelimit_store", extra={"backend": "redis"})
            return _store
        except Exception as exc:
            if not _warn_logged:
                logger.warning("ratelimit_redis_unavailable_fallback_memory", extra={"detail": str(exc)})
                _warn_logged = True
    _store = MemoryRateLimitStore()
    if not _warn_logged:
        logger.info("ratelimit_store", extra={"backend": "memory"})
        _warn_logged = True
    return _store


# Route prefix -> (limit, window_seconds)
DEFAULT_LIMITS: dict[str, tuple[int, int]] = {
    "/auth": (20, 60),       # 20 auth attempts / min
    "/payments": (30, 60),   # 30 payment calls / min
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limits: Optional[dict[str, tuple[int, int]]] = None) -> None:
        super().__init__(app)
        self.limits = limits or DEFAULT_LIMITS

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        matched_prefix = None
        for prefix, (limit, window) in self.limits.items():
            if path.startswith(prefix):
                matched_prefix = prefix
                break
        if matched_prefix is None:
            return await call_next(request)

        limit, window = self.limits[matched_prefix]
        # Key: IP, or IP+user when authed (best-effort from bearer sub).
        client_ip = request.client.host if request.client else "unknown"
        auth = request.headers.get("authorization", "")
        key_suffix = ""
        if auth.lower().startswith("bearer "):
            try:
                from app.core.security import decode_token
                sub = decode_token(auth[7:].strip()).get("sub")
                if sub:
                    key_suffix = f":u:{sub}"
            except Exception:
                pass
        key = f"rl:{matched_prefix}:{client_ip}{key_suffix}"

        store = await get_ratelimit_store()
        count, retry_after = await store.incr(key, window, limit)
        if count > limit:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "rate_limited", "message": "Too many requests"}},
                headers={"Retry-After": str(retry_after)},
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
        return response
