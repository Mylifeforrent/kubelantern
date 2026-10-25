"""通知 worker 任务：投递（BR-08 留痕）、升级链超时检查与兜底扫描。"""

from __future__ import annotations

import logging

from huntai.core import context
from huntai.domains.notifications import service as notification_service
from huntai.workers.context import get_context
from huntai.workers.tasks import named

logger = logging.getLogger("huntai.worker.notifications")


@named("notify.dispatch")
async def notify_dispatch(ctx, alert_id: int) -> None:
    context.system_actor("notify.dispatch")
    worker = get_context()
    from huntai.domains.alerts import repository as alerts_repo

    async with worker.sessionmaker() as session:
        alert = await alerts_repo.get_alert(session, alert_id)
        team = (alert.enrichments or {}).get("team") if alert else None
        await notification_service.dispatch_for_alert(
            session, alert_id=alert_id, team=str(team) if team else None
        )
        await session.commit()


@named("escalation.check_ack")
async def escalation_check_ack(ctx, alert_id: int, policy_id: int, level: int) -> bool:
    """延迟任务：第 N 级超时仍未 Ack → 升级下一级（BR-08/BR-13）。"""
    context.system_actor("escalation.check_ack")
    worker = get_context()
    async with worker.sessionmaker() as session:
        escalated = await notification_service.escalate_level(
            session, alert_id=alert_id, policy_id=policy_id, level=level
        )
        await session.commit()
    return escalated
