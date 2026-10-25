"""AI 任务 worker 任务：经 AI 网关执行（唯一模型出域口，ADR-0004）+ 审批超时扫描。"""

from __future__ import annotations

import logging

from huntai.core import context
from huntai.domains.ai import service as ai_service
from huntai.gateway.gateway import AIGateway
from huntai.workers.context import get_context
from huntai.workers.tasks import make_publish, named

logger = logging.getLogger("huntai.worker.ai")


@named("ai.execute_task")
async def ai_execute_task(ctx, task_id: int):
    """AI 任务不做框架级自动重试（预算语义 BR-03）；A1 失败重试 1 次为业务层重试。"""
    context.system_actor("ai.execute_task")
    worker = get_context()
    publish = make_publish(worker.hub)
    if worker.gateway is None:
        worker.gateway = AIGateway(worker.settings, circuit=worker.circuit)
    async with worker.sessionmaker() as session:
        try:
            task = await worker.gateway.execute_task(session, task_id, publish=publish)
            await session.commit()
            return None if task is None else task.status.value
        except Exception:
            await session.rollback()
            logger.exception("ai task failed", extra={"props": {"resource": f"ai_tasks:{task_id}"}})
            raise


@named("approval.scan_timeouts")
async def approval_scan_timeouts(ctx) -> int:
    """cron：审批超时（默认 30min [ASSUMPTION]）= 拒绝（BR-02）。"""
    context.system_actor("approval.scan_timeouts")
    worker = get_context()
    publish = make_publish(worker.hub)
    async with worker.sessionmaker() as session:
        expired = await ai_service.scan_approval_timeouts(session, publish=publish)
        await session.commit()
    return len(expired)
