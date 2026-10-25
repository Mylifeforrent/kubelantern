"""告警管道 worker 任务：管道处理、回放扫描、维护窗口收口。"""

from __future__ import annotations

import logging

from huntai.core import context
from huntai.domains.alerts import service as alerts_service
from huntai.workers.context import get_context
from huntai.workers.tasks import make_enqueue, make_publish, named

logger = logging.getLogger("huntai.worker.alerts")


@named("alert.process_pipeline")
async def alert_process_pipeline(ctx, alert_id: int) -> None:
    context.system_actor("alert.process_pipeline")
    worker = get_context()
    enqueue = make_enqueue(ctx.get("redis"))  # arq ctx 的 ArqRedis 池
    publish = make_publish(worker.hub)
    async with worker.sessionmaker() as session:
        try:
            await alerts_service.process_pipeline(session, alert_id, publish=publish, enqueue=enqueue)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("pipeline failed", extra={"props": {"resource": f"alerts:{alert_id}"}})
            raise


@named("replay.scan")
async def replay_scan(ctx) -> int:
    """cron：received 超时未消费的告警重投（outbox 回放，ADR-0003）。"""
    context.system_actor("replay.scan")
    worker = get_context()
    enqueue = make_enqueue(ctx.get("redis"))  # arq ctx 的 ArqRedis 池
    async with worker.sessionmaker() as session:
        count = await alerts_service.replay_scan(
            session, stale_seconds=worker.settings.replay_stale_seconds, enqueue=enqueue
        )
        await session.commit()
    if count:
        logger.info("replay rescanned", extra={"props": {"count": count}})
    return count


@named("maintenance.close_windows")
async def maintenance_close_windows(ctx) -> int:
    """cron：窗口结束仍未恢复的 suppressed 告警重入管道（BR-07）。"""
    context.system_actor("maintenance.close_windows")
    worker = get_context()
    enqueue = make_enqueue(ctx.get("redis"))  # arq ctx 的 ArqRedis 池
    async with worker.sessionmaker() as session:
        count = await alerts_service.close_expired_windows(session, enqueue=enqueue)
        await session.commit()
    return count
