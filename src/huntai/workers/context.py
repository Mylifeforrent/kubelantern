"""WorkerContext：worker 进程级资源（session/redis/hub），on_startup 注入。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from huntai.core.config import Settings
from huntai.core.db import create_engine_and_sessionmaker
from huntai.core.logging import setup_logging
from huntai.core.redis import create_redis_client
from huntai.realtime.hub import RealtimeHub


@dataclass
class WorkerContext:
    settings: Settings
    sessionmaker: Any = None
    redis: Any = None
    hub: RealtimeHub | None = None
    gateway: Any = None
    circuit: Any = None


_shared: WorkerContext | None = None


def get_context() -> WorkerContext:
    global _shared
    if _shared is None:
        settings = Settings()
        setup_logging(settings.log_level, settings.log_format)
        engine, sessionmaker = create_engine_and_sessionmaker(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
        )
        redis = create_redis_client(settings.redis_url)
        from huntai.gateway.circuit import CircuitBreaker

        _shared = WorkerContext(
            settings=settings,
            sessionmaker=sessionmaker,
            redis=redis,
            hub=RealtimeHub(redis, settings=settings),
            circuit=CircuitBreaker(
                failure_threshold=settings.ai_circuit_failures,
                reset_seconds=settings.ai_circuit_reset_seconds,
            ),
        )
    return _shared


def reset_context() -> None:
    global _shared
    _shared = None
