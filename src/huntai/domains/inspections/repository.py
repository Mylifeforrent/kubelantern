"""巡检数据访问。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.pagination import paginate
from huntai.domains.inspections.models import (
    Finding,
    FindingStatus,
    InspectionPolicy,
    InspectionPolicyRule,
    InspectionRule,
    InspectionRun,
)


async def list_rules(
    session: AsyncSession, *, category: str | None = None, enabled: bool | None = None,
    offset: int = 0, limit: int = 50,
) -> tuple[list[InspectionRule], int]:
    stmt = select(InspectionRule).order_by(InspectionRule.id)
    if category is not None:
        stmt = stmt.where(InspectionRule.category == category)
    if enabled is not None:
        stmt = stmt.where(InspectionRule.enabled == enabled)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def get_rule(session: AsyncSession, rule_id: int) -> InspectionRule | None:
    return await session.get(InspectionRule, rule_id)


async def code_exists(session: AsyncSession, code: str) -> bool:
    row = await session.execute(select(InspectionRule.id).where(InspectionRule.code == code))
    return row.scalar_one_or_none() is not None


async def enabled_rules(session: AsyncSession) -> list[InspectionRule]:
    rows = await session.execute(select(InspectionRule).where(InspectionRule.enabled.is_(True)))
    return list(rows.scalars().all())


async def list_policies(
    session: AsyncSession, *, cluster_id: int | None = None, enabled: bool | None = None,
    offset: int = 0, limit: int = 50,
) -> tuple[list[InspectionPolicy], int]:
    stmt = select(InspectionPolicy).order_by(InspectionPolicy.id)
    if cluster_id is not None:
        stmt = stmt.where(InspectionPolicy.cluster_id == cluster_id)
    if enabled is not None:
        stmt = stmt.where(InspectionPolicy.enabled == enabled)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def get_policy(session: AsyncSession, policy_id: int) -> InspectionPolicy | None:
    return await session.get(InspectionPolicy, policy_id)


async def policy_rule_ids(session: AsyncSession, policy_id: int) -> list[int]:
    rows = await session.execute(
        select(InspectionPolicyRule.rule_id).where(InspectionPolicyRule.policy_id == policy_id)
    )
    return [row for row in rows.scalars()]


async def replace_policy_rules(session: AsyncSession, policy_id: int, rule_ids: list[int]) -> None:
    await session.execute(
        InspectionPolicyRule.__table__.delete().where(InspectionPolicyRule.policy_id == policy_id)
    )
    for rule_id in sorted(set(rule_ids)):
        session.add(InspectionPolicyRule(policy_id=policy_id, rule_id=rule_id))
    await session.flush()


async def enabled_policies(session: AsyncSession) -> list[InspectionPolicy]:
    rows = await session.execute(
        select(InspectionPolicy).where(InspectionPolicy.enabled.is_(True))
    )
    return list(rows.scalars().all())


async def last_scheduled_run(session: AsyncSession, policy_id: int) -> InspectionRun | None:
    return (
        await session.execute(
            select(InspectionRun)
            .where(InspectionRun.policy_id == policy_id, InspectionRun.trigger == "schedule")
            .order_by(InspectionRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def list_runs(
    session: AsyncSession, *, cluster_id: int | None = None, policy_id: int | None = None,
    status: str | None = None, offset: int = 0, limit: int = 50,
) -> tuple[list[InspectionRun], int]:
    stmt = select(InspectionRun).order_by(InspectionRun.id.desc())
    if cluster_id is not None:
        stmt = stmt.where(InspectionRun.cluster_id == cluster_id)
    if policy_id is not None:
        stmt = stmt.where(InspectionRun.policy_id == policy_id)
    if status is not None:
        stmt = stmt.where(InspectionRun.status == status)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def get_run(session: AsyncSession, run_id: int) -> InspectionRun | None:
    return await session.get(InspectionRun, run_id)


async def list_findings(
    session: AsyncSession, *, cluster_id: int | None = None, rule_code: str | None = None,
    severity: str | None = None, status: str | None = None,
    offset: int = 0, limit: int = 50,
) -> tuple[list[Finding], int]:
    stmt = select(Finding).order_by(Finding.id.desc())
    if cluster_id is not None:
        stmt = stmt.where(Finding.cluster_id == cluster_id)
    if rule_code is not None:
        stmt = stmt.where(Finding.rule_code == rule_code)
    if severity is not None:
        stmt = stmt.where(Finding.severity == severity)
    if status is not None:
        stmt = stmt.where(Finding.status == status)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def get_finding(session: AsyncSession, finding_id: int) -> Finding | None:
    return await session.get(Finding, finding_id)


async def open_finding_for_ref(
    session: AsyncSession, *, cluster_id: int, rule_code: str, resource_ref: dict
) -> Finding | None:
    """复现重开判定 [ASSUMPTION]：同资源存在未处置 finding 时复用而非新开。"""
    rows = await session.execute(
        select(Finding).where(
            Finding.cluster_id == cluster_id,
            Finding.rule_code == rule_code,
            Finding.status.in_([FindingStatus.OPEN, FindingStatus.ACKNOWLEDGED, FindingStatus.IN_PROGRESS]),
        )
    )
    for finding in rows.scalars():
        if finding.resource_ref == resource_ref:
            return finding
    return None
