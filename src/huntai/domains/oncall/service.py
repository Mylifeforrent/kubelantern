"""值班域 service：排班 CRUD、当前值班解析（纯函数）、升级策略 CRUD。

排班结构以 JSONB 承载（[ASSUMPTION] 结构随排班算法详定）：
  rotation_rules: {"members": ["alice", "bob"], "interval_days": 7, "order": "asc"}
  calendar: {"2026-10-20": "alice", "2026-10-27": "bob"}
  overrides: [{"date": "2026-10-21", "user": "carol", "reason": "OOO 顶班"}]
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.db import utcnow
from huntai.core.errors import ProblemError, not_found
from huntai.domains.iam.service import record_audit
from huntai.domains.oncall import repository as repo
from huntai.domains.oncall.models import EscalationPolicy, OnCallSchedule
from huntai.domains.oncall.schemas import (
    EscalationPolicyCreateRequest,
    EscalationPolicyUpdateRequest,
    OnCallScheduleCreateRequest,
    OnCallScheduleUpdateRequest,
)


# ---------- 排班 ----------


async def create_schedule(
    session: AsyncSession, payload: OnCallScheduleCreateRequest, *, actor_id: int
) -> OnCallSchedule:
    if await repo.schedule_name_exists(session, payload.name):
        raise ProblemError(status=409, code="SCHEDULE_CONFLICT", detail=f"排班表已存在：{payload.name}")
    schedule = OnCallSchedule(
        name=payload.name, team=payload.team, rotation_rules=payload.rotation_rules,
        calendar=payload.calendar, overrides=payload.overrides, enabled=payload.enabled,
    )
    session.add(schedule)
    await session.flush()
    await record_audit(
        session, action="oncall_schedule.create", resource_type="oncall_schedules",
        resource_id=schedule.id, detail={"name": schedule.name, "team": schedule.team},
        actor_id=actor_id,
    )
    return schedule


async def update_schedule(
    session: AsyncSession, schedule_id: int, payload: OnCallScheduleUpdateRequest, *, actor_id: int
) -> OnCallSchedule:
    schedule = await repo.get_schedule(session, schedule_id)
    if schedule is None:
        raise not_found("oncall_schedules", schedule_id)
    changes = {}
    for field in ("name", "team", "rotation_rules", "calendar", "overrides", "enabled"):
        value = getattr(payload, field)
        if value is not None:
            setattr(schedule, field, value)
            changes[field] = value if field != "overrides" else len(value)
    await record_audit(
        session, action="oncall_schedule.update", resource_type="oncall_schedules",
        resource_id=schedule.id, detail=changes, actor_id=actor_id,
    )
    return schedule


async def delete_schedule(session: AsyncSession, schedule_id: int, *, actor_id: int) -> None:
    schedule = await repo.get_schedule(session, schedule_id)
    if schedule is None:
        raise not_found("oncall_schedules", schedule_id)
    schedule.enabled = False  # 排班表停用等价移除（无 deleted_at 列，契约 204）
    await record_audit(
        session, action="oncall_schedule.delete", resource_type="oncall_schedules",
        resource_id=schedule.id, detail={"name": schedule.name}, actor_id=actor_id,
    )


def resolve_oncall(rotation_rules: dict, calendar: dict, overrides: list, at: date) -> list[str]:
    """纯函数：解析指定日期的值班人（override > calendar > rotation 轮换）。"""
    for override in overrides or []:
        if str(override.get("date", "")) == at.isoformat():
            return [str(override["user"])]
    calendar_key = at.isoformat()
    if isinstance(calendar, dict):
        for offset in range(8):  # 日历允许按周配置，回看 7 天内的最近班次
            candidate = date.fromordinal(at.toordinal() - offset)
            person = calendar.get(candidate.isoformat())
            if person:
                return [str(person)]
    members = list((rotation_rules or {}).get("members", []))
    if not members:
        return []
    interval_days = int((rotation_rules or {}).get("interval_days", 7) or 7)
    week_index = at.toordinal() // max(1, interval_days)
    return [str(members[week_index % len(members)])]


async def current_oncall(session: AsyncSession, team: str) -> list[str]:
    schedules = await repo.schedules_for_team(session, team, enabled_only=True)
    if not schedules:
        return []
    schedule = schedules[0]
    return resolve_oncall(
        schedule.rotation_rules, schedule.calendar, schedule.overrides, utcnow().date()
    )


# ---------- 升级策略 ----------


def _validate_levels(levels: list[dict]) -> None:
    if not levels:
        raise ProblemError(status=400, detail="升级策略至少一级（levels 非空）")
    seen: set[int] = set()
    for level in levels:
        level_no = level.get("level")
        if not isinstance(level_no, int) or level_no < 1:
            raise ProblemError(status=400, detail=f"升级层级非法：{level}")
        if level_no in seen:
            raise ProblemError(status=400, detail=f"升级层级重复：{level_no}")
        seen.add(level_no)
        if not level.get("target") or not level.get("channel"):
            raise ProblemError(status=400, detail=f"升级层级缺少 target/channel：{level}")
        if not isinstance(level.get("timeout_min"), int) or level["timeout_min"] < 1:
            raise ProblemError(status=400, detail=f"升级层级 timeout_min 非法：{level}")
    if seen != set(range(1, len(levels) + 1)):
        raise ProblemError(status=400, detail="升级层级必须从 1 连续递增")


async def create_escalation_policy(
    session: AsyncSession, payload: EscalationPolicyCreateRequest, *, actor_id: int
) -> EscalationPolicy:
    if await repo.policy_name_exists(session, payload.name):
        raise ProblemError(status=409, code="ESCALATION_CONFLICT", detail=f"升级策略已存在：{payload.name}")
    if await repo.get_schedule(session, payload.schedule_id) is None:
        raise ProblemError(status=400, detail=f"排班表不存在：{payload.schedule_id}")
    _validate_levels(payload.levels)
    policy = EscalationPolicy(
        name=payload.name, schedule_id=payload.schedule_id, levels=sorted(
            payload.levels, key=lambda l: l["level"]
        ),
        channel_fallbacks=payload.channel_fallbacks, enabled=payload.enabled,
    )
    session.add(policy)
    await session.flush()
    await record_audit(
        session, action="escalation_policy.create", resource_type="escalation_policies",
        resource_id=policy.id, detail={"name": policy.name}, actor_id=actor_id,
    )
    return policy


async def update_escalation_policy(
    session: AsyncSession, policy_id: int, payload: EscalationPolicyUpdateRequest, *, actor_id: int
) -> EscalationPolicy:
    policy = await repo.get_policy(session, policy_id)
    if policy is None:
        raise not_found("escalation_policies", policy_id)
    changes = {}
    if payload.levels is not None:
        _validate_levels(payload.levels)
        policy.levels = sorted(payload.levels, key=lambda l: l["level"])
        changes["levels"] = len(payload.levels)
    for field in ("name", "schedule_id", "channel_fallbacks", "enabled"):
        value = getattr(payload, field)
        if value is not None:
            setattr(policy, field, value)
            changes[field] = value
    await record_audit(
        session, action="escalation_policy.update", resource_type="escalation_policies",
        resource_id=policy.id, detail=changes, actor_id=actor_id,
    )
    return policy


async def delete_escalation_policy(session: AsyncSession, policy_id: int, *, actor_id: int) -> None:
    policy = await repo.get_policy(session, policy_id)
    if policy is None:
        raise not_found("escalation_policies", policy_id)
    policy.enabled = False
    await record_audit(
        session, action="escalation_policy.delete", resource_type="escalation_policies",
        resource_id=policy.id, detail={"name": policy.name}, actor_id=actor_id,
    )
