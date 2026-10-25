"""incidents/incident-candidates/status-page tag 路由（P2）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.app.deps import get_current_user, get_session, require_permission
from huntai.core.errors import not_found
from huntai.core.pagination import clamp_page
from huntai.core.security import Principal, TeamScope
from huntai.domains.incidents import repository as repo
from huntai.domains.incidents import service
from huntai.domains.incidents.schemas import (
    CandidateRejectRequest,
    IncidentCandidatePage,
    IncidentCandidateResponse,
    IncidentCancelRequest,
    IncidentCreateRequest,
    IncidentDetailResponse,
    IncidentNoteCreateRequest,
    IncidentPage,
    IncidentResponse,
    PostmortemActionItemResponse,
    PostmortemResponse,
    PostmortemUpdateRequest,
    StatusPageEntryCreateRequest,
    StatusPageEntryPage,
    StatusPageEntryResponse,
    StatusPageUpdateRequest,
    StatusPageUpdateResponse,
)

router = APIRouter()


def _publish(request: Request):
    async def publish(event) -> None:
        await request.app.state.hub.publish(event)

    return publish


def _incident_response(i) -> IncidentResponse:
    return IncidentResponse(
        id=i.id, title=i.title, severity=i.severity, status=i.status, source=i.source,
        candidate_id=i.candidate_id, correlation_rule_id=i.correlation_rule_id, team=i.team,
        assignee_id=i.assignee_id, created_by=i.created_by, status_page_sync=i.status_page_sync,
        cancelled_reason=i.cancelled_reason, acknowledged_at=i.acknowledged_at,
        mitigated_at=i.mitigated_at, resolved_at=i.resolved_at, closed_at=i.closed_at,
        created_at=i.created_at, updated_at=i.updated_at,
    )


def _candidate_response(c) -> IncidentCandidateResponse:
    return IncidentCandidateResponse(
        id=c.id, correlation_rule_id=c.correlation_rule_id, title=c.title,
        member_alert_ids=c.member_alert_ids, similarity=float(c.similarity) if c.similarity is not None else None,
        status=c.status.value if hasattr(c.status, "value") else c.status,
        reject_reason=c.reject_reason, decided_by=c.decided_by, decided_at=c.decided_at,
        created_at=c.created_at,
    )


def _assert_visible(incident, scope: TeamScope | None) -> None:
    if incident is None:
        raise not_found("incidents", "?")
    if scope is not None and incident.team is not None and incident.team != scope.team:
        raise not_found("incidents", incident.id)


# ---------- 候选事件 ----------


@router.get("/incident-candidates", response_model=IncidentCandidatePage)
async def list_incident_candidates(
    status: str | None = "pending",
    correlation_rule_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
    scope: TeamScope | None = Depends(require_permission("incident_candidates", "read")),
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    candidates, total = await repo.list_candidates(
        session, status=status, correlation_rule_id=correlation_rule_id, offset=offset, limit=limit
    )
    items = []
    for candidate in candidates:
        if scope is not None:
            members = await repo_get_alerts_teams(session, candidate)
            if members and scope.team not in members:
                continue
        items.append(_candidate_response(candidate))
    return IncidentCandidatePage.build(items, total=total, offset=offset, limit=limit)


async def repo_get_alerts_teams(session, candidate) -> set[str]:
    from huntai.domains.alerts import repository as alerts_repo

    alerts = await alerts_repo.alerts_by_ids(session, list(candidate.member_alert_ids))
    return {
        str((a.enrichments or {}).get("team")) for a in alerts if (a.enrichments or {}).get("team")
    }


@router.post("/incident-candidates/{candidate_id}/confirm", status_code=201, response_model=IncidentResponse)
async def confirm_incident_candidate(
    request: Request,
    candidate_id: int,
    scope: TeamScope | None = Depends(require_permission("incident_candidates", "decide")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    incident = await service.confirm_candidate(
        session, candidate_id, actor_id=principal.user_id, publish=_publish(request)
    )
    return _incident_response(incident)


@router.post("/incident-candidates/{candidate_id}/reject", response_model=IncidentCandidateResponse)
async def reject_incident_candidate(
    candidate_id: int,
    payload: CandidateRejectRequest,
    scope: TeamScope | None = Depends(require_permission("incident_candidates", "decide")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    candidate = await service.reject_candidate(
        session, candidate_id, payload, actor_id=principal.user_id
    )
    return _candidate_response(candidate)


# ---------- 事件 ----------


@router.get("/incidents", response_model=IncidentPage)
async def list_incidents(
    status: str | None = None,
    severity: str | None = None,
    team: str | None = None,
    offset: int = 0,
    limit: int = 50,
    scope: TeamScope | None = Depends(require_permission("incidents", "read")),
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    incidents, total = await repo.list_incidents(
        session, status=status, severity=severity, team=team,
        team_scope=scope.team if scope else None, offset=offset, limit=limit,
    )
    return IncidentPage.build(
        [_incident_response(i) for i in incidents], total=total, offset=offset, limit=limit
    )


@router.post("/incidents", status_code=201, response_model=IncidentResponse)
async def create_incident(
    request: Request,
    payload: IncidentCreateRequest,
    scope: TeamScope | None = Depends(require_permission("incidents", "write")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    incident = await service.create_manual_incident(
        session, payload, actor_id=principal.user_id, publish=_publish(request)
    )
    return _incident_response(incident)


@router.get("/incidents/{incident_id}", response_model=IncidentDetailResponse)
async def get_incident(
    incident_id: int,
    scope: TeamScope | None = Depends(require_permission("incidents", "read")),
    session: AsyncSession = Depends(get_session),
):
    incident = await repo.get_incident(session, incident_id)
    _assert_visible(incident, scope)
    detail = await service.build_detail(session, incident)
    base = _incident_response(incident)
    return IncidentDetailResponse(**base.model_dump(), **detail)


@router.post(
    "/incidents/{incident_id}/notes", response_model=IncidentResponse, status_code=201
)
async def add_incident_note(
    request: Request,
    incident_id: int,
    payload: IncidentNoteCreateRequest,
    scope: TeamScope | None = Depends(require_permission("incidents", "transition")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """人工处理记录（FR-32）：写 audit_logs 并由详情时间线派生 manual_note 节点。"""
    incident = await repo.get_incident(session, incident_id)
    _assert_visible(incident, scope)
    incident = await service.add_manual_note(
        session, incident_id, payload.note, actor_id=principal.user_id,
        publish=_publish(request),
    )
    return _incident_response(incident)


async def _transition(request, incident_id: int, action: str, principal, scope, session, body=None):
    incident = await service.transition(
        session, incident_id, action, actor_id=principal.user_id,
        cancelled_reason=(body.cancelled_reason if body else None),
        publish=_publish(request),
    )
    return _incident_response(incident)


@router.post("/incidents/{incident_id}/acknowledge", response_model=IncidentResponse)
async def acknowledge_incident(
    request: Request, incident_id: int,
    scope: TeamScope | None = Depends(require_permission("incidents", "transition")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _transition(request, incident_id, "acknowledge", principal, scope, session)


@router.post("/incidents/{incident_id}/mitigate", response_model=IncidentResponse)
async def mitigate_incident(
    request: Request, incident_id: int,
    scope: TeamScope | None = Depends(require_permission("incidents", "transition")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _transition(request, incident_id, "mitigate", principal, scope, session)


@router.post("/incidents/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(
    request: Request, incident_id: int,
    scope: TeamScope | None = Depends(require_permission("incidents", "transition")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _transition(request, incident_id, "resolve", principal, scope, session)


@router.post("/incidents/{incident_id}/close", response_model=IncidentResponse)
async def close_incident(
    request: Request, incident_id: int,
    scope: TeamScope | None = Depends(require_permission("incidents", "transition")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _transition(request, incident_id, "close", principal, scope, session)


@router.post("/incidents/{incident_id}/cancel", response_model=IncidentResponse)
async def cancel_incident(
    request: Request, incident_id: int, payload: IncidentCancelRequest,
    scope: TeamScope | None = Depends(require_permission("incidents", "transition")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _transition(request, incident_id, "cancel", principal, scope, session, body=payload)


@router.post("/incidents/{incident_id}/status-page/sync", response_model=StatusPageEntryResponse)
async def sync_incident_status_page(
    incident_id: int,
    payload: dict | None = None,
    _scope: TeamScope | None = Depends(require_permission("incidents", "status_page")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    entry = await service.sync_status_page(
        session, incident_id, actor_id=principal.user_id,
        service_status=(payload or {}).get("service_status"),
    )
    return _entry_response(entry)


@router.post(
    "/incidents/{incident_id}/status-page/undo", response_model=StatusPageEntryResponse
)
async def undo_incident_status_page(
    incident_id: int,
    _scope: TeamScope | None = Depends(require_permission("incidents", "status_page")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    entry = await service.undo_status_page(session, incident_id, actor_id=principal.user_id)
    if entry is None:
        raise not_found("status_page_entries", incident_id)
    return _entry_response(entry, updates=await repo.entry_updates(session, entry.id))


@router.post("/incidents/{incident_id}/ai-investigation", status_code=201)
async def start_incident_ai_investigation(
    incident_id: int,
    request: Request,
    _scope: TeamScope | None = Depends(require_permission("incidents", "transition")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """A2（P3 概要级）：创建 investigate 任务；执行依赖已配置模型，无模型按 NoAI 降级。"""
    from huntai.domains.ai import service as ai_service
    from huntai.domains.ai.schemas import AITaskResponse
    from huntai.domains.incidents import repository as incident_repo

    incident = await incident_repo.get_incident(session, incident_id)
    _assert_visible(incident, _scope)

    async def enqueue(job_name, *args, **kwargs):
        from huntai.core.config import QUEUE_BY_JOB

        pool = request.app.state.arq_pool
        queue = kwargs.pop("_queue", None) or QUEUE_BY_JOB.get(job_name)
        return await pool.enqueue_job(job_name, *args, _queue_name=queue)

    task = await ai_service.create_investigation_task(
        session, incident, requested_by=principal.user_id,
        settings=request.app.state.settings, enqueue=enqueue,
    )
    return AITaskResponse(
        id=task.id, type=task.type, status=task.status, context_refs=task.context_refs,
        finding_id=task.finding_id, incident_id=task.incident_id, budget=task.budget,
        calls_used=task.calls_used, tokens_used=task.tokens_used,
        requires_approval=task.requires_approval, requested_by=task.requested_by,
        approval_deadline_at=task.approval_deadline_at, approved_by=task.approved_by,
        decided_at=task.decided_at, result=task.result, is_partial=task.is_partial,
        error=task.error, created_at=task.created_at, updated_at=task.updated_at,
        finished_at=task.finished_at,
    )


# ---------- 复盘 ----------


@router.get("/incidents/{incident_id}/postmortem", response_model=PostmortemResponse)
async def get_incident_postmortem(
    incident_id: int,
    scope: TeamScope | None = Depends(require_permission("incidents", "postmortem_read")),
    session: AsyncSession = Depends(get_session),
):
    postmortem = await service.get_or_template_postmortem(session, incident_id)
    items = await repo.action_items(session, postmortem.id) if postmortem.id else []
    return PostmortemResponse(
        id=postmortem.id, incident_id=postmortem.incident_id, timeline=postmortem.timeline,
        root_cause=postmortem.root_cause,
        action_items=[
            PostmortemActionItemResponse(
                id=item.id, content=item.content, owner_id=item.owner_id,
                due_date=str(item.due_date) if item.due_date else None,
                status=item.status, created_at=item.created_at, updated_at=item.updated_at,
            )
            for item in items
        ],
        created_by=postmortem.created_by,
        created_at=postmortem.created_at, updated_at=postmortem.updated_at,
    )


@router.put("/incidents/{incident_id}/postmortem", response_model=PostmortemResponse)
async def update_incident_postmortem(
    incident_id: int, payload: PostmortemUpdateRequest,
    scope: TeamScope | None = Depends(require_permission("incidents", "postmortem_write")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    postmortem = await service.upsert_postmortem(
        session, incident_id, payload, actor_id=principal.user_id
    )
    items = await repo.action_items(session, postmortem.id)
    return PostmortemResponse(
        id=postmortem.id, incident_id=postmortem.incident_id, timeline=postmortem.timeline,
        root_cause=postmortem.root_cause,
        action_items=[
            PostmortemActionItemResponse(
                id=item.id, content=item.content, owner_id=item.owner_id,
                due_date=str(item.due_date) if item.due_date else None,
                status=item.status, created_at=item.created_at, updated_at=item.updated_at,
            )
            for item in items
        ],
        created_by=postmortem.created_by, created_at=postmortem.created_at,
        updated_at=postmortem.updated_at,
    )


# ---------- 状态页条目 ----------


def _entry_response(e, updates=None) -> StatusPageEntryResponse:
    return StatusPageEntryResponse(
        id=e.id, incident_id=e.incident_id, title=e.title, visibility=e.visibility,
        service_status=e.service_status,
        updates=(
            [
                StatusPageUpdateResponse(
                    id=u.id, entry_id=u.entry_id, message=u.message,
                    status_snapshot=u.status_snapshot, posted_by=u.posted_by,
                    posted_at=u.posted_at, is_revoked=u.is_revoked,
                    revoked_at=u.revoked_at, revoked_by=u.revoked_by,
                )
                for u in updates
            ]
            if updates is not None
            else None
        ),
        created_at=e.created_at, updated_at=e.updated_at,
    )


@router.get("/status-page/entries", response_model=StatusPageEntryPage, tags=["status-page"])
async def list_status_page_entries(
    visibility: str | None = None,
    offset: int = 0,
    limit: int = 50,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """任何已认证角色可见（viewer 仅 public，服务层过滤）。"""
    viewer_public_only = "viewer" in principal.roles and "admin" not in principal.roles
    offset, limit = clamp_page(offset, limit)
    entries, total = await repo.list_status_entries(
        session, visibility=visibility, viewer_public_only=viewer_public_only,
        offset=offset, limit=limit,
    )
    return StatusPageEntryPage.build(
        [_entry_response(e) for e in entries], total=total, offset=offset, limit=limit
    )


@router.post("/status-page/entries", response_model=StatusPageEntryResponse, status_code=201, tags=["status-page"], dependencies=[Depends(require_permission("status_page", "write"))])
async def create_status_page_entry(
    payload: StatusPageEntryCreateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    incident = await repo.get_incident(session, payload.incident_id)
    if incident is None:
        raise not_found("incidents", payload.incident_id)
    from huntai.domains.incidents import service as incident_service

    entry = await incident_service.sync_status_page(
        session, payload.incident_id, actor_id=principal.user_id,
        service_status=payload.service_status,
    )
    entry.title = payload.title
    entry.visibility = payload.visibility
    return _entry_response(entry)


@router.get("/status-page/entries/{entry_id}", response_model=StatusPageEntryResponse, tags=["status-page"])
async def get_status_page_entry(
    entry_id: int,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    entry = await repo.get_status_entry(session, entry_id)
    if entry is None:
        raise not_found("status_page_entries", entry_id)
    if "viewer" in principal.roles and "admin" not in principal.roles and entry.visibility != "public":
        raise not_found("status_page_entries", entry_id)
    return _entry_response(entry, updates=await repo.entry_updates(session, entry.id))


@router.put("/status-page/entries/{entry_id}", response_model=StatusPageEntryResponse, tags=["status-page"], dependencies=[Depends(require_permission("status_page", "write"))])
async def update_status_page_entry(
    entry_id: int, payload: StatusPageUpdateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    entry = await repo.get_status_entry(session, entry_id)
    if entry is None:
        raise not_found("status_page_entries", entry_id)
    for field in ("title", "visibility", "service_status"):
        value = getattr(payload, field)
        if value is not None:
            setattr(entry, field, value)
    return _entry_response(entry)


@router.delete("/status-page/entries/{entry_id}", status_code=204, tags=["status-page"], dependencies=[Depends(require_permission("status_page", "write"))])
async def delete_status_page_entry(
    entry_id: int,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    entry = await repo.get_status_entry(session, entry_id)
    if entry is None:
        raise not_found("status_page_entries", entry_id)
    await session.delete(entry)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
