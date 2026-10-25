"""巡检诊断域 service：规则库/策略管理、L4 执行序（含 BR-09 分流）。

run_inspection 执行序（04-backend-design §3.3）：
① 建 run(running)；② 只读快照（cluster 不健康置 failed）；③ 纯函数判定；
④ 批量写 findings（业务键唯一）；⑤ BR-09 分流（warning/critical 转告警，info 仅看板）；
⑥ 可选 AI 解释（ai_explain_level 达标时入队 q-ai）；⑦ 汇总置 succeeded/failed。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.config import Settings
from huntai.core.cron import parse_cron
from huntai.core.db import utcnow
from huntai.core.errors import ProblemError, not_found, state_conflict
from huntai.domains.clusters import repository as clusters_repo
from huntai.domains.iam.service import record_audit
from huntai.domains.inspections import repository as repo
from huntai.domains.inspections.analyzers import BUILTIN_ANALYZERS
from huntai.domains.inspections.models import (
    Finding,
    FindingSeverity,
    FindingStatus,
    InspectionPolicy,
    InspectionPolicyRule,
    InspectionRule,
    InspectionRun,
    InspectionRunTrigger,
)
from huntai.domains.inspections.schemas import (
    InspectionPolicyCreateRequest,
    InspectionPolicyUpdateRequest,
    InspectionRuleCreateRequest,
    InspectionRuleUpdateRequest,
)

logger = logging.getLogger("huntai.inspections")


# ---------- 规则库 ----------


async def create_rule(
    session: AsyncSession, payload: InspectionRuleCreateRequest, *, actor_id: int
) -> InspectionRule:
    if payload.severity_default not in {"info", "warning", "critical"}:
        raise ProblemError(status=400, detail="severity_default 必须是 info/warning/critical")
    if await repo.code_exists(session, payload.code):
        raise ProblemError(status=409, code="INSPECTION_RULE_CONFLICT", detail=f"规则代码已存在：{payload.code}")
    rule = InspectionRule(
        code=payload.code, name=payload.name, category=payload.category,
        severity_default=payload.severity_default, k8s_version_fit=payload.k8s_version_fit,
        description=payload.description, enabled=payload.enabled,
    )
    session.add(rule)
    await session.flush()
    await record_audit(
        session, action="inspection_rule.create", resource_type="inspection_rules",
        resource_id=rule.id, detail={"code": rule.code}, actor_id=actor_id,
    )
    return rule


async def update_rule(
    session: AsyncSession, rule_id: int, payload: InspectionRuleUpdateRequest, *, actor_id: int
) -> InspectionRule:
    rule = await repo.get_rule(session, rule_id)
    if rule is None:
        raise not_found("inspection_rules", rule_id)
    changes: dict[str, Any] = {}
    for field_name in ("name", "category", "severity_default", "k8s_version_fit", "description", "enabled"):
        value = getattr(payload, field_name)
        if value is not None:
            setattr(rule, field_name, value)
            changes[field_name] = value
    await record_audit(
        session, action="inspection_rule.update", resource_type="inspection_rules",
        resource_id=rule.id, detail=changes, actor_id=actor_id,
    )
    return rule


async def delete_rule(session: AsyncSession, rule_id: int, *, actor_id: int) -> None:
    rule = await repo.get_rule(session, rule_id)
    if rule is None:
        raise not_found("inspection_rules", rule_id)
    rule.enabled = False  # 规则被策略引用，停用等价移除（无 deleted_at 列，契约 204）
    await record_audit(
        session, action="inspection_rule.delete", resource_type="inspection_rules",
        resource_id=rule.id, detail={"code": rule.code}, actor_id=actor_id,
    )


# ---------- 策略 ----------


def _validate_policy_schedule(schedule: str) -> None:
    try:
        parse_cron(schedule)
    except ValueError as exc:
        raise ProblemError(status=400, detail=f"巡检策略 schedule 非法：{exc}") from exc


async def create_policy(
    session: AsyncSession, payload: InspectionPolicyCreateRequest, *, actor_id: int
) -> InspectionPolicy:
    if payload.ai_explain_level not in {"off", "info", "warning", "critical"}:
        raise ProblemError(status=400, detail="ai_explain_level 必须是 off/info/warning/critical")
    _validate_policy_schedule(payload.schedule)
    if await clusters_repo.get_cluster(session, payload.cluster_id) is None:
        raise ProblemError(status=400, detail=f"集群不存在：{payload.cluster_id}")
    for rule_id in payload.rule_ids:
        if await repo.get_rule(session, rule_id) is None:
            raise ProblemError(status=400, detail=f"规则不存在：{rule_id}")
    policy = InspectionPolicy(
        cluster_id=payload.cluster_id, name=payload.name, schedule=payload.schedule,
        ai_explain_level=payload.ai_explain_level, enabled=payload.enabled,
    )
    session.add(policy)
    await session.flush()
    await repo.replace_policy_rules(session, policy.id, payload.rule_ids)
    await record_audit(
        session, action="inspection_policy.create", resource_type="inspection_policies",
        resource_id=policy.id, detail={"name": policy.name}, actor_id=actor_id,
    )
    return policy


async def update_policy(
    session: AsyncSession, policy_id: int, payload: InspectionPolicyUpdateRequest, *, actor_id: int
) -> InspectionPolicy:
    policy = await repo.get_policy(session, policy_id)
    if policy is None:
        raise not_found("inspection_policies", policy_id)
    changes: dict[str, Any] = {}
    if payload.schedule is not None:
        _validate_policy_schedule(payload.schedule)
    for field_name in ("name", "schedule", "ai_explain_level", "enabled"):
        value = getattr(payload, field_name)
        if value is not None:
            setattr(policy, field_name, value)
            changes[field_name] = value
    if payload.rule_ids is not None:
        for rule_id in payload.rule_ids:
            if await repo.get_rule(session, rule_id) is None:
                raise ProblemError(status=400, detail=f"规则不存在：{rule_id}")
        await repo.replace_policy_rules(session, policy.id, payload.rule_ids)
        changes["rule_ids"] = payload.rule_ids
    await record_audit(
        session, action="inspection_policy.update", resource_type="inspection_policies",
        resource_id=policy.id, detail=changes, actor_id=actor_id,
    )
    return policy


async def delete_policy(session: AsyncSession, policy_id: int, *, actor_id: int) -> None:
    policy = await repo.get_policy(session, policy_id)
    if policy is None:
        raise not_found("inspection_policies", policy_id)
    policy.enabled = False
    await record_audit(
        session, action="inspection_policy.delete", resource_type="inspection_policies",
        resource_id=policy.id, detail={"name": policy.name}, actor_id=actor_id,
    )


async def trigger_run(
    session: AsyncSession, policy_id: int, *, actor_id: int, enqueue
) -> InspectionRun:
    policy = await repo.get_policy(session, policy_id)
    if policy is None:
        raise not_found("inspection_policies", policy_id)
    run = InspectionRun(
        policy_id=policy.id, cluster_id=policy.cluster_id,
        trigger=InspectionRunTrigger.MANUAL, started_at=utcnow(),
    )
    session.add(run)
    await session.flush()
    await record_audit(
        session, action="inspection.run_trigger", resource_type="inspection_runs",
        resource_id=run.id, detail={"policy": policy.name, "trigger": "manual"}, actor_id=actor_id,
    )
    await enqueue("inspection.run", run.id)
    return run


# ---------- 执行序（worker 调用） ----------


async def run_inspection(
    session: AsyncSession, run_id: int, *, settings: Settings, publish=None, enqueue=None
) -> InspectionRun:
    run = await repo.get_run(session, run_id)
    if run is None:
        raise not_found("inspection_runs", run_id)
    cluster = await clusters_repo.get_cluster(session, run.cluster_id)
    if cluster is None or (cluster.status.value if hasattr(cluster.status, "value") else cluster.status) in {"disconnected", "unknown"}:
        run.status = "failed"
        run.error = "集群不健康或不存在（探活失败则由自监控直发告警）"
        run.finished_at = utcnow()
        await session.flush()
        return run

    # ② 只读快照（BR-02：仅加载 readonly 凭证）
    from huntai.domains.clusters import service as clusters_service

    try:
        snapshot = await clusters_service.get_snapshot(session, run.cluster_id)
    except Exception as exc:  # noqa: BLE001 - 快照失败即 run failed
        run.status = "failed"
        run.error = f"快照拉取失败：{exc}"
        run.finished_at = utcnow()
        await session.flush()
        return run

    policy = await repo.get_policy(session, run.policy_id)
    rule_ids = await repo.policy_rule_ids(session, run.policy_id)
    rules = [rule for rule in await repo.enabled_rules(session) if not rule_ids or rule.id in rule_ids]

    # ③ 纯函数判定 + ④ 批量写 findings（业务键唯一，复现沿用 open finding）
    drafts = []
    for rule in rules:
        analyzer = BUILTIN_ANALYZERS.get(rule.code)
        if analyzer is None:
            continue
        for draft in analyzer.analyze(snapshot):
            draft.severity = draft.severity or (
                rule.severity_default.value if hasattr(rule.severity_default, "value") else rule.severity_default
            )
            drafts.append((rule, draft))

    findings_count = 0
    converted = 0
    for rule, draft in drafts:
        existing = await repo.open_finding_for_ref(
            session, cluster_id=run.cluster_id, rule_code=draft.rule_code,
            resource_ref=draft.resource_ref,
        )
        if existing is not None:
            continue
        finding = Finding(
            run_id=run.id, cluster_id=run.cluster_id, rule_code=draft.rule_code,
            resource_ref=draft.resource_ref, severity=draft.severity, raw_error=draft.raw_error,
        )
        session.add(finding)
        await session.flush()
        findings_count += 1

        # ⑤ BR-09 分流：warning/critical 转告警；info 仅看板
        if draft.severity in {"warning", "critical"}:
            alert_id, _merged = await _convert_finding_to_alert(
                session, finding=finding, cluster_id=run.cluster_id, enqueue=enqueue
            )
            if alert_id is not None:
                finding.status = FindingStatus.CONVERTED_TO_ALERT
                finding.converted_alert_id = alert_id
                converted += 1
        # ⑥ 可选 AI 解释（P1；ai_explain_level 达标）
        if _explain_due(policy, draft.severity) and enqueue is not None:
            from huntai.domains.ai import service as ai_service

            await ai_service.create_task_for_finding(
                session, finding, requested_by=None, settings=settings, enqueue=enqueue,
            )

    # ⑦ 汇总
    run.status = "succeeded"
    run.findings_count = findings_count
    run.result = {"total": findings_count, "converted_to_alert": converted}
    run.finished_at = utcnow()
    await session.flush()
    if publish is not None:
        from huntai.realtime.hub import RealtimeEvent

        await publish(
            RealtimeEvent(topic="inspections", name="inspection_run.completed",
                          resource="inspection_run", resource_id=run.id)
        )
    return run


def _explain_due(policy: InspectionPolicy | None, severity: str) -> bool:
    if policy is None:
        return False
    level = policy.ai_explain_level.value if hasattr(policy.ai_explain_level, "value") else policy.ai_explain_level
    order = {"off": 0, "info": 1, "warning": 2, "critical": 3}
    return order.get(level, 0) > 0 and order.get(severity, 0) >= order.get(level, 0)


async def _convert_finding_to_alert(
    session: AsyncSession, *, finding: Finding, cluster_id: int, enqueue
) -> tuple[int | None, bool]:
    """BR-09：经 AlertService.ingest 进 L1 upsert（fingerprint 由 rule_code+resource+cluster 派生 [ASSUMPTION]）。"""
    from huntai.domains.alerts import service as alerts_service
    from huntai.domains.alerts import repository as _alerts_repo
    from huntai.domains.clusters import repository as _clusters_repo

    cluster = await _clusters_repo.get_cluster(session, cluster_id)
    provider = await _alerts_repo.get_provider_by_name(session, "huntai-inspection")
    if provider is None:
        logger.warning("BR-09 转告警跳过：缺少内置 Provider huntai-inspection")
        return None, False
    ref = finding.resource_ref
    payload = {
        "title": f"[巡检] {finding.rule_code} {ref.get('namespace', '')}/{ref.get('name', '')}",
        "severity": finding.severity.value if hasattr(finding.severity, "value") else finding.severity,
        "labels": {
            "alertname": finding.rule_code,
            "source": "huntai-inspection",
            "cluster": cluster.name if cluster else str(cluster_id),
            "kind": str(ref.get("kind", "")),
            "namespace": str(ref.get("namespace") or ""),
            "name": str(ref.get("name", "")),
        },
        "status": "firing",
    }
    alert_id, inserted = await alerts_service.ingest(
        session, provider=provider, payload=payload, enqueue=enqueue
    )
    await record_audit(
        session, action="finding.convert_to_alert", resource_type="findings",
        resource_id=finding.id, detail={"alert_id": alert_id}, actor_type="system",
    )
    return alert_id, inserted


# ---------- finding 工作台 ----------


async def ack_finding(
    session: AsyncSession, finding_id: int, *, actor_id: int, publish=None
) -> Finding:
    finding = await repo.get_finding(session, finding_id)
    if finding is None:
        raise not_found("findings", finding_id)
    if finding.status == FindingStatus.RESOLVED:
        raise state_conflict("FINDING_STATE_CONFLICT", f"finding {finding_id} 已 resolved")
    finding.status = FindingStatus.ACKNOWLEDGED
    finding.assignee_id = actor_id
    await record_audit(
        session, action="finding.ack", resource_type="findings", resource_id=finding.id,
        detail={"assignee_id": actor_id}, actor_id=actor_id,
    )
    if publish is not None:
        from huntai.realtime.hub import RealtimeEvent

        await publish(
            RealtimeEvent(topic="inspections", name="finding.updated",
                          resource="finding", resource_id=finding.id)
        )
    return finding


async def ignore_finding(
    session: AsyncSession, finding_id: int, reason: str, *, actor_id: int
) -> Finding:
    finding = await repo.get_finding(session, finding_id)
    if finding is None:
        raise not_found("findings", finding_id)
    if finding.status not in {FindingStatus.OPEN, FindingStatus.ACKNOWLEDGED, FindingStatus.IN_PROGRESS}:
        raise state_conflict("FINDING_STATE_CONFLICT", f"finding {finding_id} 不可忽略（{finding.status}）")
    finding.status = FindingStatus.IGNORED
    finding.ignored_reason = reason  # D-10：ignored 必填原因
    await record_audit(
        session, action="finding.ignore", resource_type="findings", resource_id=finding.id,
        detail={"ignored_reason": reason}, actor_id=actor_id,
    )
    return finding


async def reopen_finding(session: AsyncSession, finding_id: int, *, actor_id: int) -> Finding:
    finding = await repo.get_finding(session, finding_id)
    if finding is None:
        raise not_found("findings", finding_id)
    if finding.status not in {FindingStatus.IGNORED, FindingStatus.RESOLVED}:
        raise state_conflict("FINDING_STATE_CONFLICT", f"finding {finding_id} 不可重开（{finding.status}）")
    finding.status = FindingStatus.OPEN
    finding.ignored_reason = None
    await record_audit(
        session, action="finding.reopen", resource_type="findings", resource_id=finding.id,
        detail={}, actor_id=actor_id,
    )
    return finding


# ---------- 调度（cron tick，worker 调用） ----------


async def schedule_tick(session: AsyncSession, *, enqueue, now=None) -> list[int]:
    """cron 到期判定 [ASSUMPTION]：以该策略最近一次 trigger='schedule' run 判断是否到期。"""
    from datetime import UTC, datetime

    now = now or datetime.now(UTC)
    triggered: list[int] = []
    for policy in await repo.enabled_policies(session):
        try:
            cron = parse_cron(policy.schedule)
        except ValueError:
            continue
        last_run = await repo.last_scheduled_run(session, policy.id)
        since = last_run.started_at if last_run is not None else None
        if since is not None and since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        due = cron.matches_between(since, now) if since is not None else True
        if not due:
            continue
        run = InspectionRun(
            policy_id=policy.id, cluster_id=policy.cluster_id,
            trigger=InspectionRunTrigger.SCHEDULE, started_at=now,
        )
        session.add(run)
        await session.flush()
        await enqueue("inspection.run", run.id)
        triggered.append(run.id)
    return triggered
