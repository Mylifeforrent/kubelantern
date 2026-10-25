"""事件域数据访问。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.pagination import paginate
from huntai.domains.incidents.models import (
    Incident,
    IncidentAlert,
    IncidentCandidate,
    Postmortem,
    PostmortemActionItem,
    StatusPageEntry,
    StatusPageUpdate,
)


async def list_incidents(
    session: AsyncSession,
    *,
    status: str | None = None,
    severity: str | None = None,
    team: str | None = None,
    team_scope: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Incident], int]:
    stmt = select(Incident).order_by(Incident.id.desc())
    if status is not None:
        stmt = stmt.where(Incident.status == status)
    if severity is not None:
        stmt = stmt.where(Incident.severity == severity)
    if team is not None:
        stmt = stmt.where(Incident.team == team)
    if team_scope is not None:
        stmt = stmt.where((Incident.team == team_scope) | (Incident.team.is_(None)))
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def get_incident(session: AsyncSession, incident_id: int) -> Incident | None:
    return await session.get(Incident, incident_id)


async def linked_alerts(session: AsyncSession, incident_id: int) -> list[IncidentAlert]:
    rows = await session.execute(
        select(IncidentAlert).where(IncidentAlert.incident_id == incident_id)
    )
    return list(rows.scalars().all())


async def incidents_for_rule(session: AsyncSession, rule_id: int) -> list[Incident]:
    rows = await session.execute(
        select(Incident).where(
            Incident.correlation_rule_id == rule_id, Incident.status.notin_(["closed", "cancelled"])
        )
    )
    return list(rows.scalars().all())


async def list_candidates(
    session: AsyncSession,
    *,
    status: str | None = None,
    correlation_rule_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[IncidentCandidate], int]:
    stmt = select(IncidentCandidate).order_by(IncidentCandidate.id.desc())
    if status is not None:
        stmt = stmt.where(IncidentCandidate.status == status)
    if correlation_rule_id is not None:
        stmt = stmt.where(IncidentCandidate.correlation_rule_id == correlation_rule_id)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def get_candidate(session: AsyncSession, candidate_id: int) -> IncidentCandidate | None:
    return await session.get(IncidentCandidate, candidate_id)


async def pending_candidate_for_rule(
    session: AsyncSession, rule_id: int
) -> IncidentCandidate | None:
    return (
        await session.execute(
            select(IncidentCandidate).where(
                IncidentCandidate.correlation_rule_id == rule_id,
                IncidentCandidate.status == "pending",
            )
        )
    ).scalar_one_or_none()


async def get_postmortem(session: AsyncSession, incident_id: int) -> Postmortem | None:
    return (
        await session.execute(
            select(Postmortem).where(Postmortem.incident_id == incident_id)
        )
    ).scalar_one_or_none()


async def action_items(session: AsyncSession, postmortem_id: int) -> list[PostmortemActionItem]:
    rows = await session.execute(
        select(PostmortemActionItem).where(PostmortemActionItem.postmortem_id == postmortem_id)
    )
    return list(rows.scalars().all())


async def list_status_entries(
    session: AsyncSession,
    *,
    visibility: str | None = None,
    viewer_public_only: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[StatusPageEntry], int]:
    stmt = select(StatusPageEntry).order_by(StatusPageEntry.id.desc())
    if visibility is not None:
        stmt = stmt.where(StatusPageEntry.visibility == visibility)
    elif viewer_public_only:
        stmt = stmt.where(StatusPageEntry.visibility == "public")
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def get_status_entry(session: AsyncSession, entry_id: int) -> StatusPageEntry | None:
    return await session.get(StatusPageEntry, entry_id)


async def entry_for_incident(session: AsyncSession, incident_id: int) -> StatusPageEntry | None:
    return (
        await session.execute(
            select(StatusPageEntry).where(StatusPageEntry.incident_id == incident_id)
        )
    ).scalar_one_or_none()


async def entry_updates(session: AsyncSession, entry_id: int) -> list[StatusPageUpdate]:
    rows = await session.execute(
        select(StatusPageUpdate).where(StatusPageUpdate.entry_id == entry_id)
    )
    return list(rows.scalars().all())


async def candidate_title_exists(session: AsyncSession, title: str) -> bool:
    count = (
        await session.execute(
            select(func.count()).select_from(Incident).where(Incident.title == title)
        )
    ).scalar_one()
    return count > 0
