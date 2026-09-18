"""Redis and in-memory fallback cache manager for PRAMAAN API.

Provides resilient asynchronous caching for expensive admin aggregations
(dashboard statistics, jurisdiction scans, etc.) with automatic fallback.
Supports Upstash REST API over HTTPS (Port 443) to bypass ISP port 6379 blocking,
as well as standard Redis connections.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Try importing async redis for standard redis connections
try:
    import redis.asyncio as aioredis
    _HAS_REDIS_LIB = True
except ImportError:
    aioredis = None
    _HAS_REDIS_LIB = False


class _MemoryCache:
    """In-memory TTL cache fallback when Redis is unreachable or uninstalled."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}

    async def get(self, key: str) -> str | None:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, val = item
        if time.time() > expires_at:
            self._store.pop(key, None)
            return None
        return val

    async def set(self, key: str, value: str, ex: int = 60) -> None:
        self._store[key] = (time.time() + ex, value)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def delete_pattern(self, pattern: str) -> None:
        prefix = pattern.rstrip("*")
        keys_to_del = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_del:
            self._store.pop(k, None)


class UpstashRestClient:
    """Fast Upstash Redis client using REST API over standard HTTPS Port 443.

    Bypasses Indian ISP blocks on Redis port 6379, avoiding TCP SYN timeouts entirely.
    """

    def __init__(self, rest_url: str, token: str) -> None:
        self.base_url = rest_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}
        self._http: httpx.AsyncClient | None = None

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=httpx.Timeout(2.0, connect=1.5),
            )
        return self._http

    async def ping(self) -> bool:
        http = self._get_http()
        r = await http.get("/ping")
        return r.status_code == 200

    async def get(self, key: str) -> str | None:
        http = self._get_http()
        r = await http.get(f"/get/{key}")
        if r.status_code == 200:
            data = r.json()
            return data.get("result")
        return None

    async def set(self, key: str, value: str, ex: int = 60) -> bool:
        http = self._get_http()
        # Upstash REST: POST /set/{key}?ex={ex} with body
        r = await http.post(f"/set/{key}?ex={ex}", content=value.encode("utf-8"))
        return r.status_code == 200

    async def delete(self, *keys: str) -> None:
        if not keys:
            return
        http = self._get_http()
        await http.post("/del", json=list(keys))

    async def scan_pattern_delete(self, pattern: str) -> None:
        http = self._get_http()
        r = await http.get(f"/keys/{pattern}")
        if r.status_code == 200:
            keys = r.json().get("result", [])
            if keys:
                await http.post("/del", json=keys)


class CacheManager:
    """Singleton cache manager with instant in-memory primary cache and zero-blocking Redis replication."""

    def __init__(self) -> None:
        self._client: Any = None
        self._fallback = _MemoryCache()
        self._redis_available: bool | None = None
        self._init_attempted: bool = False

    async def _try_init_redis(self) -> None:
        if self._init_attempted:
            return
        self._init_attempted = True

        settings = get_settings()
        redis_url = getattr(settings, "redis_url", "redis://localhost:6379/0")

        # 1. UPSTASH VIA HTTPS (Port 443)
        if "upstash.io" in redis_url:
            try:
                parsed = urlparse(redis_url)
                host = parsed.hostname or "guiding-fox-285236.upstash.io"
                token = parsed.password or ""
                rest_url = f"https://{host}"
                upstash_client = UpstashRestClient(rest_url, token)

                # Ultra-quick check with strict 0.5s timeout
                ok = await asyncio.wait_for(upstash_client.ping(), timeout=0.5)
                if ok:
                    self._client = upstash_client
                    self._redis_available = True
                    print(f">>> [REDIS CACHE CONNECTED] Upstash REST connected: {host}", flush=True)
                    return
            except Exception as err:
                self._redis_available = False
                self._client = None
                print(f">>> [REDIS CACHE DISABLED] Upstash unreachable ({err}) — using local memory cache permanently", flush=True)
                return

        # 2. Standard Redis via aioredis
        if not _HAS_REDIS_LIB:
            self._redis_available = False
            return

        try:
            connect_kwargs: dict[str, Any] = {
                "encoding": "utf-8",
                "decode_responses": True,
                "socket_timeout": 0.5,
                "socket_connect_timeout": 0.5,
                "retry_on_timeout": False,
            }
            if redis_url.startswith("rediss://"):
                import ssl
                connect_kwargs["ssl_cert_reqs"] = ssl.CERT_NONE
                connect_kwargs["ssl_check_hostname"] = False

            client = aioredis.from_url(redis_url, **connect_kwargs)
            await asyncio.wait_for(client.ping(), timeout=0.5)
            self._client = client
            self._redis_available = True
            print(f">>> [REDIS CACHE CONNECTED] Standard Redis connected: {redis_url.split('@')[-1]}", flush=True)
        except Exception as err:
            self._redis_available = False
            self._client = None
            print(f">>> [REDIS CACHE DISABLED] Redis unreachable ({err}) — using local memory cache permanently", flush=True)

    async def get_json(self, key: str) -> Any | None:
        """Fetch and deserialize JSON. Checks Memory first (<0.05ms), then Redis only if active."""
        # 1. ALWAYS check in-memory first (ultra-fast < 0.05ms)
        mem_raw = await self._fallback.get(key)
        if mem_raw is not None:
            try:
                return json.loads(mem_raw)
            except Exception:
                pass

        # 2. If Redis is known to be unavailable, return immediately (0ms)
        if self._redis_available is False:
            return None

        # 3. If not attempted yet, fire check in background so current request NEVER waits
        if not self._init_attempted:
            try:
                asyncio.create_task(self._try_init_redis())
            except Exception:
                pass
            return None

        # 4. If Redis is verified active, read with tight 0.3s timeout
        if self._redis_available is True and self._client is not None:
            try:
                raw = await asyncio.wait_for(self._client.get(key), timeout=0.3)
                if raw is not None:
                    await self._fallback.set(key, raw, ex=60)
                    return json.loads(raw)
            except Exception as err:
                logger.debug("Redis read error for %s: %s", key, err)

        return None

    async def set_json(self, key: str, value: Any, ttl: int = 60) -> None:
        """Store value with TTL. Updates memory instantly (<0.05ms) and replicates to Redis in background."""
        try:
            payload = json.dumps(value, default=str)
        except Exception:
            return

        # 1. ALWAYS update memory cache immediately (instant return)
        await self._fallback.set(key, payload, ex=ttl)

        # 2. Redis replication strictly in background
        if self._redis_available is True and self._client is not None:
            try:
                asyncio.create_task(self._safe_redis_set(key, payload, ttl))
            except Exception:
                pass

    async def delete(self, key: str) -> None:
        """Delete key from memory and Redis."""
        await self._fallback.delete(key)
        if self._redis_available is True and self._client is not None:
            try:
                asyncio.create_task(self._safe_redis_delete(key))
            except Exception:
                pass

    async def _safe_redis_delete(self, key: str) -> None:
        try:
            if self._client is not None:
                await asyncio.wait_for(self._client.delete(key), timeout=0.5)
        except Exception:
            pass

    async def _safe_redis_set(self, key: str, payload: str, ttl: int) -> None:
        try:
            if self._client is not None and self._redis_available:
                await asyncio.wait_for(self._client.set(key, payload, ex=ttl), timeout=0.5)
        except Exception as err:
            logger.debug("Redis background set error for %s: %s", key, err)

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate all keys matching pattern in Redis and memory cache."""
        await self._fallback.delete_pattern(pattern)
        if self._redis_available is True and self._client is not None:
            try:
                asyncio.create_task(self._safe_redis_invalidate(pattern))
            except Exception:
                pass

    async def _safe_redis_invalidate(self, pattern: str) -> None:
        try:
            if self._client is not None and self._redis_available:
                if hasattr(self._client, "scan_pattern_delete"):
                    await self._client.scan_pattern_delete(pattern)
                else:
                    cursor = 0
                    while True:
                        cursor, keys = await self._client.scan(cursor=cursor, match=pattern, count=100)
                        if keys:
                            await self._client.delete(*keys)
                        if cursor == 0:
                            break
        except Exception as err:
            logger.debug("Redis invalidate pattern error for %s: %s", pattern, err)

    @property
    def is_redis_active(self) -> bool:
        return bool(self._redis_available)


# Global singleton cache instance
cache = CacheManager()


async def get_cached_dashboard_stats(scope_key: str) -> dict[str, Any] | None:
    return await cache.get_json(f"admin:stats:{scope_key}")


async def set_cached_dashboard_stats(scope_key: str, data: dict[str, Any], ttl: int = 60) -> None:
    await cache.set_json(f"admin:stats:{scope_key}", data, ttl=ttl)


async def invalidate_admin_cache() -> None:
    """Invalidate all cached admin stats and query results."""
    await cache.invalidate_pattern("admin:*")
