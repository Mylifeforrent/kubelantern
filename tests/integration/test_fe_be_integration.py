"""集成测试：前后端联调补录行为（搜索、策略规则集、人工记录、状态页撤回）。

覆盖 2026-10-25 联调中修复的契约偏差，防止回归。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from tests.conftest import seed_roles, seed_user

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


class FakeHub:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def publish(self, event) -> None:
        self.events.append(event)


@pytest.fixture()
async def client(sessionmaker, db_session, test_settings):
    import httpx

    from huntai.app.main import create_app
    from tests.conftest import FakeArqPool

    app = create_app(test_settings)
    app.state.settings = test_settings
    app.state.sessionmaker = sessionmaker
    app.state.arq_pool = FakeArqPool()
    app.state.hub = FakeHub()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


async def _admin(client, session) -> dict[str, str]:
    await seed_roles(session)
    await seed_user(session, "admin", "admin")
    return await _login(client, "admin")


async def _login(client, username: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/token", json={"username": username, "password": "test-password"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _seed_alert(session, *, title: str, team: str, fingerprint: str) -> int:
    from huntai.core.db import utcnow
    from huntai.domains.alerts.models import (
        Alert,
        AlertSeverity,
        AlertStatus,
        Provider,
        ProviderCategory,
    )

    provider = (
        await session.execute(select(Provider).where(Provider.name == "it-provider"))
    ).scalar_one_or_none()
    if provider is None:
        provider = Provider(
            name="it-provider", type="prometheus", category=ProviderCategory.SOURCE
        )
        session.add(provider)
        await session.flush()
    alert = Alert(
        fingerprint=fingerprint,
        provider_id=provider.id,
        title=title,
        severity=AlertSeverity.WARNING,
        status=AlertStatus.NOTIFIED,
        enrichments={"team": team},
        raw_payload={},
        first_occurred_at=utcnow(),
        last_occurred_at=utcnow(),
    )
    session.add(alert)
    await session.commit()
    return alert.id


async def _seed_cluster_and_rules(session) -> tuple[int, list[int]]:
    from huntai.domains.clusters.models import Cluster, Credential
    from huntai.domains.inspections.models import FindingSeverity, InspectionRule

    cred = Credential(name="it-cred", secret_ref="env:IT_TOKEN")
    session.add(cred)
    await session.flush()
    cluster = Cluster(
        name="it-cluster", environment="dev", api_endpoint="https://k8s.test", credential_id=cred.id
    )
    session.add(cluster)
    rules = [
        InspectionRule(
            code="it-pod-crashloop", name="Pod 崩溃循环", category="pod",
            severity_default=FindingSeverity.CRITICAL, k8s_version_fit=">=1.20",
        ),
        InspectionRule(
            code="it-pvc-pending", name="PVC 未绑定", category="pvc",
            severity_default=FindingSeverity.WARNING, k8s_version_fit=">=1.20",
        ),
    ]
    session.add_all(rules)
    await session.commit()
    return cluster.id, [r.id for r in rules]


async def test_alert_search_q_filters_title_or_fingerprint(db_session, client):
    from huntai.core.db import utcnow
    from huntai.domains.alerts.models import Alert, AlertSeverity, AlertStatus, Provider, ProviderCategory

    headers = await _admin(client, db_session)
    provider = Provider(name="it-provider", type="prometheus", category=ProviderCategory.SOURCE)
    db_session.add(provider)
    await db_session.flush()
    db_session.add_all([
        Alert(
            fingerprint="fp-alpha", provider_id=provider.id, title="AlphaGateway5xx",
            severity=AlertSeverity.CRITICAL, status=AlertStatus.NOTIFIED, raw_payload={},
            first_occurred_at=utcnow(), last_occurred_at=utcnow(),
        ),
        Alert(
            fingerprint="fp-beta", provider_id=provider.id, title="BetaDbLatency",
            severity=AlertSeverity.WARNING, status=AlertStatus.NOTIFIED, raw_payload={},
            first_occurred_at=utcnow(), last_occurred_at=utcnow(),
        ),
    ])
    await db_session.commit()

    hit = await client.get("/api/v1/alerts", params={"q": "Alpha"}, headers=headers)
    assert hit.status_code == 200, hit.text
    assert hit.json()["total"] == 1
    assert hit.json()["items"][0]["title"] == "AlphaGateway5xx"

    fp = await client.get("/api/v1/alerts", params={"q": "fp-beta"}, headers=headers)
    assert fp.json()["total"] == 1
    assert fp.json()["items"][0]["title"] == "BetaDbLatency"


async def test_inspection_policy_response_includes_rule_ids(db_session, client):
    headers = await _admin(client, db_session)
    cluster_id, rule_ids = await _seed_cluster_and_rules(db_session)

    created = await client.post(
        "/api/v1/inspection-policies",
        headers=headers,
        json={
            "cluster_id": cluster_id,
            "name": "联调策略",
            "schedule": "*/5 * * * *",
            "rule_ids": rule_ids,
        },
    )
    assert created.status_code == 201, created.text
    assert sorted(created.json()["rule_ids"]) == sorted(rule_ids)

    listed = await client.get("/api/v1/inspection-policies", headers=headers)
    assert listed.status_code == 200
    assert sorted(listed.json()["items"][0]["rule_ids"]) == sorted(rule_ids)


async def test_incident_note_appended_to_timeline(db_session, client):
    headers = await _admin(client, db_session)

    created = await client.post(
        "/api/v1/incidents",
        headers=headers,
        json={"title": "联调事件", "severity": "P3"},
    )
    assert created.status_code == 201, created.text
    incident_id = created.json()["id"]

    note = await client.post(
        f"/api/v1/incidents/{incident_id}/notes",
        headers=headers,
        json={"note": "已确认网关指标恢复"},
    )
    assert note.status_code == 201, note.text

    detail = await client.get(f"/api/v1/incidents/{incident_id}", headers=headers)
    assert detail.status_code == 200
    manual = [t for t in detail.json()["timeline"] if t["kind"] == "manual_note"]
    assert [t["summary"] for t in manual] == ["已确认网关指标恢复"]


async def test_status_page_sync_and_undo_returns_entry(db_session, client):
    headers = await _admin(client, db_session)
    created = await client.post(
        "/api/v1/incidents", headers=headers, json={"title": "状态页事件", "severity": "P3"}
    )
    incident_id = created.json()["id"]

    synced = await client.post(
        f"/api/v1/incidents/{incident_id}/status-page/sync", headers=headers
    )
    assert synced.status_code == 200, synced.text
    entry_id = synced.json()["id"]

    detail = await client.get(f"/api/v1/status-page/entries/{entry_id}", headers=headers)
    assert detail.status_code == 200
    assert len(detail.json()["updates"]) >= 1

    undone = await client.post(
        f"/api/v1/incidents/{incident_id}/status-page/undo", headers=headers
    )
    assert undone.status_code == 200, undone.text
    assert undone.json()["id"] == entry_id
    assert any(u["is_revoked"] for u in undone.json()["updates"])


async def test_suppress_suggestion_persists_reason_and_note(db_session, client):
    headers = await _admin(client, db_session)
    alert_id = await _seed_alert(
        db_session, title="网关误报", team="platform", fingerprint="fp-suppress-note"
    )

    response = await client.post(
        f"/api/v1/alerts/{alert_id}/suppress-suggestion",
        headers=headers,
        json={"reason": "false_positive", "note": "变更单 CHG-1 期间的预期误报"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"accepted": True, "alert_id": alert_id}

    logs = await client.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={"action": "alert.suppress_suggestion", "resource_id": str(alert_id)},
    )
    assert logs.status_code == 200
    detail = logs.json()["items"][0]["detail"]
    assert detail["reason"] == "false_positive"
    assert detail["note"] == "变更单 CHG-1 期间的预期误报"


async def test_suppress_suggestion_rejects_unknown_reason(db_session, client):
    headers = await _admin(client, db_session)
    alert_id = await _seed_alert(
        db_session, title="网关误报", team="platform", fingerprint="fp-suppress-invalid"
    )

    response = await client.post(
        f"/api/v1/alerts/{alert_id}/suppress-suggestion",
        headers=headers,
        json={"reason": "not_a_reason"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == 422 and body["title"] == "Validation error"


async def test_suppress_suggestion_enforces_role_and_team_scope(db_session, client):
    headers = await _admin(client, db_session)
    await seed_user(db_session, "dev", "developer", team="platform", team_scope="platform")
    await seed_user(db_session, "viewer", "viewer")
    dev_headers = await _login(client, "dev")
    viewer_headers = await _login(client, "viewer")

    own_alert = await _seed_alert(
        db_session, title="本团队告警", team="platform", fingerprint="fp-own-team"
    )
    other_alert = await _seed_alert(
        db_session, title="他团队告警", team="other", fingerprint="fp-other-team"
    )

    allowed = await client.post(
        f"/api/v1/alerts/{own_alert}/suppress-suggestion",
        headers=dev_headers,
        json={"reason": "expected_noise"},
    )
    assert allowed.status_code == 200, allowed.text

    hidden = await client.post(
        f"/api/v1/alerts/{other_alert}/suppress-suggestion",
        headers=dev_headers,
        json={"reason": "expected_noise"},
    )
    assert hidden.status_code == 404, hidden.text

    denied = await client.post(
        f"/api/v1/alerts/{own_alert}/suppress-suggestion",
        headers=viewer_headers,
        json={"reason": "duplicate_rule"},
    )
    assert denied.status_code == 403, denied.text

    admin_ok = await client.post(
        f"/api/v1/alerts/{other_alert}/suppress-suggestion",
        headers=headers,
        json={"reason": "duplicate_rule", "note": "admin 可跨团队"},
    )
    assert admin_ok.status_code == 200, admin_ok.text
