"""告警域数据访问（含 D-1 upsert、团队行级过滤、富化/关联/窗口规则）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, desc, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.pagination import paginate
from huntai.domains.alerts.models import (
    Alert,
    AlertStatus,
    CorrelationRule,
    EnrichmentRule,
    MaintenanceWindow,
    Provider,
)

# D-1 指纹 upsert（04-backend-design §3.2.1 原文 SQL；活跃指纹部分唯一索引仲裁）
_UPSERT_SQL = text(
    """
    INSERT INTO alerts (fingerprint, provider_id, title, severity, labels, raw_payload,
                        first_occurred_at, last_occurred_at, status, occurrence_count)
    VALUES (:fingerprint, :provider_id, :title, :severity, :labels, :raw_payload,
            :occurred_at, :occurred_at, 'received', 1)
    ON CONFLICT (fingerprint) WHERE status <> 'resolved'
    DO UPDATE SET occurrence_count = alerts.occurrence_count + 1,
                  last_occurred_at = EXCLUDED.last_occurred_at
    RETURNING id, (xmax = 0) AS inserted
    """
)


async def upsert_alert(
    session: AsyncSession, *, fingerprint: str, provider_id: int, title: str | None,
    severity: str, labels: dict, raw_payload: dict, occurred_at: datetime,
) -> tuple[int, bool]:
    import json

    result = await session.execute(
        _UPSERT_SQL,
        {
            "fingerprint": fingerprint,
            "provider_id": provider_id,
            "title": title,
            "severity": severity,
            "labels": json.dumps(labels, ensure_ascii=False),
            "raw_payload": json.dumps(raw_payload, ensure_ascii=False, default=str),
            "occurred_at": occurred_at,
        },
    )
    row = result.one()
    return row.id, bool(row.inserted)


async def get_alert(session: AsyncSession, alert_id: int) -> Alert | None:
    return await session.get(Alert, alert_id)


async def get_active_by_fingerprint(session: AsyncSession, fingerprint: str) -> Alert | None:
    return (
        await session.execute(
            select(Alert).where(Alert.fingerprint == fingerprint, Alert.status != AlertStatus.RESOLVED)
        )
    ).scalar_one_or_none()


async def list_alerts(
    session: AsyncSession,
    *,
    severity: str | None = None,
    status: str | None = None,
    team: str | None = None,
    fingerprint: str | None = None,
    team_scope: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Alert], int]:
    stmt = select(Alert).order_by(desc(Alert.last_occurred_at))
    if severity is not None:
        stmt = stmt.where(Alert.severity == severity)
    if status is not None:
        stmt = stmt.where(Alert.status == status)
    if fingerprint is not None:
        stmt = stmt.where(Alert.fingerprint == fingerprint)
    if team is not None:
        stmt = stmt.where(Alert.enrichments["team"].astext == team)
    if team_scope is not None:
        # T 行级过滤：enrichments.team 缺失或等于本团队（[TBD-BE] 表达式索引增补待确认）
        team_filter = or_(
            Alert.enrichments["team"].astext == team_scope,
            ~Alert.enrichments.has_key("team"),
        )
        stmt = stmt.where(team_filter)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def gate_to_enriched(session: AsyncSession, alert_id: int) -> bool:
    """幂等门闩：received/deduplicated → enriched；已被处理则 False（04-backend-design §3.2.2）。"""
    result = await session.execute(
        update(Alert)
        .where(Alert.id == alert_id, Alert.status.in_([AlertStatus.RECEIVED, AlertStatus.DEDUPLICATED]))
        .values(status=AlertStatus.ENRICHED)
    )
    return result.rowcount > 0


async def set_status(session: AsyncSession, alert_id: int, status: AlertStatus, **extra) -> bool:
    result = await session.execute(
        update(Alert).where(Alert.id == alert_id).values(status=status, **extra)
    )
    return result.rowcount > 0


async def active_alerts_matching(
    session: AsyncSession,
    *,
    since: datetime,
    exclude_id: int,
) -> list[Alert]:
    """时间窗内活跃（未 resolved）告警，供关联引擎分组。"""
    rows = await session.execute(
        select(Alert)
        .where(
            Alert.status != AlertStatus.RESOLVED,
            Alert.last_occurred_at >= since,
            Alert.id != exclude_id,
        )
        .order_by(Alert.first_occurred_at)
    )
    return list(rows.scalars().all())


async def stale_received(session: AsyncSession, *, stale_seconds: int, batch: int = 100) -> list[Alert]:
    """回放器：received 且超时未被管道消费的告警。"""
    threshold = func.now() - text(f"interval '{stale_seconds} seconds'")
    rows = await session.execute(
        select(Alert)
        .where(Alert.status == AlertStatus.RECEIVED, Alert.updated_at < threshold)
        .order_by(Alert.first_occurred_at)
        .limit(batch)
    )
    return list(rows.scalars().all())


async def suppressed_by_ending_windows(session: AsyncSession, *, now: datetime, batch: int = 100) -> list[Alert]:
    """窗口结束仍未恢复的 suppressed 告警（BR-07 重入管道）。"""
    rows = await session.execute(
        select(Alert, MaintenanceWindow)
        .join(MaintenanceWindow, Alert.suppressed_by_window_id == MaintenanceWindow.id)
        .where(Alert.status == AlertStatus.SUPPRESSED, MaintenanceWindow.ends_at <= now)
        .limit(batch)
    )
    return [alert for alert, _window in rows.all()]


async def active_windows(session: AsyncSession, *, now: datetime) -> list[MaintenanceWindow]:
    rows = await session.execute(
        select(MaintenanceWindow).where(
            MaintenanceWindow.starts_at <= now, MaintenanceWindow.ends_at > now
        )
    )
    return list(rows.scalars().all())


async def list_enrichment_rules(
    session: AsyncSession, *, enabled: bool | None = None, offset: int = 0, limit: int = 50
) -> tuple[list[EnrichmentRule], int]:
    stmt = select(EnrichmentRule).where(EnrichmentRule.deleted_at.is_(None)).order_by(EnrichmentRule.id)
    if enabled is not None:
        stmt = stmt.where(EnrichmentRule.enabled == enabled)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def active_enrichment_rules(session: AsyncSession) -> list[EnrichmentRule]:
    rows = await session.execute(
        select(EnrichmentRule)
        .where(EnrichmentRule.enabled.is_(True), EnrichmentRule.deleted_at.is_(None))
        .order_by(EnrichmentRule.priority)
    )
    return list(rows.scalars().all())


async def get_enrichment_rule(session: AsyncSession, rule_id: int) -> EnrichmentRule | None:
    rule = await session.get(EnrichmentRule, rule_id)
    if rule is not None and rule.deleted_at is not None:
        return None
    return rule


async def list_correlation_rules(
    session: AsyncSession, *, mode: str | None = None, enabled: bool | None = None,
    offset: int = 0, limit: int = 50,
) -> tuple[list[CorrelationRule], int]:
    stmt = select(CorrelationRule).where(CorrelationRule.deleted_at.is_(None)).order_by(CorrelationRule.id)
    if mode is not None:
        stmt = stmt.where(CorrelationRule.mode == mode)
    if enabled is not None:
        stmt = stmt.where(CorrelationRule.enabled == enabled)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def enabled_correlation_rules(session: AsyncSession) -> list[CorrelationRule]:
    rows = await session.execute(
        select(CorrelationRule).where(
            CorrelationRule.enabled.is_(True), CorrelationRule.deleted_at.is_(None)
        )
    )
    return list(rows.scalars().all())


async def get_correlation_rule(session: AsyncSession, rule_id: int) -> CorrelationRule | None:
    rule = await session.get(CorrelationRule, rule_id)
    if rule is not None and rule.deleted_at is not None:
        return None
    return rule


async def list_maintenance_windows(
    session: AsyncSession, *, active_only: bool | None = None, offset: int = 0, limit: int = 50
) -> tuple[list[MaintenanceWindow], int]:
    stmt = select(MaintenanceWindow).order_by(desc(MaintenanceWindow.starts_at))
    if active_only:
        now = func.now()
        stmt = stmt.where(and_(MaintenanceWindow.starts_at <= now, MaintenanceWindow.ends_at > now))
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def alerts_by_ids(session: AsyncSession, alert_ids: list[int]) -> list[Alert]:
    if not alert_ids:
        return []
    rows = await session.execute(select(Alert).where(Alert.id.in_(alert_ids)))
    return list(rows.scalars().all())


# ---------- Provider（01-data-model §2.4 归告警管理域） ----------


async def list_providers(
    session: AsyncSession,
    *,
    category: str | None = None,
    enabled: bool | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Provider], int]:
    stmt = select(Provider).order_by(Provider.id)
    if category is not None:
        stmt = stmt.where(Provider.category == category)
    if enabled is not None:
        stmt = stmt.where(Provider.enabled == enabled)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def get_provider(session: AsyncSession, provider_id: int) -> Provider | None:
    return await session.get(Provider, provider_id)


async def get_provider_by_name(session: AsyncSession, name: str) -> Provider | None:
    return (
        await session.execute(select(Provider).where(Provider.name == name))
    ).scalar_one_or_none()


async def provider_name_exists(session: AsyncSession, name: str, *, exclude_id: int | None = None) -> bool:
    stmt = select(Provider.id).where(Provider.name == name)
    if exclude_id is not None:
        stmt = stmt.where(Provider.id != exclude_id)
    row = await session.execute(stmt)
    return row.scalar_one_or_none() is not None


async def bump_window_counters(
    session: AsyncSession, rule_id: int, *, confirmed: bool
) -> None:
    if confirmed:
        await session.execute(
            update(CorrelationRule)
            .where(CorrelationRule.id == rule_id)
            .values(confirm_count=CorrelationRule.confirm_count + 1)
        )
    else:
        await session.execute(
            update(CorrelationRule)
            .where(CorrelationRule.id == rule_id)
            .values(reject_count=CorrelationRule.reject_count + 1)
        )


async def window_alerts(session: AsyncSession, window_id: int) -> list[Alert]:
    rows = await session.execute(
        select(Alert).where(Alert.suppressed_by_window_id == window_id)
    )
    return list(rows.scalars().all())
