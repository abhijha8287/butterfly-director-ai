from redis.asyncio import ConnectionPool, Redis

from app.config.settings import Settings, get_settings

_pool: ConnectionPool | None = None


def get_redis_pool(settings: Settings | None = None) -> ConnectionPool:
    global _pool
    if _pool is None:
        settings = settings or get_settings()
        _pool = ConnectionPool.from_url(settings.redis_url, decode_responses=True)
    return _pool


def get_redis_client() -> Redis:
    return Redis(connection_pool=get_redis_pool())


async def close_redis_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
