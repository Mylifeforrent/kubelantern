"""alerts/alert-ingestion/alert-rules tag 路由（webhook 机器入口 + 工作台 + 规则管理）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.app.deps import get_current_user, get_session, require_permission
from huntai.core.errors import ProblemError, not_found
from huntai.core.pagination import clamp_page
from huntai.core.security import Principal, TeamScope
from huntai.core.secrets import resolve_secret
from huntai.domains.alerts import repository as repo
from huntai.domains.alerts import service
from huntai.domains.alerts.schemas import (
    AIExplanationPage,
    AIExplanationResponse,
    AlertDetailResponse,
    AlertPage,
    AlertResponse,
    CorrelationRuleCreateRequest,
    CorrelationRulePage,
    CorrelationRuleResponse,
    CorrelationRuleUpdateRequest,
    EnrichmentRuleCreateRequest,
    EnrichmentRulePage,
    EnrichmentRuleResponse,
    EnrichmentRuleUpdateRequest,
    MaintenanceWindowCreateRequest,
    MaintenanceWindowPage,
    MaintenanceWindowResponse,
    WebhookIngestResult,
)
from huntai.domains.clusters import repository as clusters_repo

router = APIRouter()


def _publish(request: Request):
    async def publish(event) -> None:
        await request.app.state.hub.publish(event)

    return publish


def _enqueue(request: Request):
    async def enqueue(job_name: str, *args, **kwargs):
        from huntai.core.config import QUEUE_BY_JOB

        pool = request.app.state.arq_pool
        queue = kwargs.pop("_queue", None) or QUEUE_BY_JOB.get(job_name)
        return await pool.enqueue_job(job_name, *args, _queue_name=queue)

    return enqueue


def _alert_response(a: Any) -> AlertResponse:
    return AlertResponse(
        id=a.id, fingerprint=a.fingerprint, provider_id=a.provider_id, title=a.title,
        severity=a.severity.value if hasattr(a.severity, "value") else a.severity,
        status=a.status.value if hasattr(a.status, "value") else a.status,
        labels=a.labels, enrichments=a.enrichments, occurrence_count=a.occurrence_count,
        first_occurred_at=a.first_occurred_at, last_occurred_at=a.last_occurred_at,
        assignee_id=a.assignee_id, acknowledged_at=a.acknowledged_at, resolved_at=a.resolved_at,
        suppressed_by_window_id=a.suppressed_by_window_id,
        created_at=a.created_at, updated_at=a.updated_at,
    )


@router.post(
    "/alerts/webhook/{provider_key}",
    response_model=WebhookIngestResult,
    status_code=http_status.HTTP_202_ACCEPTED,
    tags=["alert-ingestion"],
)
async def ingest_alert_webhook(
    provider_key: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """机器入口：Provider 令牌认证（[ASSUMPTION] P0 Provider 框架详设）+ 先落盘再入队（ADR-0003）。"""
    from huntai.domains.alerts import repository as alerts_repo

    provider = await alerts_repo.get_provider_by_name(session, provider_key)
    if provider is None or not provider.enabled:
        raise not_found("providers", provider_key)
    if provider.credential_id is not None:
        cred = await clusters_repo.get_credential(session, provider.credential_id)
        if cred is None:
            raise ProblemError(status=500, detail=f"Provider {provider_key} 凭证引用缺失")
        expected = resolve_secret(cred.secret_ref)
        provided = request.headers.get("X-Provider-Token", "")
        if provided != expected:
            raise ProblemError(status=401, detail="Provider 令牌校验失败")
    payload = await request.json()
    alert_id, merged = await service.ingest(
        session, provider=provider, payload=payload,
        enqueue=_enqueue(request), publish=_publish(request),
    )
    return WebhookIngestResult(alert_id=alert_id, merged=merged)


@router.get("/alerts", response_model=AlertPage)
async def list_alerts(
    request: Request,
    severity: str | None = None,
    status: str | None = None,
    team: str | None = None,
    fingerprint: str | None = None,
    offset: int = 0,
    limit: int = 50,
    scope: TeamScope | None = Depends(require_permission("alerts", "read")),
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    alerts, total = await service.list_alerts(
        session, severity=severity, status=status, team=team, fingerprint=fingerprint,
        team_scope=scope.team if scope else None, offset=offset, limit=limit,
    )
    return AlertPage.build(
        [_alert_response(a) for a in alerts], total=total, offset=offset, limit=limit
    )


@router.get("/alerts/{alert_id}", response_model=AlertDetailResponse)
async def get_alert(
    alert_id: int,
    scope: TeamScope | None = Depends(require_permission("alerts", "read")),
    session: AsyncSession = Depends(get_session),
):
    alert = await service.get_alert(session, alert_id)
    _assert_team_visible(alert, scope)
    base = _alert_response(alert)
    return AlertDetailResponse(**base.model_dump(), raw_payload=alert.raw_payload)


@router.post("/alerts/{alert_id}/ack", response_model=AlertResponse)
async def ack_alert(
    request: Request,
    alert_id: int,
    scope: TeamScope | None = Depends(require_permission("alerts", "acknowledge")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    alert = await service.acknowledge(
        session, alert_id, actor_id=principal.user_id, publish=_publish(request)
    )
    from huntai.domains.notifications import service as notification_service

    await notification_service.record_alert_ack(session, alert_id=alert_id)  # 升级链停止留痕
    return _alert_response(alert)


@router.post("/alerts/{alert_id}/close", response_model=AlertResponse)
async def close_alert(
    request: Request,
    alert_id: int,
    _scope: TeamScope | None = Depends(require_permission("alerts", "close")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    alert = await service.close(
        session, alert_id, actor_id=principal.user_id, publish=_publish(request)
    )
    return _alert_response(alert)


@router.post(
    "/alerts/{alert_id}/convert-to-incident",
    status_code=http_status.HTTP_201_CREATED,
    response_model=None,
)
async def convert_alert_to_incident(
    alert_id: int,
    payload: dict | None = None,
    scope: TeamScope | None = Depends(require_permission("alerts", "convert")),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from huntai.domains.incidents.schemas import IncidentResponse

    body = payload or {}
    incident = await service.convert_to_incident(
        session, alert_id, actor_id=principal.user_id,
        title=body.get("title"), severity=body.get("severity"), team=body.get("team"),
        extra_alert_ids=body.get("related_alert_ids"),
    )
    from huntai.domains.incidents import service as incidents_service

    return IncidentResponse(
        id=incident.id, title=incident.title, severity=incident.severity,
        status=incident.status, source=incident.source, candidate_id=incident.candidate_id,
        correlation_rule_id=incident.correlation_rule_id, team=incident.team,
        assignee_id=incident.assignee_id, created_by=incident.created_by,
        status_page_sync=incident.status_page_sync, cancelled_reason=incident.cancelled_reason,
        acknowledged_at=incident.acknowledged_at, mitigated_at=incident.mitigated_at,
        resolved_at=incident.resolved_at, closed_at=incident.closed_at,
        created_at=incident.created_at, updated_at=incident.updated_at,
    )


@router.post("/alerts/{alert_id}/suppress-suggestion")
async def suppress_suggestion(
    alert_id: int,
    payload: dict | None = None,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """契约草案待补端点（M0 验收流「误报抑制建议提交」；前端已消费）。"""
    result = await service.suppress_suggestion(
        session, alert_id, actor_id=principal.user_id,
        reason=(payload or {}).get("reason"),
    )
    return result


@router.get("/alerts/{alert_id}/explanations", response_model=AIExplanationPage)
async def list_alert_explanations(
    alert_id: int,
    offset: int = 0,
    limit: int = 50,
    scope: TeamScope | None = Depends(require_permission("alerts", "read")),
    session: AsyncSession = Depends(get_session),
):
    """告警级 AI 解释：经转告警回链（findings.converted_alert_id）派生（契约 [ASSUMPTION] 映射）。"""
    from sqlalchemy import select

    from huntai.domains.ai.models import AIExplanation
    from huntai.domains.inspections.models import Finding

    alert = await service.get_alert(session, alert_id)
    _assert_team_visible(alert, scope)
    finding_ids = (
        (
            await session.execute(
                select(Finding.id).where(Finding.converted_alert_id == alert_id)
            )
        )
        .scalars()
        .all()
    )
    explanations = (
        (
            await session.execute(
                select(AIExplanation).where(AIExplanation.finding_id.in_(finding_ids)).offset(offset).limit(limit)
            )
        )
        .scalars()
        .all()
        if finding_ids
        else []
    )
    items = [
        AIExplanationResponse(
            id=e.id, finding_id=e.finding_id, task_id=e.task_id,
            sanitized_input_digest=e.sanitized_input_digest, output=e.output,
            model=e.model, tokens=e.tokens, created_at=e.created_at,
        )
        for e in explanations
    ]
    return AIExplanationPage.build(items, total=len(items), offset=offset, limit=limit)


def _assert_team_visible(alert: Any, scope: TeamScope | None) -> None:
    if alert is None:
        raise not_found("alerts", "?")
    if scope is not None:
        alert_team = (alert.enrichments or {}).get("team")
        if alert_team is not None and alert_team != scope.team:
            raise not_found("alerts", alert.id)  # 团队隔离越权一律 404 防探测


# ---------- 富化规则 ----------


def _enrich_response(r) -> EnrichmentRuleResponse:
    return EnrichmentRuleResponse(
        id=r.id, name=r.name, matchers=r.matchers, mappings=r.mappings, priority=r.priority,
        enabled=r.enabled, created_at=r.created_at, updated_at=r.updated_at,
    )


@router.get("/enrichment-rules", response_model=EnrichmentRulePage, tags=["alert-rules"], dependencies=[Depends(require_permission("enrichment_rules", "read"))])
async def list_enrichment_rules(
    enabled: bool | None = None, offset: int = 0, limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    rules, total = await repo.list_enrichment_rules(session, enabled=enabled, offset=offset, limit=limit)
    return EnrichmentRulePage.build(
        [_enrich_response(r) for r in rules], total=total, offset=offset, limit=limit
    )


@router.post("/enrichment-rules", response_model=EnrichmentRuleResponse, status_code=201, tags=["alert-rules"], dependencies=[Depends(require_permission("enrichment_rules", "write"))])
async def create_enrichment_rule(
    payload: EnrichmentRuleCreateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _enrich_response(await service.create_enrichment_rule(session, payload, actor_id=principal.user_id))


@router.get("/enrichment-rules/{rule_id}", response_model=EnrichmentRuleResponse, tags=["alert-rules"], dependencies=[Depends(require_permission("enrichment_rules", "read"))])
async def get_enrichment_rule(rule_id: int, session: AsyncSession = Depends(get_session)):
    rule = await repo.get_enrichment_rule(session, rule_id)
    if rule is None:
        raise not_found("enrichment_rules", rule_id)
    return _enrich_response(rule)


@router.put("/enrichment-rules/{rule_id}", response_model=EnrichmentRuleResponse, tags=["alert-rules"], dependencies=[Depends(require_permission("enrichment_rules", "write"))])
async def update_enrichment_rule(
    rule_id: int, payload: EnrichmentRuleUpdateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _enrich_response(
        await service.update_enrichment_rule(session, rule_id, payload, actor_id=principal.user_id)
    )


@router.delete("/enrichment-rules/{rule_id}", status_code=204, tags=["alert-rules"], dependencies=[Depends(require_permission("enrichment_rules", "write"))])
async def delete_enrichment_rule(
    rule_id: int, principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await service.delete_enrichment_rule(session, rule_id, actor_id=principal.user_id)
    from fastapi import Response

    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


# ---------- 关联规则（P2） ----------


def _corr_response(r) -> CorrelationRuleResponse:
    return CorrelationRuleResponse(
        id=r.id, name=r.name, conditions=r.conditions,
        time_window_seconds=r.time_window_seconds,
        mode=r.mode.value if hasattr(r.mode, "value") else r.mode,
        activated_at=r.activated_at, confirm_count=r.confirm_count, reject_count=r.reject_count,
        enabled=r.enabled, created_at=r.created_at, updated_at=r.updated_at,
    )


@router.get("/correlation-rules", response_model=CorrelationRulePage, tags=["alert-rules"], dependencies=[Depends(require_permission("correlation_rules", "read"))])
async def list_correlation_rules(
    mode: str | None = None, enabled: bool | None = None, offset: int = 0, limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    rules, total = await repo.list_correlation_rules(session, mode=mode, enabled=enabled, offset=offset, limit=limit)
    return CorrelationRulePage.build(
        [_corr_response(r) for r in rules], total=total, offset=offset, limit=limit
    )


@router.post("/correlation-rules", response_model=CorrelationRuleResponse, status_code=201, tags=["alert-rules"], dependencies=[Depends(require_permission("correlation_rules", "write"))])
async def create_correlation_rule(
    payload: CorrelationRuleCreateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _corr_response(await service.create_correlation_rule(session, payload, actor_id=principal.user_id))


@router.get("/correlation-rules/{rule_id}", response_model=CorrelationRuleResponse, tags=["alert-rules"], dependencies=[Depends(require_permission("correlation_rules", "read"))])
async def get_correlation_rule(rule_id: int, session: AsyncSession = Depends(get_session)):
    rule = await repo.get_correlation_rule(session, rule_id)
    if rule is None:
        raise not_found("correlation_rules", rule_id)
    return _corr_response(rule)


@router.put("/correlation-rules/{rule_id}", response_model=CorrelationRuleResponse, tags=["alert-rules"], dependencies=[Depends(require_permission("correlation_rules", "write"))])
async def update_correlation_rule(
    rule_id: int, payload: CorrelationRuleUpdateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return _corr_response(
        await service.update_correlation_rule(session, rule_id, payload, actor_id=principal.user_id)
    )


@router.delete("/correlation-rules/{rule_id}", status_code=204, tags=["alert-rules"], dependencies=[Depends(require_permission("correlation_rules", "write"))])
async def delete_correlation_rule(
    rule_id: int, principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await service.delete_correlation_rule(session, rule_id, actor_id=principal.user_id)
    from fastapi import Response

    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


# ---------- 维护窗口（P2） ----------


@router.get("/maintenance-windows", response_model=MaintenanceWindowPage, tags=["alert-rules"], dependencies=[Depends(require_permission("maintenance_windows", "read"))])
async def list_maintenance_windows(
    active_only: bool | None = None, offset: int = 0, limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    windows, total = await repo.list_maintenance_windows(
        session, active_only=active_only, offset=offset, limit=limit
    )
    items = [
        MaintenanceWindowResponse(
            id=w.id, name=w.name, scope=w.scope, starts_at=w.starts_at, ends_at=w.ends_at,
            reason=w.reason, created_by=w.created_by, created_at=w.created_at,
        )
        for w in windows
    ]
    return MaintenanceWindowPage.build(items, total=total, offset=offset, limit=limit)


@router.post("/maintenance-windows", response_model=MaintenanceWindowResponse, status_code=201, tags=["alert-rules"], dependencies=[Depends(require_permission("maintenance_windows", "write"))])
async def create_maintenance_window(
    payload: MaintenanceWindowCreateRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    window = await service.create_maintenance_window(session, payload, actor_id=principal.user_id)
    return MaintenanceWindowResponse(
        id=window.id, name=window.name, scope=window.scope, starts_at=window.starts_at,
        ends_at=window.ends_at, reason=window.reason, created_by=window.created_by,
        created_at=window.created_at,
    )
