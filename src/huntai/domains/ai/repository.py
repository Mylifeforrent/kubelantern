"""AI 域数据访问。"""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.pagination import paginate
from huntai.domains.ai.models import AICallLog, AIExplanation, AITask, AITaskStatus


async def list_tasks(
    session: AsyncSession, *,
    status: str | None = None, type_: str | None = None,
    incident_id: int | None = None, finding_id: int | None = None,
    offset: int = 0, limit: int = 50,
) -> tuple[list[AITask], int]:
    stmt = select(AITask).order_by(AITask.id.desc())
    if status is not None:
        stmt = stmt.where(AITask.status == status)
    if type_ is not None:
        stmt = stmt.where(AITask.type == type_)
    if incident_id is not None:
        stmt = stmt.where(AITask.incident_id == incident_id)
    if finding_id is not None:
        stmt = stmt.where(AITask.finding_id == finding_id)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def get_task(session: AsyncSession, task_id: int) -> AITask | None:
    return await session.get(AITask, task_id)


async def list_call_logs(
    session: AsyncSession, task_id: int, *, offset: int = 0, limit: int = 50
) -> tuple[list[AICallLog], int]:
    stmt = select(AICallLog).where(AICallLog.task_id == task_id).order_by(AICallLog.id)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def get_explanation_for_finding(session: AsyncSession, finding_id: int) -> AIExplanation | None:
    return (
        await session.execute(select(AIExplanation).where(AIExplanation.finding_id == finding_id))
    ).scalar_one_or_none()


async def explanations_for_findings(
    session: AsyncSession, finding_ids: list[int]
) -> list[AIExplanation]:
    if not finding_ids:
        return []
    rows = await session.execute(select(AIExplanation).where(AIExplanation.finding_id.in_(finding_ids)))
    return list(rows.scalars().all())


async def timed_out_pending_approvals(
    session: AsyncSession, *, now, batch: int = 100
) -> list[AITask]:
    rows = await session.execute(
        select(AITask)
        .where(
            AITask.status == AITaskStatus.PENDING_APPROVAL,
            AITask.approval_deadline_at.is_not(None),
            AITask.approval_deadline_at < now,
        )
        .limit(batch)
    )
    return list(rows.scalars().all())


async def consume_budget(session: AsyncSession, task_id: int, *, calls: int = 0, tokens: int = 0) -> None:
    """计数只允许 SQL 原子表达式（04-backend-design §1.5）。"""
    await session.execute(
        update(AITask)
        .where(AITask.id == task_id)
        .values(
            calls_used=AITask.calls_used + calls,
            tokens_used=AITask.tokens_used + tokens,
        )
    )


async def count_tasks(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(AITask))).scalar_one()
