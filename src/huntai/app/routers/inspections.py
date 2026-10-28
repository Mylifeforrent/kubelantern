"""inspections/findings tag 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.app.deps import get_current_user, get_session, require_permission
from huntai.app.routing import TransactionalAPIRoute
from huntai.core.errors import not_found
from huntai.core.pagination import clamp_page
from huntai.core.security import Principal, TeamScope
from huntai.domains.inspections import repository as repo
from huntai.domains.inspections import service
from huntai.domains.inspections.schemas import (
    FindingIgnoreRequest,
    FindingPage,
    FindingResponse,
    InspectionPolicyCreateRequest,
    InspectionPolicyPage,
    InspectionPolicyResponse,
    InspectionPolicyUpdateRequest,
    InspectionRuleCreateRequest,
    InspectionRulePage,
    InspectionRuleResponse,
    InspectionRuleUpdateRequest,
    InspectionRunPage,
    InspectionRunResponse,
)

router = APIRouter(route_class=TransactionalAPIRoute)


def _rule_response(r) -> InspectionRuleResponse:
    return InspectionRuleResponse(
        id=r.id, code=r.code, name=r.name, category=r.category,
        severity_default=r.severity_default.value if hasattr(r.severity_default, "value") else r.severity_default,
        k8s_version_fit=r.k8s_version_fit, description=r.description, enabled=r.enabled,
        created_at=r.created_at, updated_at=r.updated_at,
    )


async def _policy_response(session: AsyncSession, p) -> InspectionPolicyResponse:
    return InspectionPolicyResponse(
        id=p.id, cluster_id=p.cluster_id, name=p.name, schedule=p.schedule,
        ai_explain_level=p.ai_explain_level.value if hasattr(p.ai_explain_level, "value") else p.ai_explain_level,
        rule_ids=await repo.policy_rule_ids(session, p.id),
        enabled=p.enabled, created_at=p.created_at, updated_at=p.updated_at,
    )


def _run_response(r) -> InspectionRunResponse:
    return InspectionRunResponse(
        id=r.id, policy_id=r.policy_id, cluster_id=r.cluster_id,
        trigger=r.trigger.value if hasattr(r.trigger, "value") else r.trigger,
        status=r.status.value if hasattr(r.status, "value") else r.status,
        result=r.result, findings_count=r.findings_count, error=r.error,
        started_at=r.started_at, finished_at=r.finished_at,
    )


def _finding_response(f) -> FindingResponse:
    return FindingResponse(
        id=f.id, run_id=f.run_id, cluster_id=f.cluster_id, rule_code=f.rule_code,
        resource_ref=f.resource_ref,
        severity=f.severity.value if hasattr(f.severity, "value") else f.severity,
        raw_error=f.raw_error,
        status=f.status.value if hasattr(f.status, "value") else f.status,
        assignee_id=f.assignee_id, ignored_reason=f.ignored_reason,
        converted_alert_id=f.converted_alert_id, resolved_at=f.resolved_at,
        created_at=f.created_at, updated_at=f.updated_at,
    )


# ---------- 规则库 ----------


@router.get("/inspection-rules", response_model=InspectionRulePage)
async def list_inspection_rules(
    category: str | None = None, enabled: bool | None = None, offset: int = 0, limit: int = 50,
    _scope: TeamScope | None = Depends(require_permission("inspection_rules", "read")),
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    rules, total = await repo.list_rules(session, category=category, enabled=enabled, offset=offset, limit=limit)
    return InspectionRulePage.build(
        [_rule_response(r) for r in rules], total=total, offset=offset, limit=limit
    )


@router.post("/inspection-rules", response_model=InspectionRuleResponse, status_code=201, dependencies=[Depends(require_permission("inspection_rules", "write"))])
async def create_inspection_rule(
    payload: InspectionRuleCreateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _rule_response(await service.create_rule(session, payload, actor_id=principal.user_id))


@router.get("/inspection-rules/{rule_id}", response_model=InspectionRuleResponse, dependencies=[Depends(require_permission("inspection_rules", "read"))])
async def get_inspection_rule(rule_id: int, session: AsyncSession = Depends(get_session)):
    rule = await repo.get_rule(session, rule_id)
    if rule is None:
        raise not_found("inspection_rules", rule_id)
    return _rule_response(rule)


@router.put("/inspection-rules/{rule_id}", response_model=InspectionRuleResponse, dependencies=[Depends(require_permission("inspection_rules", "write"))])
async def update_inspection_rule(
    rule_id: int, payload: InspectionRuleUpdateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _rule_response(await service.update_rule(session, rule_id, payload, actor_id=principal.user_id))


@router.delete("/inspection-rules/{rule_id}", status_code=204, dependencies=[Depends(require_permission("inspection_rules", "write"))])
async def delete_inspection_rule(
    rule_id: int, principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await service.delete_rule(session, rule_id, actor_id=principal.user_id)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


# ---------- 策略 ----------


@router.get("/inspection-policies", response_model=InspectionPolicyPage, dependencies=[Depends(require_permission("inspection_policies", "read"))])
async def list_inspection_policies(
    cluster_id: int | None = None, enabled: bool | None = None, offset: int = 0, limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    policies, total = await repo.list_policies(session, cluster_id=cluster_id, enabled=enabled, offset=offset, limit=limit)
    items = [await _policy_response(session, p) for p in policies]
    return InspectionPolicyPage.build(items, total=total, offset=offset, limit=limit)


@router.post("/inspection-policies", response_model=InspectionPolicyResponse, status_code=201, dependencies=[Depends(require_permission("inspection_policies", "write"))])
async def create_inspection_policy(
    payload: InspectionPolicyCreateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    policy = await service.create_policy(session, payload, actor_id=principal.user_id)
    return await _policy_response(session, policy)


@router.get("/inspection-policies/{policy_id}", response_model=InspectionPolicyResponse, dependencies=[Depends(require_permission("inspection_policies", "read"))])
async def get_inspection_policy(policy_id: int, session: AsyncSession = Depends(get_session)):
    policy = await repo.get_policy(session, policy_id)
    if policy is None:
        raise not_found("inspection_policies", policy_id)
    return await _policy_response(session, policy)


@router.put("/inspection-policies/{policy_id}", response_model=InspectionPolicyResponse, dependencies=[Depends(require_permission("inspection_policies", "write"))])
async def update_inspection_policy(
    policy_id: int, payload: InspectionPolicyUpdateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    policy = await service.update_policy(session, policy_id, payload, actor_id=principal.user_id)
    return await _policy_response(session, policy)


@router.delete("/inspection-policies/{policy_id}", status_code=204, dependencies=[Depends(require_permission("inspection_policies", "write"))])
async def delete_inspection_policy(
    policy_id: int, principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await service.delete_policy(session, policy_id, actor_id=principal.user_id)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.post("/inspection-policies/{policy_id}/run", response_model=InspectionRunResponse, status_code=201, dependencies=[Depends(require_permission("inspection_policies", "run"))])
async def run_inspection_policy(
    policy_id: int,
    request: Request,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    async def enqueue(job_name: str, *args, **kwargs):
        from huntai.core.config import QUEUE_BY_JOB

        queue = kwargs.pop("_queue", None) or QUEUE_BY_JOB.get(job_name)
        return await request.app.state.arq_pool.enqueue_job(job_name, *args, _queue_name=queue)

    run = await service.trigger_run(session, policy_id, actor_id=principal.user_id, enqueue=enqueue)
    return _run_response(run)


# ---------- 执行与发现 ----------


@router.get("/inspection-runs", response_model=InspectionRunPage, dependencies=[Depends(require_permission("inspection_runs", "read"))])
async def list_inspection_runs(
    cluster_id: int | None = None, policy_id: int | None = None, status: str | None = None,
    offset: int = 0, limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    runs, total = await repo.list_runs(
        session, cluster_id=cluster_id, policy_id=policy_id, status=status, offset=offset, limit=limit
    )
    return InspectionRunPage.build(
        [_run_response(r) for r in runs], total=total, offset=offset, limit=limit
    )


@router.get("/inspection-runs/{run_id}", response_model=InspectionRunResponse, dependencies=[Depends(require_permission("inspection_runs", "read"))])
async def get_inspection_run(run_id: int, session: AsyncSession = Depends(get_session)):
    run = await repo.get_run(session, run_id)
    if run is None:
        raise not_found("inspection_runs", run_id)
    return _run_response(run)


@router.get("/findings", response_model=FindingPage)
async def list_findings(
    cluster_id: int | None = None, rule_code: str | None = None, severity: str | None = None,
    status: str | None = None, offset: int = 0, limit: int = 50,
    scope: TeamScope | None = Depends(require_permission("findings", "read")),
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    findings, total = await repo.list_findings(
        session, cluster_id=cluster_id, rule_code=rule_code, severity=severity,
        status=status, offset=offset, limit=limit,
    )
    return FindingPage.build(
        [_finding_response(f) for f in findings], total=total, offset=offset, limit=limit
    )


@router.post("/findings/{finding_id}/ack", response_model=FindingResponse)
async def ack_finding(
    request: Request, finding_id: int,
    scope: TeamScope | None = Depends(require_permission("findings", "acknowledge")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    async def publish(event) -> None:
        await request.app.state.hub.publish(event)

    return _finding_response(
        await service.ack_finding(session, finding_id, actor_id=principal.user_id, publish=publish)
    )


@router.post("/findings/{finding_id}/ignore", response_model=FindingResponse, dependencies=[Depends(require_permission("findings", "ignore"))])
async def ignore_finding(
    finding_id: int, payload: FindingIgnoreRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _finding_response(
        await service.ignore_finding(session, finding_id, payload.ignored_reason, actor_id=principal.user_id)
    )


@router.post("/findings/{finding_id}/reopen", response_model=FindingResponse, dependencies=[Depends(require_permission("findings", "reopen"))])
async def reopen_finding(
    finding_id: int,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _finding_response(await service.reopen_finding(session, finding_id, actor_id=principal.user_id))


@router.post("/findings/{finding_id}/explain", status_code=201, dependencies=[Depends(require_permission("findings", "explain"))])
async def explain_finding(
    finding_id: int,
    request: Request,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """A1 一键 AI 解释（P1）：创建 explain 任务并投递 q-ai。"""
    from huntai.domains.ai import service as ai_service
    from huntai.domains.ai.schemas import AITaskResponse

    finding = await repo.get_finding(session, finding_id)
    if finding is None:
        raise not_found("findings", finding_id)

    async def enqueue(job_name: str, *args, **kwargs):
        from huntai.core.config import QUEUE_BY_JOB

        queue = kwargs.pop("_queue", None) or QUEUE_BY_JOB.get(job_name)
        return await request.app.state.arq_pool.enqueue_job(job_name, *args, _queue_name=queue)

    task = await ai_service.create_task_for_finding(
        session, finding, requested_by=principal.user_id,
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
