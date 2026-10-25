"""告警管理域 service：webhook 接入、L1 管道四步、工作台操作、规则管理。

- 状态机集中在此（8 态值域禁改）；非法迁移抛 409（ALERT_STATE_CONFLICT）。
- 审计与业务变更同事务；系统关键决策（抑制等）写 audit_logs(actor_type=system)。
- SSE 发布与任务入队经回调注入（publish/enqueue），域层不依赖 app.state。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.db import utcnow
from huntai.core.errors import ProblemError, not_found, state_conflict
from huntai.domains.alerts import repository as repo
from huntai.domains.alerts.models import (
    Alert,
    AlertStatus,
    CorrelationRule,
    EnrichmentRule,
    MaintenanceWindow,
    Provider,
)
from huntai.domains.alerts.schemas import (
    CorrelationRuleCreateRequest,
    CorrelationRuleUpdateRequest,
    EnrichmentRuleCreateRequest,
    EnrichmentRuleUpdateRequest,
    MaintenanceWindowCreateRequest,
)
from huntai.domains.iam.service import record_audit
from huntai.pipeline import correlate as correlate_lib
from huntai.pipeline import normalizer
from huntai.pipeline.enrich import apply_enrichments, match_rule

logger = logging.getLogger("huntai.alerts")

PublishFn = Callable[..., Awaitable[None]]
EnqueueFn = Callable[..., Awaitable[str | None]]

AUTO_MODE_MIN_AGE_DAYS = 30  # BR-04 auto 准入门槛（运行 ≥30 天；细则 [TBD-BIZ]）


# ---------- webhook 接入（同步段：先落盘再入队，ADR-0003） ----------


async def ingest(
    session: AsyncSession,
    *,
    provider: Provider,
    payload: dict,
    enqueue: EnqueueFn | None = None,
    publish: PublishFn | None = None,
) -> tuple[int, bool]:
    normalized = normalizer.normalize(payload, fingerprint_fields=provider.fingerprint_fields or [])
    now = utcnow()

    if normalized.is_resolve:
        active = await repo.get_active_by_fingerprint(session, normalized.fingerprint)
        if active is not None:
            active.status = AlertStatus.RESOLVED
            active.resolved_at = now
            await record_audit(
                session, action="alert.auto_resolve", resource_type="alerts", resource_id=active.id,
                detail={"fingerprint": normalized.fingerprint}, actor_type="system",
            )
            if publish:
                await _publish_status(publish, active)
            return active.id, True
        resolved_row = Alert(
            fingerprint=normalized.fingerprint,
            provider_id=provider.id,
            title=normalized.title,
            severity=normalized.severity,
            status=AlertStatus.RESOLVED,
            labels=normalized.labels,
            raw_payload=normalized.raw,
            first_occurred_at=normalized.occurred_at,
            last_occurred_at=normalized.occurred_at,
            resolved_at=now,
        )
        session.add(resolved_row)
        await session.flush()
        return resolved_row.id, False

    alert_id, inserted = await repo.upsert_alert(
        session,
        fingerprint=normalized.fingerprint,
        provider_id=provider.id,
        title=normalized.title,
        severity=normalized.severity,
        labels=normalized.labels,
        raw_payload=normalized.raw,
        occurred_at=normalized.occurred_at,
    )
    if inserted and enqueue is not None:
        # 任务载荷只传 id（04-backend-design §1.7）
        await enqueue("alert.process_pipeline", alert_id)
    if inserted and publish is not None:
        await _publish_status(publish, await repo.get_alert(session, alert_id), to_="received")
    # merged=true 表示命中活跃指纹合并计数（不产生新行）
    return alert_id, not inserted


# ---------- L1 管道异步段（worker 执行；四步顺序不可调换） ----------


async def process_pipeline(
    session: AsyncSession,
    alert_id: int,
    *,
    publish: PublishFn | None = None,
    enqueue: EnqueueFn | None = None,
) -> None:
    from huntai.realtime.hub import RealtimeEvent

    # 步骤 1：幂等门闩 received/deduplicated → enriched（rowcount=0 即已被处理）
    if not await repo.gate_to_enriched(session, alert_id):
        return
    alert = await repo.get_alert(session, alert_id)
    if alert is None:
        return

    # 步骤 2：富化（纯函数匹配；结果与原始 labels 分离）
    rules = await repo.active_enrichment_rules(session)
    enrichments = apply_enrichments(
        [(r.matchers, r.mappings, r.priority) for r in rules], alert.labels
    )
    if enrichments:
        alert.enrichments = enrichments
        await session.flush()
    if publish:
        await publish(RealtimeEvent(topic="alerts", name="alert.updated", resource="alert", resource_id=alert_id))

    # 步骤 3：关联（BR-04；无规则命中 → standalone）
    status = await _correlate_step(session, alert, publish=publish)

    # 步骤 4：窗口检查 + 通知触发（BR-07；suppressed 优先于通知）
    if status == "standalone":
        window = await _matching_window(session, alert)
        if window is not None:
            alert.status = AlertStatus.SUPPRESSED
            alert.suppressed_by_window_id = window.id
            await session.flush()
            await record_audit(
                session, action="alert.suppress", resource_type="alerts", resource_id=alert.id,
                detail={"maintenance_window_id": window.id}, actor_type="system",
            )
            if publish:
                await _publish_status(publish, alert, to_="suppressed")
            return
        alert.status = AlertStatus.NOTIFIED
        await session.flush()
        if publish:
            await _publish_status(publish, alert, to_="notified")
        if enqueue is not None:
            await enqueue("notify.dispatch", alert_id=alert.id, _queue="q-notification")


async def _correlate_step(session: AsyncSession, alert: Alert, *, publish: PublishFn | None) -> str:
    rules = await repo.enabled_correlation_rules(session)
    attrs = {**alert.labels, **(alert.enrichments or {})}
    from huntai.realtime.hub import RealtimeEvent

    for rule in rules:
        if not correlate_lib.conditions_match(rule.conditions, attrs):
            continue
        window_start = alert.last_occurred_at - timedelta(seconds=rule.time_window_seconds)
        others = await repo.active_alerts_matching(session, since=window_start, exclude_id=alert.id)
        members = [alert]
        for other in others:
            other_attrs = {**other.labels, **(other.enrichments or {})}
            if (
                correlate_lib.conditions_match(rule.conditions, other_attrs)
                and correlate_lib.group_key(rule.conditions, attrs)
                == correlate_lib.group_key(rule.conditions, other_attrs)
            ):
                members.append(other)
        if len(members) < 2:
            continue
        member_ids = sorted({m.id for m in members})
        if rule.mode == "auto":
            from huntai.domains.incidents import service as incident_service

            await incident_service.merge_into_auto_incident(session, rule=rule, member_alerts=members)
        else:
            from huntai.domains.incidents import service as incident_service

            await incident_service.upsert_candidate(
                session, rule=rule, member_alert_ids=member_ids
            )
        for member in members:
            if member.status not in (AlertStatus.RESOLVED,):
                member.status = AlertStatus.CORRELATED
        await session.flush()
        if publish:
            await publish(
                RealtimeEvent(
                    topic="candidates", name="candidate.created",
                    resource="incident_candidate", resource_id=-1,
                    team=attrs.get("team"),
                )
            )
        return "correlated"
    alert.status = AlertStatus.STANDALONE
    await session.flush()
    return "standalone"


async def _matching_window(session: AsyncSession, alert: Alert) -> MaintenanceWindow | None:
    windows = await repo.active_windows(session, now=utcnow())
    attrs = {**alert.labels, **(alert.enrichments or {})}
    for window in windows:
        scope = window.scope
        matchers = scope.get("matchers") if isinstance(scope, dict) else scope
        if match_rule(matchers, {k: str(v) for k, v in attrs.items()}):
            return window
    return None


async def _publish_status(publish: PublishFn, alert: Alert | None, *, to_: str | None = None) -> None:
    from huntai.realtime.hub import RealtimeEvent

    if alert is None:
        return
    team = (alert.enrichments or {}).get("team")
    await publish(
        RealtimeEvent(
            topic="alerts",
            name="alert.updated",
            resource="alert",
            resource_id=alert.id,
            team=str(team) if team else None,
        )
    )


# ---------- 工作台操作 ----------


async def acknowledge(
    session: AsyncSession, alert_id: int, *, actor_id: int, publish: PublishFn | None = None
) -> Alert:
    alert = await repo.get_alert(session, alert_id)
    if alert is None:
        raise not_found("alerts", alert_id)
    if alert.status == AlertStatus.RESOLVED:
        raise state_conflict("ALERT_STATE_CONFLICT", f"alert {alert_id} 已 resolved，不可认领")
    alert.assignee_id = actor_id
    alert.acknowledged_at = utcnow()
    await record_audit(
        session, action="alert.acknowledge", resource_type="alerts", resource_id=alert.id,
        detail={"assignee_id": actor_id}, actor_id=actor_id,
    )
    if publish:
        await _publish_status(publish, alert)
    return alert


async def close(
    session: AsyncSession, alert_id: int, *, actor_id: int, publish: PublishFn | None = None
) -> Alert:
    alert = await repo.get_alert(session, alert_id)
    if alert is None:
        raise not_found("alerts", alert_id)
    if alert.status == AlertStatus.RESOLVED:
        raise state_conflict("ALERT_STATE_CONFLICT", f"alert {alert_id} 已 resolved")
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = utcnow()
    await record_audit(
        session, action="alert.close", resource_type="alerts", resource_id=alert.id,
        detail={"by": actor_id}, actor_id=actor_id,
    )
    if publish:
        await _publish_status(publish, alert)
    return alert


async def suppress_suggestion(
    session: AsyncSession, alert_id: int, *, actor_id: int, reason: str | None
) -> dict[str, Any]:
    """误报抑制建议（契约草案待补端点；写入降噪规则反馈池=audit）。"""
    alert = await repo.get_alert(session, alert_id)
    if alert is None:
        raise not_found("alerts", alert_id)
    await record_audit(
        session,
        action="alert.suppress_suggestion",
        resource_type="alerts",
        resource_id=alert.id,
        detail={"fingerprint": alert.fingerprint, "reason": reason or ""},
        actor_id=actor_id,
    )
    return {"accepted": True}


async def convert_to_incident(
    session: AsyncSession,
    alert_id: int,
    *,
    actor_id: int,
    title: str | None = None,
    severity: str | None = None,
    team: str | None = None,
    extra_alert_ids: list[int] | None = None,
) -> Any:
    from huntai.domains.incidents import service as incident_service
    from huntai.domains.incidents.schemas import IncidentCreateRequest

    alert = await repo.get_alert(session, alert_id)
    if alert is None:
        raise not_found("alerts", alert_id)
    alert_ids = sorted({alert_id, *(extra_alert_ids or [])})
    alerts = await repo.alerts_by_ids(session, alert_ids)
    deduced_title = title or alert.title or alert.labels.get("alertname") or f"告警 {alert_id} 转事件"
    deduced_severity = severity or ("P2" if alert.severity == "critical" else "P3")
    deduced_team = team or (alert.enrichments or {}).get("team")
    payload = IncidentCreateRequest(
        title=str(deduced_title),
        severity=deduced_severity,
        team=str(deduced_team) if deduced_team else None,
        related_alert_ids=alert_ids,
    )
    incident = await incident_service.create_manual_incident(
        session, payload, actor_id=actor_id
    )
    for member in alerts:
        if member.status != AlertStatus.RESOLVED:
            member.status = AlertStatus.CORRELATED
    return incident


async def list_alerts(session: AsyncSession, **filters) -> tuple[list[Alert], int]:
    return await repo.list_alerts(session, **filters)


async def get_alert(session: AsyncSession, alert_id: int) -> Alert:
    alert = await repo.get_alert(session, alert_id)
    if alert is None:
        raise not_found("alerts", alert_id)
    return alert


# ---------- 规则管理（富化 / 关联 / 维护窗口） ----------


async def create_enrichment_rule(
    session: AsyncSession, payload: EnrichmentRuleCreateRequest, *, actor_id: int
) -> EnrichmentRule:
    rule = EnrichmentRule(
        name=payload.name, matchers=payload.matchers, mappings=payload.mappings,
        priority=payload.priority, enabled=payload.enabled,
    )
    session.add(rule)
    await session.flush()
    await record_audit(
        session, action="enrichment_rule.create", resource_type="enrichment_rules",
        resource_id=rule.id, detail={"name": rule.name}, actor_id=actor_id,
    )
    return rule


async def update_enrichment_rule(
    session: AsyncSession, rule_id: int, payload: EnrichmentRuleUpdateRequest, *, actor_id: int
) -> EnrichmentRule:
    rule = await repo.get_enrichment_rule(session, rule_id)
    if rule is None:
        raise not_found("enrichment_rules", rule_id)
    changes: dict[str, Any] = {}
    for field in ("name", "matchers", "mappings", "priority", "enabled"):
        value = getattr(payload, field)
        if value is not None:
            setattr(rule, field, value)
            changes[field] = value
    await record_audit(
        session, action="enrichment_rule.update", resource_type="enrichment_rules",
        resource_id=rule.id, detail=changes, actor_id=actor_id,
    )
    return rule


async def delete_enrichment_rule(session: AsyncSession, rule_id: int, *, actor_id: int) -> None:
    rule = await repo.get_enrichment_rule(session, rule_id)
    if rule is None:
        raise not_found("enrichment_rules", rule_id)
    rule.deleted_at = utcnow()
    await record_audit(
        session, action="enrichment_rule.delete", resource_type="enrichment_rules",
        resource_id=rule.id, detail={"name": rule.name}, actor_id=actor_id,
    )


def _validate_auto_mode(rule_mode: str, activated_at) -> None:
    if rule_mode == "auto":
        if activated_at is None:
            raise ProblemError(
                status=400, detail="auto 关联模式必须设置 activated_at（BR-04 准入计算）",
            )
        if (utcnow() - activated_at).days < AUTO_MODE_MIN_AGE_DAYS:
            raise ProblemError(
                status=400,
                code="CORRELATION_AUTO_NOT_QUALIFIED",
                detail=f"auto 模式准入要求规则已运行 ≥{AUTO_MODE_MIN_AGE_DAYS} 天（BR-04）",
            )


async def create_correlation_rule(
    session: AsyncSession, payload: CorrelationRuleCreateRequest, *, actor_id: int
) -> CorrelationRule:
    _validate_auto_mode(payload.mode, payload.activated_at)
    rule = CorrelationRule(
        name=payload.name, conditions=payload.conditions,
        time_window_seconds=payload.time_window_seconds,
        mode=payload.mode, activated_at=payload.activated_at, enabled=payload.enabled,
    )
    session.add(rule)
    await session.flush()
    await record_audit(
        session, action="correlation_rule.create", resource_type="correlation_rules",
        resource_id=rule.id, detail={"name": rule.name, "mode": rule.mode}, actor_id=actor_id,
    )
    return rule


async def update_correlation_rule(
    session: AsyncSession, rule_id: int, payload: CorrelationRuleUpdateRequest, *, actor_id: int
) -> CorrelationRule:
    rule = await repo.get_correlation_rule(session, rule_id)
    if rule is None:
        raise not_found("correlation_rules", rule_id)
    changes: dict[str, Any] = {}
    for field in ("name", "conditions", "time_window_seconds", "enabled"):
        value = getattr(payload, field)
        if value is not None:
            setattr(rule, field, value)
            changes[field] = value
    if payload.mode is not None and payload.mode != rule.mode:
        effective_activated = rule.activated_at
        _validate_auto_mode(payload.mode, effective_activated)
        rule.mode = payload.mode
        changes["mode"] = payload.mode
    await record_audit(
        session, action="correlation_rule.update", resource_type="correlation_rules",
        resource_id=rule.id, detail=changes, actor_id=actor_id,
    )
    return rule


async def delete_correlation_rule(session: AsyncSession, rule_id: int, *, actor_id: int) -> None:
    rule = await repo.get_correlation_rule(session, rule_id)
    if rule is None:
        raise not_found("correlation_rules", rule_id)
    rule.deleted_at = utcnow()
    await record_audit(
        session, action="correlation_rule.delete", resource_type="correlation_rules",
        resource_id=rule.id, detail={"name": rule.name}, actor_id=actor_id,
    )


async def create_maintenance_window(
    session: AsyncSession, payload: MaintenanceWindowCreateRequest, *, actor_id: int
) -> MaintenanceWindow:
    if payload.ends_at <= payload.starts_at:
        raise ProblemError(status=400, detail="维护窗口 ends_at 必须晚于 starts_at")
    window = MaintenanceWindow(
        name=payload.name, scope=payload.scope, starts_at=payload.starts_at,
        ends_at=payload.ends_at, reason=payload.reason, created_by=actor_id,
    )
    session.add(window)
    await session.flush()
    await record_audit(
        session, action="maintenance_window.create", resource_type="maintenance_windows",
        resource_id=window.id, detail={"name": window.name}, actor_id=actor_id,
    )
    return window


# ---------- worker 侧入口 ----------


async def replay_scan(session: AsyncSession, *, stale_seconds: int, enqueue: EnqueueFn) -> int:
    """回放器：received 超时未消费的告警按 first_occurred_at 顺序重投（幂等由门闩兜底）。"""
    stale = await repo.stale_received(session, stale_seconds=stale_seconds)
    for alert in stale:
        await enqueue("alert.process_pipeline", alert.id)
    return len(stale)


async def close_expired_windows(session: AsyncSession, *, enqueue: EnqueueFn) -> int:
    """窗口结束仍未恢复的 suppressed 告警重新入管道（BR-07）。"""
    alerts = await repo.suppressed_by_ending_windows(session, now=utcnow())
    for alert in alerts:
        alert.status = AlertStatus.RECEIVED
        alert.suppressed_by_window_id = None
        await record_audit(
            session, action="alert.resubmit_after_window", resource_type="alerts",
            resource_id=alert.id, detail={}, actor_type="system",
        )
        await enqueue("alert.process_pipeline", alert.id)
    return len(alerts)


# ---------- Provider 管理（01-data-model §2.4 归告警管理域） ----------


_FORBIDDEN_CONFIG_KEYS = {"token", "secret", "password", "api_key", "apikey"}


async def create_provider(session: AsyncSession, payload, *, actor_id: int) -> Provider:
    if payload.config and any(k.lower() in _FORBIDDEN_CONFIG_KEYS for k in payload.config):
        raise ProblemError(
            status=400,
            detail="providers.config 禁止写入密钥值（D-2）：请改用 credential_id 引用密钥管理",
        )
    if await repo.provider_name_exists(session, payload.name):
        raise ProblemError(status=409, code="PROVIDER_CONFLICT", detail=f"Provider 名已存在：{payload.name}")
    provider = Provider(
        name=payload.name, type=payload.type, category=payload.category,
        pull_mode=payload.pull_mode, config=payload.config,
        credential_id=payload.credential_id, fingerprint_fields=payload.fingerprint_fields,
        enabled=payload.enabled,
    )
    session.add(provider)
    await session.flush()
    await record_audit(
        session, action="provider.create", resource_type="providers", resource_id=provider.id,
        detail={"name": provider.name, "type": provider.type}, actor_id=actor_id,
    )
    return provider


async def update_provider(session: AsyncSession, provider_id: int, payload, *, actor_id: int) -> Provider:
    provider = await repo.get_provider(session, provider_id)
    if provider is None:
        raise not_found("providers", provider_id)
    changes: dict = {}
    for field in ("name", "type", "category", "pull_mode", "config", "credential_id", "fingerprint_fields", "enabled"):
        value = getattr(payload, field)
        if value is not None:
            setattr(provider, field, value)
            changes[field] = value
    if payload.config and any(k.lower() in _FORBIDDEN_CONFIG_KEYS for k in payload.config):
        raise ProblemError(
            status=400,
            detail="providers.config 禁止写入密钥值（D-2）：请改用 credential_id 引用密钥管理",
        )
    await record_audit(
        session, action="provider.update", resource_type="providers", resource_id=provider.id,
        detail=changes, actor_id=actor_id,
    )
    return provider


async def delete_provider(session: AsyncSession, provider_id: int, *, actor_id: int) -> None:
    provider = await repo.get_provider(session, provider_id)
    if provider is None:
        raise not_found("providers", provider_id)
    provider.enabled = False  # Provider 无 deleted_at 列，停用等价移除（契约 204）
    await record_audit(
        session, action="provider.delete", resource_type="providers", resource_id=provider.id,
        detail={"name": provider.name}, actor_id=actor_id,
    )
