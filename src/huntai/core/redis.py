"""Redis 客户端与 arq 任务池工厂（api 侧只投递不消费，04-backend-design §1.3）。"""

from __future__ import annotations

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from redis.asyncio import Redis


def create_redis_client(redis_url: str) -> Redis:
    return Redis.from_url(redis_url, decode_responses=True)


async def create_arq_pool(redis_url: str) -> ArqRedis:
    settings = RedisSettings.from_dsn(redis_url)
    return await create_pool(settings)
