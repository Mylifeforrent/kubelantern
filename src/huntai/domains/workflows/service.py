"""流程编排域（P3 薄层）：CRUD/版本/审批/运行记录；执行引擎语义随 P3 详设另立。"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import Field

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.db import utcnow
from huntai.core.errors import ProblemError, not_found
from huntai.core.pagination import paginate
from huntai.core.schemas import BaseSchema, Page, UtcDateTime
from huntai.domains.iam.service import record_audit
from huntai.domains.workflows.models import Workflow, WorkflowRun, WorkflowRunTrigger

logger = logging.getLogger("huntai.workflows")


class WorkflowResponse(BaseSchema):
    id: int
    name: str
    version: int
    yaml: str
    source: str
    approved_by: int | None = None
    enabled: bool
    is_current: bool
    created_by: int
    created_at: UtcDateTime
    updated_at: UtcDateTime


class WorkflowCreateRequest(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    yaml: str = Field(min_length=1)
    enabled: bool = True


class WorkflowVersionCreateRequest(BaseSchema):
    yaml: str = Field(min_length=1)


class WorkflowFromDescriptionRequest(BaseSchema):
    description: str = Field(min_length=1, max_length=4000)


class WorkflowRunResponse(BaseSchema):
    id: int
    workflow_id: int
    workflow_version: int
    yaml_snapshot: str
    trigger_type: str
    triggered_by: int | None = None
    alert_id: int | None = None
    incident_id: int | None = None
    status: str
    steps_log: list[Any]
    error: str | None = None
    started_at: UtcDateTime
    finished_at: UtcDateTime | None = None
    created_at: UtcDateTime


class WorkflowRunCreateRequest(BaseSchema):
    workflow_id: int
    trigger_type: str = "manual"
    alert_id: int | None = None
    incident_id: int | None = None


class WorkflowPage(Page[WorkflowResponse]):
    pass


def _validate_yaml(text: str) -> None:
    """YAML 解析校验（语法级；语义校验随 P3 详设）。标准库无 YAML，做基础结构检查。"""
    if "steps:" not in text:
        raise ProblemError(status=400, detail="Workflow YAML 必须包含 steps 字段（P3 语义级校验另立）")


async def list_workflows(
    session: AsyncSession, *, offset: int = 0, limit: int = 50, current_only: bool = True
) -> tuple[list[Workflow], int]:
    stmt = select(Workflow).order_by(desc(Workflow.id))
    if current_only:
        stmt = stmt.where(Workflow.is_current.is_(True))
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def get_workflow(session: AsyncSession, workflow_id: int) -> Workflow | None:
    return await session.get(Workflow, workflow_id)


async def create_workflow(
    session: AsyncSession, payload: WorkflowCreateRequest, *, actor_id: int, source: str = "manual",
    approved_by: int | None = None,
) -> Workflow:
    _validate_yaml(payload.yaml)
    if source == "ai_generated" and approved_by is None:
        # service + D-10 双层（BR-05）
        raise ProblemError(status=400, code="WORKFLOW_APPROVAL_REQUIRED",
                           detail="source=ai_generated 必须提供 approved_by（BR-05）")
    latest = await session.execute(
        select(func.max(Workflow.version)).where(Workflow.name == payload.name)
    )
    next_version = (latest.scalar_one() or 0) + 1
    for existing in (
        await session.execute(select(Workflow).where(Workflow.name == payload.name, Workflow.is_current.is_(True)))
    ).scalars():
        existing.is_current = False
    workflow = Workflow(
        name=payload.name, version=next_version, yaml=payload.yaml, source=source,
        approved_by=approved_by, enabled=payload.enabled, is_current=True, created_by=actor_id,
    )
    session.add(workflow)
    await session.flush()
    await record_audit(
        session, action="workflow.create", resource_type="workflows", resource_id=workflow.id,
        detail={"name": workflow.name, "version": workflow.version, "source": source},
        actor_id=actor_id,
    )
    return workflow


async def create_version(
    session: AsyncSession, workflow_id: int, yaml_text: str, *, actor_id: int
) -> Workflow:
    base = await get_workflow(session, workflow_id)
    if base is None:
        raise not_found("workflows", workflow_id)
    _validate_yaml(yaml_text)
    return await create_workflow(
        session, WorkflowCreateRequest(name=base.name, yaml=yaml_text, enabled=base.enabled),
        actor_id=actor_id, source=base.source, approved_by=base.approved_by,
    )


async def approve_workflow(
    session: AsyncSession, workflow_id: int, *, actor_id: int
) -> Workflow:
    """AI 生成 Workflow 的确认（BR-05）：补 approved_by。"""
    workflow = await get_workflow(session, workflow_id)
    if workflow is None:
        raise not_found("workflows", workflow_id)
    if workflow.source != "ai_generated":
        raise ProblemError(status=409, code="WORKFLOW_STATE_CONFLICT", detail="仅 ai_generated 来源需要确认")
    if workflow.approved_by is not None:
        raise ProblemError(status=409, code="WORKFLOW_STATE_CONFLICT", detail="该 Workflow 已确认")
    workflow.approved_by = actor_id
    await record_audit(
        session, action="workflow.approve", resource_type="workflows", resource_id=workflow.id,
        detail={}, actor_id=actor_id,
    )
    return workflow


async def create_run(
    session: AsyncSession, payload: WorkflowRunCreateRequest, *, actor_id: int
) -> WorkflowRun:
    workflow = await get_workflow(session, payload.workflow_id)
    if workflow is None:
        raise not_found("workflows", payload.workflow_id)
    if payload.trigger_type not in {"alert", "manual", "schedule"}:
        raise ProblemError(status=400, detail="trigger_type 必须是 alert/manual/schedule")
    if workflow.source == "ai_generated" and workflow.approved_by is None:
        raise ProblemError(status=409, code="WORKFLOW_APPROVAL_REQUIRED",
                           detail="ai_generated Workflow 未确认，不可执行（BR-05）")
    run = WorkflowRun(
        workflow_id=workflow.id, workflow_version=workflow.version,
        yaml_snapshot=workflow.yaml, trigger_type=payload.trigger_type,
        triggered_by=actor_id if payload.trigger_type == "manual" else None,
        alert_id=payload.alert_id, incident_id=payload.incident_id,
        steps_log=[],
    )
    session.add(run)
    await session.flush()
    await record_audit(
        session, action="workflow_run.create", resource_type="workflow_runs", resource_id=run.id,
        detail={"workflow": workflow.name, "version": workflow.version}, actor_id=actor_id,
    )
    # 执行引擎随 P3 详设另立；run 停留在 triggered（已入队语义）
    return run


async def get_run(session: AsyncSession, run_id: int) -> WorkflowRun | None:
    return await session.get(WorkflowRun, run_id)
