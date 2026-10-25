"""通知中心域（P2）：渠道抽象、投递留痕（BR-08）、升级链（BR-13）。

- notification_records 只追加（D-6 库级 REVOKE）：每次状态演进写新行而非 UPDATE。
- 渠道真实对接 [TBD-BIZ]；dev 渠道投递即记 sent，结构就绪后替换 Channel 实现。
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.errors import not_found
from huntai.core.pagination import clamp_page, paginate
from huntai.domains.iam.service import record_audit
from huntai.domains.notifications.models import NotificationRecord, NotificationStatus
from huntai.domains.oncall import repository as oncall_repo
from huntai.domains.oncall.service import current_oncall

logger = logging.getLogger("huntai.notifications")


@dataclass
class DeliveryResult:
    ok: bool
    error: str | None = None


class Channel(Protocol):
    name: str  # im / sms / voice

    async def send(self, target: str, message: str) -> DeliveryResult: ...


class DevImChannel:
    """dev 渠道：不外呼，投递即成功（真实渠道组合 [TBD-BIZ]）。"""

    name = "im"

    async def send(self, target: str, message: str) -> DeliveryResult:
        logger.info("notification delivered", extra={"props": {"channel": self.name, "target": target}})
        return DeliveryResult(ok=True)


CHANNELS: dict[str, Channel] = {"im": DevImChannel()}


def content_digest(message: str) -> str:
    return hashlib.sha256(message.encode()).hexdigest()[:32]


async def _append_record(
    session: AsyncSession,
    *,
    channel: str,
    target: str,
    digest: str,
    status: NotificationStatus,
    alert_id: int | None = None,
    incident_id: int | None = None,
    escalation_policy_id: int | None = None,
    escalation_level: int | None = None,
    error: str | None = None,
) -> NotificationRecord:
    record = NotificationRecord(
        channel=channel, target=target, content_digest=digest, status=status,
        alert_id=alert_id, incident_id=incident_id,
        escalation_policy_id=escalation_policy_id, escalation_level=escalation_level,
        error=error,
    )
    session.add(record)
    await session.flush()
    return record


async def _send_with_fallbacks(
    session: AsyncSession,
    *,
    channel_name: str,
    fallbacks: list,
    target: str,
    message: str,
    **record_kwargs,
) -> bool:
    """BR-13 降级链：主渠道失败依序降级；每次尝试独立留痕。"""
    chain = [channel_name] + [str(fb) for fb in fallbacks if str(fb) in CHANNELS]
    last_error: str | None = None
    for name in chain:
        channel = CHANNELS.get(name)
        if channel is None:
            last_error = f"渠道未注册：{name}"
            await _append_record(
                session, channel=name, target=target, digest=content_digest(message),
                status=NotificationStatus.FAILED, error=last_error, **record_kwargs,
            )
            continue
        result = await channel.send(target, message)
        await _append_record(
            session, channel=name, target=target, digest=content_digest(message),
            status=NotificationStatus.SENT if result.ok else NotificationStatus.FAILED,
            error=result.error, **record_kwargs,
        )
        if result.ok:
            return True
        last_error = result.error
    return False


async def dispatch_for_alert(
    session: AsyncSession, *, alert_id: int, team: str | None, enqueue=None
) -> list[NotificationRecord]:
    """告警管道末段触发：定位升级链第 1 级并投递（P2）。"""
    from huntai.domains.alerts import repository as alerts_repo

    alert = await alerts_repo.get_alert(session, alert_id)
    if alert is None:
        raise not_found("alerts", alert_id)
    policies = await oncall_repo.enabled_policies(session)
    policy = None
    for candidate in policies:
        schedule = await oncall_repo.get_schedule(session, candidate.schedule_id)
        if schedule is not None and (team is None or schedule.team == team):
            policy = candidate
            break
    title = alert.title or alert.labels.get("alertname") or alert.fingerprint[:8]
    message = f"[{alert.severity.value if hasattr(alert.severity, 'value') else alert.severity}] {title}"
    records: list[NotificationRecord] = []
    if policy is None or not policy.levels:
        # 无升级链：仍按 dev IM 渠道投递当前值班团队（保底通知）
        targets = await current_oncall(session, team) if team else []
        for target in targets or ["admin"]:
            await _send_with_fallbacks(
                session, channel_name="im", fallbacks=[], target=target,
                message=message, alert_id=alert_id,
            )
        return records
    first_level = min(policy.levels, key=lambda level: level["level"])
    targets = await _resolve_targets(session, first_level, team)
    for target in targets:
        await _send_with_fallbacks(
            session, channel_name=str(first_level.get("channel", "im")),
            fallbacks=list(policy.channel_fallbacks or []), target=target,
            message=message, alert_id=alert_id,
            escalation_policy_id=policy.id, escalation_level=first_level["level"],
        )
    if enqueue is not None and len(policy.levels) > 1:
        import datetime as dt

        await enqueue(
            "escalation.check_ack", alert_id=alert_id, policy_id=policy.id,
            level=first_level["level"],
            _defer_by=dt.timedelta(minutes=int(first_level.get("timeout_min", 15))),
        )
    await record_audit(
        session, action="notification.dispatch", resource_type="alerts",
        resource_id=alert_id, detail={"policy": policy.name}, actor_type="system",
    )
    return records


async def _resolve_targets(session: AsyncSession, level: dict, team: str | None) -> list[str]:
    target = str(level.get("target", ""))
    if target.startswith("oncall:"):
        return await current_oncall(session, target.split(":", 1)[1])
    if target == "oncall" and team:
        return await current_oncall(session, team)
    return [target or "admin"]


async def escalate_level(
    session: AsyncSession, *, alert_id: int, policy_id: int, level: int
) -> bool:
    """升级链推进：目标未 Ack → 下一级投递；全渠道失败不停链直接进下一级（BR-13）。"""
    from huntai.domains.alerts import repository as alerts_repo

    alert = await alerts_repo.get_alert(session, alert_id)
    if alert is None:
        return False
    if alert.acknowledged_at is not None or alert.status.value == "resolved":
        return False  # Ack 同步驱动升级链停止
    policy = await oncall_repo.get_policy(session, policy_id)
    if policy is None:
        return False
    levels = sorted(policy.levels, key=lambda level_def: level_def["level"])
    next_level = next((item for item in levels if item["level"] > level), None)
    if next_level is None:
        await record_audit(
            session, action="escalation.exhausted", resource_type="alerts",
            resource_id=alert_id, detail={"policy": policy.name}, actor_type="system",
        )
        return False
    team = (alert.enrichments or {}).get("team")
    title = alert.title or alert.labels.get("alertname") or alert.fingerprint[:8]
    message = f"[升级 L{next_level['level']}] {title}"
    for target in await _resolve_targets(session, next_level, team):
        await _send_with_fallbacks(
            session, channel_name=str(next_level.get("channel", "im")),
            fallbacks=list(policy.channel_fallbacks or []), target=target,
            message=message, alert_id=alert_id,
            escalation_policy_id=policy.id, escalation_level=next_level["level"],
        )
    await record_audit(
        session, action="escalation.advance", resource_type="alerts", resource_id=alert_id,
        detail={"policy": policy.name, "to_level": next_level["level"]}, actor_type="system",
    )
    return True


async def record_alert_ack(session: AsyncSession, *, alert_id: int) -> None:
    """告警被 Ack：追加 acked 留痕（升级链读取 ack 状态停止）。"""
    recent = await session.execute(
        select(NotificationRecord)
        .where(NotificationRecord.alert_id == alert_id)
        .order_by(NotificationRecord.id.desc())
        .limit(1)
    )
    latest = recent.scalar_one_or_none()
    if latest is None:
        return
    await _append_record(
        session, channel=latest.channel, target=latest.target,
        digest=latest.content_digest, status=NotificationStatus.ACKED,
        alert_id=alert_id, ack_action="ack",
    )


async def list_records(
    session: AsyncSession,
    *,
    alert_id: int | None = None,
    incident_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[NotificationRecord], int]:
    from huntai.domains.notifications.models import NotificationRecord as NR

    stmt = select(NR).order_by(NR.id.desc())
    if alert_id is not None:
        stmt = stmt.where(NR.alert_id == alert_id)
    if incident_id is not None:
        stmt = stmt.where(NR.incident_id == incident_id)
    if status is not None:
        stmt = stmt.where(NR.status == status)
    offset, limit = clamp_page(offset, limit)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total
