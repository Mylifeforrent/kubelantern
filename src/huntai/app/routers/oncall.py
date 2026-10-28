"""oncall/notifications/workflows tag 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.app.deps import get_current_user, get_session, require_permission
from huntai.app.routing import TransactionalAPIRoute
from huntai.core.errors import not_found
from huntai.core.pagination import clamp_page
from huntai.core.security import Principal, TeamScope
from huntai.domains.notifications import service as notification_service
from huntai.domains.oncall import repository as oncall_repo
from huntai.domains.oncall import service
from huntai.domains.oncall.schemas import (
    EscalationPolicyCreateRequest,
    EscalationPolicyPage,
    EscalationPolicyResponse,
    EscalationPolicyUpdateRequest,
    NotificationRecordPage,
    NotificationRecordResponse,
    OnCallScheduleCreateRequest,
    OnCallSchedulePage,
    OnCallScheduleResponse,
    OnCallScheduleUpdateRequest,
)
from huntai.domains.workflows import service as workflow_service
from huntai.domains.workflows.service import (
    WorkflowCreateRequest,
    WorkflowFromDescriptionRequest,
    WorkflowPage,
    WorkflowResponse,
    WorkflowRunCreateRequest,
    WorkflowRunResponse,
    WorkflowVersionCreateRequest,
)

router = APIRouter(route_class=TransactionalAPIRoute)


def _schedule_response(s) -> OnCallScheduleResponse:
    return OnCallScheduleResponse(
        id=s.id, name=s.name, team=s.team, rotation_rules=s.rotation_rules,
        calendar=s.calendar, overrides=s.overrides, enabled=s.enabled,
        created_at=s.created_at, updated_at=s.updated_at,
    )


def _policy_response(p) -> EscalationPolicyResponse:
    return EscalationPolicyResponse(
        id=p.id, name=p.name, schedule_id=p.schedule_id, levels=p.levels,
        channel_fallbacks=p.channel_fallbacks, enabled=p.enabled,
        created_at=p.created_at, updated_at=p.updated_at,
    )


# ---------- 排班 ----------


@router.get("/oncall-schedules", response_model=OnCallSchedulePage, dependencies=[Depends(require_permission("oncall_schedules", "read"))])
async def list_oncall_schedules(
    team: str | None = None, offset: int = 0, limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    schedules, total = await oncall_repo.list_schedules(session, team=team, offset=offset, limit=limit)
    return OnCallSchedulePage.build(
        [_schedule_response(s) for s in schedules], total=total, offset=offset, limit=limit
    )


@router.post("/oncall-schedules", response_model=OnCallScheduleResponse, status_code=201, dependencies=[Depends(require_permission("oncall_schedules", "write"))])
async def create_oncall_schedule(
    payload: OnCallScheduleCreateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _schedule_response(await service.create_schedule(session, payload, actor_id=principal.user_id))


@router.get("/oncall-schedules/{schedule_id}", response_model=OnCallScheduleResponse, dependencies=[Depends(require_permission("oncall_schedules", "read"))])
async def get_oncall_schedule(schedule_id: int, session: AsyncSession = Depends(get_session)):
    schedule = await oncall_repo.get_schedule(session, schedule_id)
    if schedule is None:
        raise not_found("oncall_schedules", schedule_id)
    return _schedule_response(schedule)


@router.put("/oncall-schedules/{schedule_id}", response_model=OnCallScheduleResponse, dependencies=[Depends(require_permission("oncall_schedules", "write"))])
async def update_oncall_schedule(
    schedule_id: int, payload: OnCallScheduleUpdateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _schedule_response(
        await service.update_schedule(session, schedule_id, payload, actor_id=principal.user_id)
    )


@router.delete("/oncall-schedules/{schedule_id}", status_code=204, dependencies=[Depends(require_permission("oncall_schedules", "write"))])
async def delete_oncall_schedule(
    schedule_id: int, principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await service.delete_schedule(session, schedule_id, actor_id=principal.user_id)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


# ---------- 升级策略 ----------


@router.get("/escalation-policies", response_model=EscalationPolicyPage, dependencies=[Depends(require_permission("escalation_policies", "read"))])
async def list_escalation_policies(
    schedule_id: int | None = None, offset: int = 0, limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    policies, total = await oncall_repo.list_policies(session, schedule_id=schedule_id, offset=offset, limit=limit)
    return EscalationPolicyPage.build(
        [_policy_response(p) for p in policies], total=total, offset=offset, limit=limit
    )


@router.post("/escalation-policies", response_model=EscalationPolicyResponse, status_code=201, dependencies=[Depends(require_permission("escalation_policies", "write"))])
async def create_escalation_policy(
    payload: EscalationPolicyCreateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _policy_response(await service.create_escalation_policy(session, payload, actor_id=principal.user_id))


@router.get("/escalation-policies/{policy_id}", response_model=EscalationPolicyResponse, dependencies=[Depends(require_permission("escalation_policies", "read"))])
async def get_escalation_policy(policy_id: int, session: AsyncSession = Depends(get_session)):
    policy = await oncall_repo.get_policy(session, policy_id)
    if policy is None:
        raise not_found("escalation_policies", policy_id)
    return _policy_response(policy)


@router.put("/escalation-policies/{policy_id}", response_model=EscalationPolicyResponse, dependencies=[Depends(require_permission("escalation_policies", "write"))])
async def update_escalation_policy(
    policy_id: int, payload: EscalationPolicyUpdateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _policy_response(
        await service.update_escalation_policy(session, policy_id, payload, actor_id=principal.user_id)
    )


@router.delete("/escalation-policies/{policy_id}", status_code=204, dependencies=[Depends(require_permission("escalation_policies", "write"))])
async def delete_escalation_policy(
    policy_id: int, principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await service.delete_escalation_policy(session, policy_id, actor_id=principal.user_id)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


# ---------- 通知记录（P2） ----------


@router.get("/notification-records", response_model=NotificationRecordPage, dependencies=[Depends(require_permission("notification_records", "read"))])
async def list_notification_records(
    alert_id: int | None = None, incident_id: int | None = None, status: str | None = None,
    offset: int = 0, limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    records, total = await notification_service.list_records(
        session, alert_id=alert_id, incident_id=incident_id, status=status, offset=offset, limit=limit
    )
    items = [
        NotificationRecordResponse(
            id=r.id, channel=r.channel, target=r.target, content_digest=r.content_digest,
            status=r.status.value if hasattr(r.status, "value") else r.status,
            ack_action=r.ack_action, ack_at=r.ack_at, alert_id=r.alert_id,
            incident_id=r.incident_id, escalation_policy_id=r.escalation_policy_id,
            escalation_level=r.escalation_level, error=r.error, created_at=r.created_at,
        )
        for r in records
    ]
    return NotificationRecordPage.build(items, total=total, offset=offset, limit=limit)


# ---------- Workflow（P3 薄层） ----------


def _workflow_response(w) -> WorkflowResponse:
    return WorkflowResponse(
        id=w.id, name=w.name, version=w.version, yaml=w.yaml,
        source=w.source.value if hasattr(w.source, "value") else w.source,
        approved_by=w.approved_by, enabled=w.enabled, is_current=w.is_current,
        created_by=w.created_by, created_at=w.created_at, updated_at=w.updated_at,
    )


def _run_response(r) -> WorkflowRunResponse:
    return WorkflowRunResponse(
        id=r.id, workflow_id=r.workflow_id, workflow_version=r.workflow_version,
        yaml_snapshot=r.yaml_snapshot,
        trigger_type=r.trigger_type.value if hasattr(r.trigger_type, "value") else r.trigger_type,
        triggered_by=r.triggered_by, alert_id=r.alert_id, incident_id=r.incident_id,
        status=r.status.value if hasattr(r.status, "value") else r.status,
        steps_log=r.steps_log, error=r.error, started_at=r.started_at,
        finished_at=r.finished_at, created_at=r.created_at,
    )


@router.get("/workflows", response_model=WorkflowPage, tags=["workflows"], dependencies=[Depends(require_permission("workflows", "read"))])
async def list_workflows(offset: int = 0, limit: int = 50, session: AsyncSession = Depends(get_session)):
    offset, limit = clamp_page(offset, limit)
    workflows, total = await workflow_service.list_workflows(session, offset=offset, limit=limit)
    return WorkflowPage.build(
        [_workflow_response(w) for w in workflows], total=total, offset=offset, limit=limit
    )


@router.post("/workflows", response_model=WorkflowResponse, status_code=201, tags=["workflows"], dependencies=[Depends(require_permission("workflows", "write"))])
async def create_workflow(
    payload: WorkflowCreateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _workflow_response(
        await workflow_service.create_workflow(session, payload, actor_id=principal.user_id)
    )


@router.post("/workflows/{workflow_id}/versions", response_model=WorkflowResponse, status_code=201, tags=["workflows"], dependencies=[Depends(require_permission("workflows", "write"))])
async def create_workflow_version(
    workflow_id: int, payload: WorkflowVersionCreateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _workflow_response(
        await workflow_service.create_version(session, workflow_id, payload.yaml, actor_id=principal.user_id)
    )


@router.post("/workflows/from-description", status_code=201, tags=["workflows"], dependencies=[Depends(require_permission("workflows", "write"))])
async def generate_workflow_from_description(
    payload: WorkflowFromDescriptionRequest,
    request: Request,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """A3（P3 概要级）：创建 workflow_gen 任务；产出草稿待确认（BR-05），执行依赖模型配置。"""
    from huntai.domains.ai import service as ai_service
    from huntai.domains.ai.schemas import AITaskResponse

    async def enqueue(job_name, *args, **kwargs):
        from huntai.core.config import QUEUE_BY_JOB

        queue = kwargs.pop("_queue", None) or QUEUE_BY_JOB.get(job_name)
        return await request.app.state.arq_pool.enqueue_job(job_name, *args, _queue_name=queue)

    task = await ai_service.create_workflow_gen_task(
        session, payload.description, requested_by=principal.user_id,
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


@router.post("/workflows/{workflow_id}/approve", response_model=WorkflowResponse, tags=["workflows"], dependencies=[Depends(require_permission("workflows", "write"))])
async def approve_workflow(
    workflow_id: int,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _workflow_response(
        await workflow_service.approve_workflow(session, workflow_id, actor_id=principal.user_id)
    )


@router.post("/workflow-runs", response_model=WorkflowRunResponse, status_code=201, tags=["workflows"], dependencies=[Depends(require_permission("workflow_runs", "write"))])
async def create_workflow_run(
    payload: WorkflowRunCreateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _run_response(
        await workflow_service.create_run(session, payload, actor_id=principal.user_id)
    )


@router.get("/workflow-runs/{run_id}", response_model=WorkflowRunResponse, tags=["workflows"], dependencies=[Depends(require_permission("workflow_runs", "read"))])
async def get_workflow_run(run_id: int, session: AsyncSession = Depends(get_session)):
    run = await workflow_service.get_run(session, run_id)
    if run is None:
        raise not_found("workflow_runs", run_id)
    return _run_response(run)
