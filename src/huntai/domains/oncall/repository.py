"""值班域数据访问。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.pagination import paginate
from huntai.domains.oncall.models import EscalationPolicy, OnCallSchedule


async def list_schedules(
    session: AsyncSession, *, team: str | None = None, offset: int = 0, limit: int = 50
) -> tuple[list[OnCallSchedule], int]:
    stmt = select(OnCallSchedule).order_by(OnCallSchedule.id)
    if team is not None:
        stmt = stmt.where(OnCallSchedule.team == team)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def schedules_for_team(
    session: AsyncSession, team: str, *, enabled_only: bool = False
) -> list[OnCallSchedule]:
    stmt = select(OnCallSchedule).where(OnCallSchedule.team == team)
    if enabled_only:
        stmt = stmt.where(OnCallSchedule.enabled.is_(True))
    rows = await session.execute(stmt.order_by(OnCallSchedule.id))
    return list(rows.scalars().all())


async def get_schedule(session: AsyncSession, schedule_id: int) -> OnCallSchedule | None:
    return await session.get(OnCallSchedule, schedule_id)


async def schedule_name_exists(session: AsyncSession, name: str) -> bool:
    row = await session.execute(select(OnCallSchedule.id).where(OnCallSchedule.name == name))
    return row.scalar_one_or_none() is not None


async def list_policies(
    session: AsyncSession, *, schedule_id: int | None = None, offset: int = 0, limit: int = 50
) -> tuple[list[EscalationPolicy], int]:
    stmt = select(EscalationPolicy).order_by(EscalationPolicy.id)
    if schedule_id is not None:
        stmt = stmt.where(EscalationPolicy.schedule_id == schedule_id)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def get_policy(session: AsyncSession, policy_id: int) -> EscalationPolicy | None:
    return await session.get(EscalationPolicy, policy_id)


async def enabled_policies(session: AsyncSession) -> list[EscalationPolicy]:
    rows = await session.execute(
        select(EscalationPolicy).where(EscalationPolicy.enabled.is_(True))
    )
    return list(rows.scalars().all())


async def policy_name_exists(session: AsyncSession, name: str) -> bool:
    row = await session.execute(select(EscalationPolicy.id).where(EscalationPolicy.name == name))
    return row.scalar_one_or_none() is not None
