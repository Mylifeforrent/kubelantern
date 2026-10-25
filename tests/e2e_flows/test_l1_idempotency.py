"""e2e 链路一（文档 §7.3 必测）：L1 幂等。"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.conftest import seed_roles

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def _noop_enqueue(job_name, *args, **kwargs):
    return None


async def _provider(db_session):
    from huntai.domains.alerts.models import Provider

    provider = Provider(
        name="am-test", type="alertmanager", category="source", pull_mode="push",
        fingerprint_fields=["alertname", "namespace"],
    )
    db_session.add(provider)
    await db_session.flush()
    return provider


_PAYLOAD = {
    "status": "firing",
    "labels": {"alertname": "HighErrorRate", "namespace": "api", "severity": "critical"},
}


async def test_l1_dedup_upsert_idempotent(db_session):
    """同 fingerprint 活跃告警重复上报 N 次 → 恰 1 行、occurrence_count=N、仅入队一次。"""
    from huntai.domains.alerts import repository as repo
    from huntai.domains.alerts import service

    provider = await _provider(db_session)
    enqueued: list = []

    async def enqueue(job_name, *args, **kwargs):
        enqueued.append((job_name, args))

    alert_ids = set()
    for _ in range(5):
        alert_id, _merged = await service.ingest(
            db_session, provider=provider, payload=_PAYLOAD, enqueue=enqueue
        )
        alert_ids.add(alert_id)
    assert len(alert_ids) == 1, "重复上报应合并为同一行"
    alert = await repo.get_alert(db_session, alert_ids.pop())
    assert alert.occurrence_count == 5
    assert alert.status.value == "received"
    assert enqueued.count(("alert.process_pipeline", (alert.id,))) == 1


async def test_l1_resolved_then_recurrence_creates_new_row(db_session):
    from huntai.domains.alerts import service
    from huntai.domains.alerts.models import Alert, AlertStatus

    provider = await _provider(db_session)
    first_id, _merged = await service.ingest(
        db_session, provider=provider, payload=_PAYLOAD, enqueue=_noop_enqueue
    )
    alert = await db_session.get(Alert, first_id)
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = alert.last_occurred_at
    await db_session.flush()

    second_payload = dict(_PAYLOAD, labels=dict(_PAYLOAD["labels"], severity="warning"))
    second_id, merged = await service.ingest(
        db_session, provider=provider, payload=second_payload, enqueue=_noop_enqueue
    )
    assert second_id != first_id, "resolved 后同指纹再现应产生新行（D-1）"
    assert merged is False


async def test_l1_pipeline_gate_idempotent(db_session):
    """重复投递管道任务无副作用：门闩保证二次处理直接返回。"""
    from tests.conftest import capture_publish

    from huntai.domains.alerts import repository as repo
    from huntai.domains.alerts import service

    await seed_roles(db_session)
    provider = await _provider(db_session)
    events: list = []
    alert_id, _merged = await service.ingest(
        db_session, provider=provider, payload=_PAYLOAD, enqueue=_noop_enqueue
    )
    await service.process_pipeline(db_session, alert_id, publish=capture_publish(events))
    first = await repo.get_alert(db_session, alert_id)
    assert first.status.value == "notified"  # 无关联规则/窗口 → standalone → 已通知（管道末段）

    await service.process_pipeline(db_session, alert_id, publish=capture_publish(events))
    again = await repo.get_alert(db_session, alert_id)
    assert again.status.value == "notified", "重复消费不应推进状态"


async def test_l1_replay_resubmits_stale_received(db_session):
    from huntai.domains.alerts import service

    provider = await _provider(db_session)
    enqueued: list = []

    async def enqueue(job_name, *args, **kwargs):
        enqueued.append((job_name, args))

    alert_id, _merged = await service.ingest(
        db_session, provider=provider, payload=_PAYLOAD, enqueue=enqueue
    )
    # 人为积压：updated_at 回拨超过 stale 阈值
    await db_session.execute(
        text("UPDATE alerts SET updated_at = now() - interval '120 seconds' WHERE id = :i"),
        {"i": alert_id},
    )
    count = await service.replay_scan(db_session, stale_seconds=60, enqueue=enqueue)
    assert count == 1
    assert enqueued[-1] == ("alert.process_pipeline", (alert_id,))
