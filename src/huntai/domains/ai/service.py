"""AI 域 service：任务管理（创建/审批/取消/查询）；执行面在 gateway/（worker 内运行）。

- 预算默认 BR-03（40 次调用 / 100k 输出 token），管理员可调。
- 审批（BR-02/BR-05）：approve 限 sre 本团队；超时由 approval.scan_timeouts 置 cancelled。
- A1 失败重试 1 次为业务层重试（不依赖框架自动重试）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.config import Settings
from huntai.core.db import utcnow
from huntai.core.errors import not_found, state_conflict
from huntai.domains.ai import repository as repo
from huntai.domains.ai.models import (
    AICallLog,
    AIExplanation,
    AITask,
    AITaskStatus,
    AITaskType,
)
from huntai.domains.iam.service import record_audit


def default_budget(settings: Settings) -> dict[str, int]:
    return {
        "max_calls": settings.ai_budget_default_calls,
        "max_output_tokens": settings.ai_budget_default_tokens,
    }


async def create_task_for_finding(
    session: AsyncSession, finding, *, requested_by: int | None, settings: Settings, enqueue=None
) -> AITask:
    """A1：巡检 finding 一键 AI 解释（P1；worker 入口与 API 共用）。"""
    task = AITask(
        type=AITaskType.EXPLAIN,
        status=AITaskStatus.CREATED,
        context_refs={"finding_id": finding.id, "rule_code": finding.rule_code},
        finding_id=finding.id,
        budget=default_budget(settings),
        requested_by=requested_by
        if requested_by is not None
        else await _system_requester_id(session),
    )
    session.add(task)
    await session.flush()
    if enqueue is not None:
        await enqueue("ai.execute_task", task.id, _queue="q-ai")
    return task


async def create_investigation_task(
    session: AsyncSession, incident, *, requested_by: int, settings: Settings, enqueue=None
) -> AITask:
    """A2（P3 概要级）：事件自动调查任务。"""
    task = AITask(
        type=AITaskType.INVESTIGATE,
        status=AITaskStatus.CREATED,
        context_refs={"incident_id": incident.id},
        incident_id=incident.id,
        budget=default_budget(settings),
        requested_by=requested_by,
    )
    session.add(task)
    await session.flush()
    await record_audit(
        session, action="ai_task.create", resource_type="ai_tasks", resource_id=task.id,
        detail={"type": "investigate", "incident_id": incident.id}, actor_id=requested_by,
    )
    if enqueue is not None:
        await enqueue("ai.execute_task", task.id, _queue="q-ai")
    return task


async def create_workflow_gen_task(
    session: AsyncSession, description: str, *, requested_by: int, settings: Settings, enqueue=None
) -> AITask:
    """A3（P3 概要级）：自然语言生成 Workflow 草稿（确认后经 API 创建 workflows 行，BR-05）。"""
    task = AITask(
        type=AITaskType.WORKFLOW_GEN,
        status=AITaskStatus.CREATED,
        context_refs={"description": description},
        budget=default_budget(settings),
        requested_by=requested_by,
    )
    session.add(task)
    await session.flush()
    await record_audit(
        session, action="ai_task.create", resource_type="ai_tasks", resource_id=task.id,
        detail={"type": "workflow_gen"}, actor_id=requested_by,
    )
    if enqueue is not None:
        await enqueue("ai.execute_task", task.id, _queue="q-ai")
    return task


async def _system_requester_id(session: AsyncSession) -> int:
    """系统发起的 A1 任务需要一个 requested_by；取首个 admin 用户（seed 保证存在）。"""
    from sqlalchemy import select

    from huntai.domains.iam.models import Role, User, UserRoleGrant

    row = await session.execute(
        select(User.id)
        .join(UserRoleGrant, UserRoleGrant.user_id == User.id)
        .join(Role, Role.id == UserRoleGrant.role_id)
        .where(Role.code == "admin")
        .limit(1)
    )
    user_id = row.scalar_one_or_none()
    return int(user_id) if user_id is not None else 0


async def approve_task(session: AsyncSession, task_id: int, *, actor_id: int, publish=None) -> AITask:
    task = await repo.get_task(session, task_id)
    if task is None:
        raise not_found("ai_tasks", task_id)
    if task.status != AITaskStatus.PENDING_APPROVAL:
        raise state_conflict(
            "AI_TASK_STATE_CONFLICT", f"AI 任务 {task_id} 不在待审批状态（{task.status}）"
        )
    task.status = AITaskStatus.RUNNING
    task.approved_by = actor_id
    task.decided_at = utcnow()
    await record_audit(
        session, action="ai_task.approve", resource_type="ai_tasks", resource_id=task.id,
        detail={}, actor_id=actor_id,
    )
    if publish is not None:
        from huntai.realtime.hub import RealtimeEvent

        await publish(
            RealtimeEvent(topic="ai-tasks", name="ai_task.updated", resource="ai_task", resource_id=task.id)
        )
    return task


async def cancel_task(
    session: AsyncSession, task_id: int, *, actor_id: int, reason: str | None = None, publish=None
) -> AITask:
    task = await repo.get_task(session, task_id)
    if task is None:
        raise not_found("ai_tasks", task_id)
    if task.status in {AITaskStatus.COMPLETED, AITaskStatus.CANCELLED, AITaskStatus.FAILED}:
        raise state_conflict(
            "AI_TASK_STATE_CONFLICT", f"AI 任务 {task_id} 已终态（{task.status}）"
        )
    task.status = AITaskStatus.CANCELLED
    task.error = reason
    task.finished_at = utcnow()
    await record_audit(
        session, action="ai_task.cancel", resource_type="ai_tasks", resource_id=task.id,
        detail={"reason": reason or ""}, actor_id=actor_id,
    )
    if publish is not None:
        from huntai.realtime.hub import RealtimeEvent

        await publish(
            RealtimeEvent(topic="ai-tasks", name="ai_task.updated", resource="ai_task", resource_id=task.id)
        )
    return task


async def scan_approval_timeouts(session: AsyncSession, *, publish=None) -> list[AITask]:
    """审批超时（默认 30min [ASSUMPTION]）= 拒绝：置 cancelled 并通知发起人（BR-02）。"""
    expired = await repo.timed_out_pending_approvals(session, now=utcnow())
    for task in expired:
        task.status = AITaskStatus.CANCELLED
        task.error = "审批超时未决，按拒绝处理（BR-02）"
        task.finished_at = utcnow()
        await record_audit(
            session, action="ai_task.approval_timeout", resource_type="ai_tasks",
            resource_id=task.id, detail={}, actor_type="system",
        )
        if publish is not None:
            from huntai.realtime.hub import RealtimeEvent

            await publish(
                RealtimeEvent(topic="ai-tasks", name="ai_task.updated", resource="ai_task", resource_id=task.id)
            )
    return expired


def append_call_log(
    session: AsyncSession,
    *,
    task_id: int,
    model: str,
    prompt_digest: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    result_code: str,
    tool_used: str | None = None,
    error: str | None = None,
) -> AICallLog:
    log = AICallLog(
        task_id=task_id, model=model, tool_used=tool_used, prompt_digest=prompt_digest,
        tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=latency_ms,
        result_code=result_code, error=error,
    )
    session.add(log)
    return log


def upsert_explanation(
    session: AsyncSession,
    existing: AIExplanation | None,
    *,
    finding_id: int,
    task_id: int | None,
    sanitized_input_digest: str,
    output: dict[str, Any],
    model: str,
    tokens: int,
) -> AIExplanation:
    if existing is not None:
        existing.task_id = task_id
        existing.sanitized_input_digest = sanitized_input_digest
        existing.output = output
        existing.model = model
        existing.tokens = tokens
        return existing
    explanation = AIExplanation(
        finding_id=finding_id, task_id=task_id, sanitized_input_digest=sanitized_input_digest,
        output=output, model=model, tokens=tokens,
    )
    session.add(explanation)
    return explanation
