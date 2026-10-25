"""任务注册辅助 + 通用入队/发布绑定。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from arq.connections import ArqRedis


def named(job_name: str) -> Callable:
    """把协程注册为点号命名空间任务名（<域>.<动作>，04-backend-design §1.7）。

    arq 以 __qualname__ 注册函数名，两个属性都要改。
    """

    def wrap(fn):
        fn.__name__ = job_name
        fn.__qualname__ = job_name
        return fn

    return wrap


def make_enqueue(pool: ArqRedis | None) -> Callable[..., Awaitable[str | None]]:
    async def enqueue(job_name: str, *args, **kwargs) -> str | None:
        if pool is None:
            return None
        from huntai.core.config import QUEUE_BY_JOB

        queue = kwargs.pop("_queue", None) or QUEUE_BY_JOB.get(job_name)
        defer_by = kwargs.pop("_defer_by", None)
        return await pool.enqueue_job(job_name, *args, _queue_name=queue, _defer_by=defer_by)

    return enqueue


def make_publish(hub) -> Callable[..., Awaitable[None]]:
    async def publish(event) -> None:
        if hub is None:
            return
        await hub.publish(event)

    return publish
