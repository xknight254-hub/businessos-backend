"""Backend-agnostic revocation store for JWT refresh-token rotation (M2.4).

Design: a single ``TokenStore`` interface with two implementations:
- ``MemoryTokenStore``: process-local dict. Default when Redis is absent
  (single-instance dev / preview). NOT shared across workers.
- ``RedisTokenStore``: used when ``settings.REDIS_URL`` is reachable. Shared
  across workers/instances — required for multi-instance production.

Revocation semantics: when a refresh token is rotated, the old ``jti`` is
added to the revocation set with a TTL equal to the token's remaining
lifetime, so a replayed (rotated) refresh token is rejected.

The store auto-selects: if ``REDIS_URL`` is set AND redis is reachable, use
Redis; otherwise fall back to memory (logged once). This keeps the code
deployable with zero infra and production-ready via config only.
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("businessos.token_store")


class TokenStore:
    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        raise NotImplementedError

    async def is_revoked(self, jti: str) -> bool:
        raise NotImplementedError


class MemoryTokenStore(TokenStore):
    def __init__(self) -> None:
        self._revoked: dict[str, float] = {}

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        self._revoked[jti] = time.time() + ttl_seconds

    async def is_revoked(self, jti: str) -> bool:
        exp = self._revoked.get(jti)
        if exp is None:
            return False
        if exp < time.time():
            self._revoked.pop(jti, None)
            return False
        return True


class RedisTokenStore(TokenStore):
    def __init__(self, redis) -> None:
        self._redis = redis

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        await self._redis.set(f"revoked:{jti}", "1", ex=max(1, int(ttl_seconds)))

    async def is_revoked(self, jti: str) -> bool:
        return await self._redis.exists(f"revoked:{jti}") == 1


_store: Optional[TokenStore] = None
_warn_logged = False


async def get_token_store() -> TokenStore:
    """Return the active store, building it once (lazy)."""
    global _store, _warn_logged
    if _store is not None:
        return _store
    redis_url = getattr(settings, "REDIS_URL", "")
    if redis_url:
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(redis_url, socket_connect_timeout=1.0)
            await asyncio.wait_for(client.ping(), timeout=1.0)
            _store = RedisTokenStore(client)
            logger.info("token_store", extra={"backend": "redis"})
            return _store
        except Exception as exc:
            if not _warn_logged:
                logger.warning(
                    "token_store_redis_unavailable_fallback_memory",
                    extra={"detail": str(exc)},
                )
                _warn_logged = True
    _store = MemoryTokenStore()
    if not _warn_logged:
        logger.info("token_store", extra={"backend": "memory"})
        _warn_logged = True
    return _store


def revoke_token_sync(jti: str, ttl_seconds: int) -> None:
    """Synchronous helper for use in non-async paths (e.g. deploy scripts)."""
    try:
        asyncio.get_event_loop().run_until_complete(get_token_store().revoke(jti, ttl_seconds))
    except Exception:
        pass
