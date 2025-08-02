import redis.asyncio as redis


class RedisCacheService:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def get(self, key: str) -> str | None:
        try:
            value = await self.redis.get(key)
            return value.decode("utf-8") if value else None
        except Exception:
            return None

    async def set(self, key: str, value: str, expire: int | None = None) -> bool:
        try:
            await self.redis.set(key, value, ex=expire)
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> bool:
        try:
            result = await self.redis.delete(key)
            return result > 0
        except Exception:
            return False

    async def exists(self, key: str) -> bool:
        try:
            result = await self.redis.exists(key)
            return result > 0
        except Exception:
            return False
