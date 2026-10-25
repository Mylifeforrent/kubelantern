"""e2e 链路二（文档 §7.3 必测）：BR-04 候选事件确认流。"""

from __future__ import annotations

import pytest
from sqlalchemy import select

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def _noop_enqueue(job_name, *args, **kwargs):
    return None


async def _alert(db_session, name: str, team: str):
    from huntai.domains.alerts.models import Provider

    provider = Provider(name=f"p-{name}", type="alertmanager", category="source")
    db_session.add(provider)
    await db_session.flush()
    from huntai.domains.alerts import service

    return await service.ingest(
        db_session, provider=provider, enqueue=_noop_enqueue,
        payload={
            "status": "firing",
            "labels": {"alertname": name, "namespace": "prod", "team": team, "severity": "warning"},
        },
    )


async def _candidate_rule(db_session, *, mode: str = "candidate", activated_at=None):
    from huntai.domains.alerts.models import CorrelationRule

    rule = CorrelationRule(
        name=f"r-{mode}-{activated_at}", conditions={
            "op": "AND",
            "rules": [{"field": "namespace", "operator": "eq", "value": "prod"}],
            "group_by": ["namespace"],
        },
        time_window_seconds=600, mode=mode, activated_at=activated_at,
    )
    db_session.add(rule)
    await db_session.flush()
    return rule


async def test_br04_candidate_flow_confirm_and_reject(db_session):
    from huntai.domains.alerts.models import AlertStatus
    from huntai.domains.incidents import repository as incident_repo
    from huntai.domains.incidents import service
    from huntai.domains.incidents.schemas import CandidateRejectRequest
    from huntai.domains.incidents.models import Incident, IncidentAlert, IncidentCandidate
    from tests.conftest import seed_roles, seed_user

    await seed_roles(db_session)
    admin_id = await seed_user(db_session, "admin", "admin")
    rule = await _candidate_rule(db_session)
    first_id, _ = await _alert(db_session, "ErrorA", "platform")
    second_id, _ = await _alert(db_session, "ErrorB", "platform")

    from huntai.domains.alerts import service as alerts_service

    for alert_id in (first_id, second_id):
        await alerts_service.process_pipeline(db_session, alert_id)

    candidate = (
        await db_session.execute(select(IncidentCandidate).order_by(IncidentCandidate.id))
    ).scalars().first()
    assert candidate is not None, "两告警命中同一规则 → 候选事件产生（D-8）"
    assert candidate.status.value == "pending"
    assert sorted(candidate.member_alert_ids) == sorted([first_id, second_id])
    assert (
        await db_session.execute(select(Incident).where(Incident.candidate_id == candidate.id))
    ).scalar_one_or_none() is None, "pending 候选不产生 incident"

    # 确认 → incident(source=correlation) + incident_alerts + 告警置 correlated + 计数
    incident = await service.confirm_candidate(db_session, candidate.id, actor_id=admin_id)
    source = incident.source.value if hasattr(incident.source, "value") else incident.source
    assert source == "correlation"
    links = await incident_repo.linked_alerts(db_session, incident.id)
    assert {link.alert_id for link in links} == {first_id, second_id}
    refreshed = await db_session.execute(select(IncidentCandidate).where(IncidentCandidate.id == candidate.id))
    refreshed_status = refreshed.scalar_one().status
    assert (refreshed_status.value if hasattr(refreshed_status, "value") else refreshed_status) == "confirmed"
    rule_after = await db_session.get(type(rule), rule.id)
    assert rule_after.confirm_count == 1
    for alert_id in (first_id, second_id):
        from huntai.domains.alerts.models import Alert

        alert = await db_session.get(Alert, alert_id)
        assert alert.status.value == "correlated"
    # P2 事件（severity P2，因告警 warning）自动同步状态页（BR-06）
    entry = await incident_repo.entry_for_incident(db_session, incident.id)
    assert entry is not None

    # 第二条候选走驳回路径
    third_id, _ = await _alert(db_session, "ErrorC", "platform")
    fourth_id, _ = await _alert(db_session, "ErrorD", "platform")
    for alert_id in (third_id, fourth_id):
        await alerts_service.process_pipeline(db_session, alert_id)
    pending = (
        await db_session.execute(
            select(IncidentCandidate).where(IncidentCandidate.status == "pending")
        )
    ).scalars().first()
    assert pending is not None
    rejected = await service.reject_candidate(
        db_session, pending.id,
        CandidateRejectRequest(reject_reason="rule_too_broad"),
        actor_id=admin_id,
    )
    rejected_status = rejected.status.value if hasattr(rejected.status, "value") else rejected.status
    assert rejected_status == "rejected"
    assert rejected.reject_reason == "rule_too_broad"
    rule_final = await db_session.get(type(rule), rule.id)
    assert rule_final.reject_count == 1


async def test_br04_auto_mode_requires_30_days_age(db_session):
    from datetime import UTC, datetime, timedelta

    from huntai.core.errors import ProblemError
    from huntai.domains.alerts import service as alerts_service
    from huntai.domains.alerts.schemas import CorrelationRuleCreateRequest

    young = CorrelationRuleCreateRequest(
        name="auto-young", conditions={"op": "AND", "rules": [{"field": "a", "operator": "eq", "value": "b"}]},
        time_window_seconds=300, mode="auto",
        activated_at=datetime.now(UTC) - timedelta(days=7),
    )
    with pytest.raises(ProblemError) as exc_info:
        await alerts_service.create_correlation_rule(db_session, young, actor_id=1)
    assert "≥30" in exc_info.value.detail

    unactivated = CorrelationRuleCreateRequest(
        name="auto-noage", conditions=young.conditions, time_window_seconds=300, mode="auto",
    )
    with pytest.raises(ProblemError):
        await alerts_service.create_correlation_rule(db_session, unactivated, actor_id=1)
