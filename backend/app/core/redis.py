import time
from typing import Optional, Any
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class InMemoryCache:
    """
    In-memory fallback cache when Redis is unavailable or disabled.
    Thread-safe and async-friendly with TTL expiration support.
    """
    def __init__(self):
        self._store: dict[str, tuple[Any, Optional[float]]] = {}

    async def get(self, key: str) -> Optional[str]:
        if key not in self._store:
            return None
        value, expiry = self._store[key]
        if expiry is not None and time.time() > expiry:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        expiry = time.time() + ex if ex else None
        self._store[key] = (str(value), expiry)
        return True

    async def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._store.clear()


class CacheClient:
    def __init__(self):
        self.client = None
        self.is_redis: bool = False

    async def connect(self):
        if settings.REDIS_ENABLED:
            try:
                import redis.asyncio as aioredis
                self.client = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                )
                await self.client.ping()
                self.is_redis = True
                logger.info("Connected to Redis cache server.")
                return
            except Exception as e:
                logger.warning(f"Could not connect to Redis ({e}). Falling back to in-memory cache.")
                self.client = InMemoryCache()
                self.is_redis = False
        else:
            logger.info("Redis disabled. Using in-memory local cache.")
            self.client = InMemoryCache()
            self.is_redis = False

    async def get(self, key: str) -> Optional[str]:
        if not self.client:
            await self.connect()
        return await self.client.get(key)

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        if not self.client:
            await self.connect()
        return await self.client.set(key, value, ex=ex)

    async def delete(self, key: str) -> bool:
        if not self.client:
            await self.connect()
        return await self.client.delete(key)

    async def ping(self) -> bool:
        if not self.client:
            await self.connect()
        try:
            return await self.client.ping()
        except Exception:
            return False

    async def close(self):
        if self.client:
            try:
                await self.client.close()
            except Exception:
                pass


cache_client = CacheClient()
