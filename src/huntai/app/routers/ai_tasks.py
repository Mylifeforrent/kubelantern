"""ai-tasks tag 路由（P1；路径按契约 /ai/tasks，C3）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.app.deps import get_current_user, get_session, require_permission
from huntai.app.routing import TransactionalAPIRoute
from huntai.core.errors import not_found
from huntai.core.pagination import clamp_page
from huntai.core.security import Principal, TeamScope
from huntai.domains.ai import repository as repo
from huntai.domains.ai import service
from huntai.domains.ai.schemas import (
    AICallLogPage,
    AICallLogResponse,
    AITaskCancelRequest,
    AITaskPage,
    AITaskResponse,
)

router = APIRouter(route_class=TransactionalAPIRoute)


def _task_response(t) -> AITaskResponse:
    return AITaskResponse(
        id=t.id, type=t.type.value if hasattr(t.type, "value") else t.type,
        status=t.status.value if hasattr(t.status, "value") else t.status,
        context_refs=t.context_refs, finding_id=t.finding_id, incident_id=t.incident_id,
        budget=t.budget, calls_used=t.calls_used, tokens_used=t.tokens_used,
        requires_approval=t.requires_approval, requested_by=t.requested_by,
        approval_deadline_at=t.approval_deadline_at, approved_by=t.approved_by,
        decided_at=t.decided_at, result=t.result, is_partial=t.is_partial, error=t.error,
        created_at=t.created_at, updated_at=t.updated_at, finished_at=t.finished_at,
    )


def _publish(request: Request):
    async def publish(event) -> None:
        await request.app.state.hub.publish(event)

    return publish


@router.get("/ai/tasks", response_model=AITaskPage)
async def list_ai_tasks(
    status: str | None = None,
    type: str | None = None,
    incident_id: int | None = None,
    finding_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
    scope: TeamScope | None = Depends(require_permission("ai_tasks", "read")),
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    tasks, total = await repo.list_tasks(
        session, status=status, type_=type, incident_id=incident_id,
        finding_id=finding_id, offset=offset, limit=limit,
    )
    items = []
    for task in tasks:
        if scope is not None and task.incident_id is not None:
            from huntai.domains.incidents import repository as incident_repo

            incident = await incident_repo.get_incident(session, task.incident_id)
            if incident is not None and incident.team is not None and incident.team != scope.team:
                continue  # sre(T) 行级过滤：AI 任务随事件团队
        items.append(_task_response(task))
    return AITaskPage.build(items, total=total, offset=offset, limit=limit)


@router.get("/ai/tasks/{task_id}", response_model=AITaskResponse)
async def get_ai_task(
    task_id: int,
    scope: TeamScope | None = Depends(require_permission("ai_tasks", "read")),
    session: AsyncSession = Depends(get_session),
):
    task = await repo.get_task(session, task_id)
    if task is None:
        raise not_found("ai_tasks", task_id)
    return _task_response(task)


@router.post("/ai/tasks/{task_id}/approve", response_model=AITaskResponse)
async def approve_ai_task(
    request: Request, task_id: int,
    scope: TeamScope | None = Depends(require_permission("ai_tasks", "approve")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    task = await service.approve_task(
        session, task_id, actor_id=principal.user_id, publish=_publish(request)
    )
    return _task_response(task)


@router.post("/ai/tasks/{task_id}/cancel", response_model=AITaskResponse)
async def cancel_ai_task(
    request: Request, task_id: int, payload: AITaskCancelRequest | None = None,
    scope: TeamScope | None = Depends(require_permission("ai_tasks", "cancel")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    task = await service.cancel_task(
        session, task_id, actor_id=principal.user_id,
        reason=payload.reason if payload else None, publish=_publish(request),
    )
    return _task_response(task)


@router.get("/ai/tasks/{task_id}/call-logs", response_model=AICallLogPage)
async def list_ai_task_call_logs(
    task_id: int,
    offset: int = 0,
    limit: int = 50,
    scope: TeamScope | None = Depends(require_permission("ai_tasks", "call_logs")),
    session: AsyncSession = Depends(get_session),
):
    if await repo.get_task(session, task_id) is None:
        raise not_found("ai_tasks", task_id)
    offset, limit = clamp_page(offset, limit)
    logs, total = await repo.list_call_logs(session, task_id, offset=offset, limit=limit)
    items = [
        AICallLogResponse(
            id=log.id, task_id=log.task_id, model=log.model, tool_used=log.tool_used,
            prompt_digest=log.prompt_digest, tokens_in=log.tokens_in, tokens_out=log.tokens_out,
            latency_ms=log.latency_ms,
            result_code=log.result_code.value if hasattr(log.result_code, "value") else log.result_code,
            error=log.error, created_at=log.created_at,
        )
        for log in logs
    ]
    return AICallLogPage.build(items, total=total, offset=offset, limit=limit)
