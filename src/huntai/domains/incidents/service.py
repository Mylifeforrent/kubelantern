"""事件响应域 service：候选流（BR-04/D-8）、事件状态机（6 态禁改）、状态页（BR-06）、复盘。

合法迁移表集中于 transition；路由层禁止绕过（非法迁移 409 INCIDENT_STATE_CONFLICT）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.db import utcnow
from huntai.core.errors import not_found, state_conflict
from huntai.domains.alerts import repository as alerts_repo
from huntai.domains.alerts.models import AlertStatus
from huntai.domains.incidents import repository as repo
from huntai.domains.incidents.models import (
    Incident,
    IncidentAlert,
    IncidentCandidate,
    Postmortem,
    PostmortemActionItem,
    StatusPageEntry,
    StatusPageUpdate,
)
from huntai.domains.incidents.schemas import (
    CandidateRejectRequest,
    IncidentCreateRequest,
    PostmortemUpdateRequest,
)
from huntai.domains.iam.service import record_audit

# 6 态合法迁移表（领域 §6；值域禁改）
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"acknowledged", "cancelled"},
    "acknowledged": {"mitigated", "cancelled"},
    "mitigated": {"resolved", "cancelled"},
    "resolved": {"closed"},
    "cancelled": set(),
    "closed": set(),
}

_ACTION_TARGET = {
    "acknowledge": "acknowledged",
    "mitigate": "mitigated",
    "resolve": "resolved",
    "close": "closed",
    "cancel": "cancelled",
}

REJECT_REASONS = {"rule_too_broad", "time_window_too_long", "enrichment_field_error"}


# ---------- 候选流（管道入口，BR-04） ----------


async def upsert_candidate(session: AsyncSession, *, rule, member_alert_ids: list[int]) -> IncidentCandidate:
    """candidate 模式命中：并入已有 pending 候选或新建；不产生 incident（D-8）。"""
    existing = await repo.pending_candidate_for_rule(session, rule.id)
    if existing is not None:
        merged = sorted(set(existing.member_alert_ids) | set(member_alert_ids))
        existing.member_alert_ids = merged
        await session.flush()
        return existing
    candidate = IncidentCandidate(
        correlation_rule_id=rule.id,
        title=rule.name,
        member_alert_ids=sorted(set(member_alert_ids)),
    )
    session.add(candidate)
    await session.flush()
    await record_audit(
        session, action="incident_candidate.create", resource_type="incident_candidates",
        resource_id=candidate.id, detail={"rule": rule.name, "members": candidate.member_alert_ids},
        actor_type="system",
    )
    return candidate


async def merge_into_auto_incident(session: AsyncSession, *, rule, member_alerts) -> Incident:
    """auto 模式命中：归并进未关闭事件，否则新建（准入门槛在规则创建/切换时校验）。"""
    incidents = await repo.incidents_for_rule(session, rule.id)
    incident = incidents[0] if incidents else None
    linked_ids = {link.alert_id for link in await repo.linked_alerts(session, incident.id)} if incident else set()
    if incident is None:
        incident = Incident(
            title=rule.name,
            severity="P2",
            status="open",
            source="correlation",
            correlation_rule_id=rule.id,
        )
        session.add(incident)
        await session.flush()
        await record_audit(
            session, action="incident.create", resource_type="incidents", resource_id=incident.id,
            detail={"source": "correlation", "rule": rule.name}, actor_type="system",
        )
    for alert in member_alerts:
        if alert.id not in linked_ids:
            session.add(
                IncidentAlert(
                    incident_id=incident.id, alert_id=alert.id,
                    correlation_rule_id=rule.id, linked_at=utcnow(),
                )
            )
    await session.flush()
    return incident


async def confirm_candidate(
    session: AsyncSession, candidate_id: int, *, actor_id: int, publish=None
) -> Incident:
    candidate = await repo.get_candidate(session, candidate_id)
    if candidate is None:
        raise not_found("incident_candidates", candidate_id)
    if candidate.status != "pending":
        raise state_conflict(
            "CANDIDATE_STATE_CONFLICT", f"候选事件 {candidate_id} 已处理（{candidate.status}）"
        )
    rule = candidate.correlation_rule_id
    alerts = await alerts_repo.alerts_by_ids(session, list(candidate.member_alert_ids))
    incident = Incident(
        title=candidate.title,
        severity=_deduce_incident_severity(alerts),
        status="open",
        source="correlation",
        candidate_id=candidate.id,
        correlation_rule_id=rule,
    )
    session.add(incident)
    await session.flush()
    for alert in alerts:
        session.add(
            IncidentAlert(
                incident_id=incident.id, alert_id=alert.id,
                correlation_rule_id=rule, linked_at=utcnow(),
            )
        )
        if alert.status != AlertStatus.RESOLVED:
            alert.status = AlertStatus.CORRELATED
    candidate.status = "confirmed"
    candidate.decided_by = actor_id
    candidate.decided_at = utcnow()
    from huntai.domains.alerts import repository as _alerts_repo

    await _alerts_repo.bump_window_counters(session, rule, confirmed=True)
    await record_audit(
        session, action="incident_candidate.confirm", resource_type="incident_candidates",
        resource_id=candidate.id, detail={"incident_id": incident.id}, actor_id=actor_id,
    )
    # BR-06：P1/P2 事件确认后自动同步状态页
    if incident.severity in {"P1", "P2"}:
        await sync_status_page(session, incident.id, actor_id=actor_id, auto=True)
    if publish is not None:
        from huntai.realtime.hub import RealtimeEvent

        await publish(
            RealtimeEvent(topic="incidents", name="incident.timeline.updated",
                          resource="incident", resource_id=incident.id, team=incident.team)
        )
    return incident


async def reject_candidate(
    session: AsyncSession, candidate_id: int, payload: CandidateRejectRequest, *, actor_id: int
) -> IncidentCandidate:
    candidate = await repo.get_candidate(session, candidate_id)
    if candidate is None:
        raise not_found("incident_candidates", candidate_id)
    if candidate.status != "pending":
        raise state_conflict(
            "CANDIDATE_STATE_CONFLICT", f"候选事件 {candidate_id} 已处理（{candidate.status}）"
        )
    if payload.reject_reason not in REJECT_REASONS:
        raise state_conflict("CANDIDATE_STATE_CONFLICT", "驳回原因必须在三值枚举内（BR-04）")
    candidate.status = "rejected"
    candidate.reject_reason = payload.reject_reason
    candidate.decided_by = actor_id
    candidate.decided_at = utcnow()
    from huntai.domains.alerts import repository as _alerts_repo

    await _alerts_repo.bump_window_counters(session, candidate.correlation_rule_id, confirmed=False)
    await record_audit(
        session, action="incident_candidate.reject", resource_type="incident_candidates",
        resource_id=candidate.id,
        detail={"reject_reason": payload.reject_reason, "note": payload.note or ""},
        actor_id=actor_id,
    )
    return candidate


def _deduce_incident_severity(alerts) -> str:
    severities = {a.severity.value if hasattr(a.severity, "value") else a.severity for a in alerts}
    if "critical" in severities:
        return "P1"
    if "warning" in severities:
        return "P2"
    return "P3"


# ---------- 人工立项与状态机 ----------


async def create_manual_incident(
    session: AsyncSession, payload: IncidentCreateRequest, *, actor_id: int, publish=None
) -> Incident:
    incident = Incident(
        title=payload.title,
        severity=payload.severity,
        status="open",
        source="manual",
        team=payload.team,
        assignee_id=payload.assignee_id,
        created_by=actor_id,
    )
    session.add(incident)
    await session.flush()
    for alert_id in payload.related_alert_ids:
        alert = await alerts_repo.get_alert(session, alert_id)
        if alert is None:
            raise not_found("alerts", alert_id)
        session.add(
            IncidentAlert(incident_id=incident.id, alert_id=alert_id, linked_at=utcnow())
        )
        if alert.status != AlertStatus.RESOLVED:
            alert.status = AlertStatus.CORRELATED
    await record_audit(
        session, action="incident.create", resource_type="incidents", resource_id=incident.id,
        detail={"source": "manual", "title": incident.title}, actor_id=actor_id,
    )
    if publish is not None:
        from huntai.realtime.hub import RealtimeEvent

        await publish(
            RealtimeEvent(topic="incidents", name="incident.timeline.updated",
                          resource="incident", resource_id=incident.id, team=incident.team)
        )
    return incident


async def transition(
    session: AsyncSession, incident_id: int, action: str, *, actor_id: int,
    cancelled_reason: str | None = None, publish=None,
) -> Incident:
    incident = await repo.get_incident(session, incident_id)
    if incident is None:
        raise not_found("incidents", incident_id)
    target = _ACTION_TARGET[action]
    current = incident.status.value if hasattr(incident.status, "value") else incident.status
    if target not in ALLOWED_TRANSITIONS[current]:
        raise state_conflict(
            "INCIDENT_STATE_CONFLICT", f"事件 {incident_id} 不允许 {current} → {target}"
        )
    if action == "cancel":
        if not cancelled_reason:
            raise state_conflict("INCIDENT_STATE_CONFLICT", "cancelled 必填原因（D-10）")
        incident.cancelled_reason = cancelled_reason
    incident.status = target
    stamp_field = {
        "acknowledged": "acknowledged_at", "mitigated": "mitigated_at",
        "resolved": "resolved_at", "closed": "closed_at",
    }
    if target in stamp_field:
        setattr(incident, stamp_field[target], utcnow())
    await record_audit(
        session, action=f"incident.{action}", resource_type="incidents", resource_id=incident.id,
        detail={"from": current, "to": target}, actor_id=actor_id,
    )
    if publish is not None:
        from huntai.realtime.hub import RealtimeEvent

        await publish(
            RealtimeEvent(topic="incidents", name="incident.timeline.updated",
                          resource="incident", resource_id=incident.id, team=incident.team)
        )
    return incident


async def add_manual_note(
    session: AsyncSession, incident_id: int, note: str, *, actor_id: int, publish=None
) -> Incident:
    """人工处理记录（FR-32）：写入 audit_logs，详情时间线派生为 manual_note 节点。"""
    incident = await repo.get_incident(session, incident_id)
    if incident is None:
        raise not_found("incidents", incident_id)
    await record_audit(
        session, action="incident.note", resource_type="incidents", resource_id=incident.id,
        detail={"note": note}, actor_id=actor_id,
    )
    if publish is not None:
        from huntai.realtime.hub import RealtimeEvent

        await publish(
            RealtimeEvent(topic="incidents", name="incident.timeline.updated",
                          resource="incident", resource_id=incident.id, team=incident.team)
        )
    return incident


# ---------- 详情（时间线派生） ----------


async def build_detail(session: AsyncSession, incident: Incident) -> dict[str, Any]:
    links = await repo.linked_alerts(session, incident.id)
    alerts = await alerts_repo.alerts_by_ids(session, [link.alert_id for link in links])
    timeline: list[dict[str, Any]] = [
        {"occurred_at": incident.created_at, "kind": "status_changed",
         "summary": "事件立项", "actor_id": incident.created_by},
    ]
    for field, label in (
        ("acknowledged_at", "已确认（Ack）"), ("mitigated_at", "止血完成"),
        ("resolved_at", "根因恢复"), ("closed_at", "事件关闭"),
    ):
        stamp = getattr(incident, field)
        if stamp:
            timeline.append({"occurred_at": stamp, "kind": "status_changed", "summary": label})
    for link in links:
        timeline.append({"occurred_at": link.linked_at, "kind": "status_changed",
                         "summary": f"关联告警 #{link.alert_id}"})
    # 人工处理记录（FR-32）：以 audit_logs 为唯一存储，派生进时间线（不新增列/迁移）
    from huntai.domains.iam.models import AuditLog

    note_rows = (
        await session.execute(
            select(AuditLog)
            .where(
                AuditLog.action == "incident.note",
                AuditLog.resource_type == "incidents",
                AuditLog.resource_id == str(incident.id),
            )
            .order_by(AuditLog.id)
        )
    ).scalars().all()
    for note in note_rows:
        timeline.append({
            "occurred_at": note.created_at,
            "kind": "manual_note",
            "summary": str((note.detail or {}).get("note", "")),
            "actor_id": note.actor_user_id,
        })
    timeline.sort(key=lambda item: item["occurred_at"])
    related = [
        {
            "id": a.id, "fingerprint": a.fingerprint, "title": a.title,
            "severity": a.severity.value if hasattr(a.severity, "value") else a.severity,
            "status": a.status.value if hasattr(a.status, "value") else a.status,
        }
        for a in alerts
    ]
    return {"timeline": timeline, "related_alerts": related, "escalation_summary": {}}


# ---------- 状态页（BR-06） ----------


async def sync_status_page(
    session: AsyncSession, incident_id: int, *, actor_id: int | None, auto: bool = False,
    service_status: str | None = None,
) -> StatusPageEntry:
    incident = await repo.get_incident(session, incident_id)
    if incident is None:
        raise not_found("incidents", incident_id)
    entry = await repo.entry_for_incident(session, incident.id)
    if entry is None:
        entry = StatusPageEntry(
            incident_id=incident.id,
            title=incident.title,
            service_status=service_status or "degraded",
        )
        session.add(entry)
        await session.flush()
    elif service_status:
        entry.service_status = service_status
    session.add(
        StatusPageUpdate(
            entry_id=entry.id,
            message=f"事件状态：{incident.status.value if hasattr(incident.status, 'value') else incident.status}",
            status_snapshot=entry.service_status,
            posted_by=actor_id,
            posted_at=utcnow(),
        )
    )
    incident.status_page_sync = True
    await record_audit(
        session, action="incident.status_page_sync", resource_type="incidents",
        resource_id=incident.id, detail={"auto": auto}, actor_id=actor_id,
        actor_type=None if actor_id else "system",
    )
    return entry


async def undo_status_page(
    session: AsyncSession, incident_id: int, *, actor_id: int
) -> StatusPageEntry | None:
    """撤回最近同步：更新行置 is_revoked（留痕），条目保留（契约 /status-page/undo 返回条目）。"""
    incident = await repo.get_incident(session, incident_id)
    if incident is None:
        raise not_found("incidents", incident_id)
    entry = await repo.entry_for_incident(session, incident.id)
    if entry is not None:
        for update in await repo.entry_updates(session, entry.id):
            if not update.is_revoked:
                update.is_revoked = True
                update.revoked_at = utcnow()
                update.revoked_by = actor_id
                break
    incident.status_page_sync = False
    await record_audit(
        session, action="incident.status_page_undo", resource_type="incidents",
        resource_id=incident.id, detail={}, actor_id=actor_id,
    )
    return entry


# ---------- 复盘（L3） ----------


async def get_or_template_postmortem(session: AsyncSession, incident_id: int) -> Postmortem:
    incident = await repo.get_incident(session, incident_id)
    if incident is None:
        raise not_found("incidents", incident_id)
    existing = await repo.get_postmortem(session, incident_id)
    if existing is not None:
        return existing
    detail = await build_detail(session, incident)
    # 模板未持久化：返回零值行，PUT 时落库；时间戳取当前时刻满足契约必填
    stamp = utcnow()
    return Postmortem(
        id=0, incident_id=incident_id, timeline=detail["timeline"],
        root_cause="", created_by=incident.created_by or 0,
        created_at=stamp, updated_at=stamp,
    )


async def upsert_postmortem(
    session: AsyncSession, incident_id: int, payload: PostmortemUpdateRequest, *, actor_id: int
) -> Postmortem:
    incident = await repo.get_incident(session, incident_id)
    if incident is None:
        raise not_found("incidents", incident_id)
    postmortem = await repo.get_postmortem(session, incident_id)
    if postmortem is None:
        postmortem = Postmortem(
            incident_id=incident_id,
            timeline=payload.timeline or [],
            root_cause=payload.root_cause,
            created_by=actor_id,
        )
        session.add(postmortem)
        await session.flush()
    else:
        postmortem.root_cause = payload.root_cause
        if payload.timeline is not None:
            postmortem.timeline = payload.timeline
        for item in await repo.action_items(session, postmortem.id):
            await session.delete(item)
        await session.flush()
    for action in payload.action_items or []:
        session.add(
            PostmortemActionItem(
                postmortem_id=postmortem.id,
                content=str(action.get("content", "")),
                owner_id=action.get("owner_id"),
                status=str(action.get("status", "pending")),
            )
        )
    await record_audit(
        session, action="postmortem.update", resource_type="incidents",
        resource_id=incident_id, detail={"root_cause_len": len(payload.root_cause)},
        actor_id=actor_id,
    )
    return postmortem
