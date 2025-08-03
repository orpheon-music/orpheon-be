import redis.asyncio as redis

from app.config.settings import get_settings

settings = get_settings()

# Create Redis client
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
)


async def get_redis_client() -> redis.Redis:
    return redis_client


async def close_redis_connection():
    await redis_client.close()


async def check_redis_connection():
    """Check Redis connection during startup"""
    await redis_client.ping()  # type: ignore
    return True
