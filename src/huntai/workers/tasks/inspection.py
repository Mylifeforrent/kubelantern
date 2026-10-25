"""巡检 worker 任务：执行、调度 tick、集群探活。"""

from __future__ import annotations

import logging

from huntai.core import context
from huntai.domains.clusters import repository as clusters_repo
from huntai.domains.clusters import service as clusters_service
from huntai.domains.inspections import service as inspection_service
from huntai.workers.context import get_context
from huntai.workers.tasks import make_enqueue, make_publish, named

logger = logging.getLogger("huntai.worker.inspections")


@named("inspection.run")
async def inspection_run(ctx, run_id: int) -> None:
    context.system_actor("inspection.run")
    worker = get_context()
    enqueue = make_enqueue(ctx.get("redis"))  # arq ctx 的 ArqRedis 池
    publish = make_publish(worker.hub)
    async with worker.sessionmaker() as session:
        try:
            await inspection_service.run_inspection(
                session, run_id, settings=worker.settings, publish=publish, enqueue=enqueue
            )
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("inspection failed", extra={"props": {"resource": f"inspection_runs:{run_id}"}})
            raise


@named("inspection.schedule_tick")
async def inspection_schedule_tick(ctx) -> list[int]:
    """cron：判定各策略 cron 到期并创建 run（多副本防重以最近 schedule run 判断 [ASSUMPTION]）。"""
    context.system_actor("inspection.schedule_tick")
    worker = get_context()
    enqueue = make_enqueue(ctx.get("redis"))  # arq ctx 的 ArqRedis 池
    async with worker.sessionmaker() as session:
        triggered = await inspection_service.schedule_tick(session, enqueue=enqueue)
        await session.commit()
    return triggered


@named("cluster.probe")
async def cluster_probe(ctx) -> None:
    """cron：集群探活更新 status（连接器只读、凭证仅内存态，BR-02）。"""
    from sqlalchemy import select

    from huntai.domains.clusters.models import Cluster

    context.system_actor("cluster.probe")
    worker = get_context()
    async with worker.sessionmaker() as session:
        clusters = (
            (await session.execute(select(Cluster).where(Cluster.deleted_at.is_(None))))
            .scalars()
            .all()
        )
        for cluster in clusters:
            await clusters_service.test_connection(session, cluster.id, actor_id=None)
        await session.commit()
