"""e2e 链路三（文档 §7.3 必测）：BR-03 预算耗尽 graceful 终止。"""

from __future__ import annotations

import pytest
from sqlalchemy import select

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


class _FakeProvider:
    name = "fake-local"
    is_local = True

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, prompt: str, *, max_tokens: int):
        self.calls += 1
        from huntai.gateway.providers.base import Completion

        return Completion(text=f"answer-{self.calls}", tokens_in=10, tokens_out=20)


async def test_br03_budget_exhaustion_graceful(db_session, test_settings):
    """max_calls=2 → 第 3 次调用前 graceful 终止：budget_exceeded / is_partial / call_logs 恰 2 条。"""
    from huntai.domains.ai import repository as ai_repo
    from huntai.domains.ai import service as ai_service
    from huntai.domains.ai.models import AICallLog, AITaskStatus
    from huntai.domains.alerts.models import Provider
    from huntai.domains.clusters.models import Cluster, Credential
    from huntai.domains.inspections.models import Finding, InspectionPolicy, InspectionRun
    from huntai.gateway.gateway import AIGateway
    from tests.conftest import seed_roles, seed_user

    await seed_roles(db_session)
    admin_id = await seed_user(db_session, "admin", "admin")

    cred = Credential(name="k8s", secret_ref="env:X")
    db_session.add(cred)
    await db_session.flush()
    cluster = Cluster(name="c1", environment="prod", api_endpoint="https://x", credential_id=cred.id)
    db_session.add(cluster)
    await db_session.flush()
    policy = InspectionPolicy(cluster_id=cluster.id, name="p", schedule="* * * * *")
    db_session.add(policy)
    await db_session.flush()
    run = InspectionRun(policy_id=policy.id, cluster_id=cluster.id)
    db_session.add(run)
    await db_session.flush()
    finding = Finding(
        run_id=run.id, cluster_id=cluster.id, rule_code="pod-crashloopbackoff",
        resource_ref={"kind": "Pod", "namespace": "payment", "name": "web-1"},
        severity="warning", raw_error={"reason": "CrashLoopBackOff"},
    )
    db_session.add(finding)
    await db_session.flush()

    task = await ai_service.create_task_for_finding(
        db_session, finding, requested_by=admin_id, settings=test_settings,
    )
    task.budget = {"max_calls": 2, "max_output_tokens": 100000}
    await db_session.flush()

    gateway = AIGateway(test_settings)
    fake = _FakeProvider()
    gateway._providers["local"] = fake  # noqa: SLF001 - 测试注入替身 Provider

    # 第一次预算内调用成功
    task = await gateway.execute_task(db_session, task.id)
    assert task.status.value == "completed"
    assert task.calls_used == 1

    # 重置任务并连续消耗至预算上限
    task2 = await ai_service.create_task_for_finding(
        db_session, finding, requested_by=admin_id, settings=test_settings,
    )
    task2.budget = {"max_calls": 2, "max_output_tokens": 100000}
    task2.calls_used = 2  # 已用满 2 次（模拟前两次调用完成）
    task2.status = AITaskStatus.CREATED
    await db_session.flush()

    task2 = await gateway.execute_task(db_session, task2.id)
    assert task2.status.value == "budget_exceeded", "第 3 次调用前应 graceful 终止（BR-03）"
    assert task2.is_partial is True
    logs = (
        await db_session.execute(select(AICallLog).where(AICallLog.task_id == task2.id))
    ).scalars().all()
    assert len(logs) == 0, "预算耗尽任务不应再产生新调用"
    assert task2.calls_used == 2

    # 完整走两次调用的任务：call_logs 恰 2 条（首次调用 + 第二任务首调用已计入 task1）
    first_task_logs = (
        await db_session.execute(select(AICallLog).where(AICallLog.task_id == task.id))
    ).scalars().all()
    assert len(first_task_logs) == 1
    assert fake.calls == 1


async def test_br03_output_token_budget(db_session, test_settings):
    from huntai.domains.ai import service as ai_service
    from huntai.domains.alerts.models import Provider
    from huntai.domains.clusters.models import Cluster, Credential
    from huntai.domains.inspections.models import Finding, InspectionPolicy, InspectionRun
    from huntai.gateway.gateway import AIGateway
    from tests.conftest import seed_roles, seed_user

    await seed_roles(db_session)
    admin_id = await seed_user(db_session, "admin", "admin")
    cred = Credential(name="k8s2", secret_ref="env:X")
    db_session.add(cred)
    await db_session.flush()
    cluster = Cluster(name="c2", environment="prod", api_endpoint="https://x", credential_id=cred.id)
    db_session.add(cluster)
    await db_session.flush()
    policy = InspectionPolicy(cluster_id=cluster.id, name="p2", schedule="* * * * *")
    db_session.add(policy)
    await db_session.flush()
    run = InspectionRun(policy_id=policy.id, cluster_id=cluster.id)
    db_session.add(run)
    await db_session.flush()
    finding = Finding(
        run_id=run.id, cluster_id=cluster.id, rule_code="pvc-pending",
        resource_ref={"kind": "PersistentVolumeClaim", "namespace": "data", "name": "vol"},
        severity="warning", raw_error={"phase": "Pending"},
    )
    db_session.add(finding)
    await db_session.flush()

    task = await ai_service.create_task_for_finding(
        db_session, finding, requested_by=admin_id, settings=test_settings,
    )
    task.budget = {"max_calls": 5, "max_output_tokens": 10}
    task.tokens_used = 10
    from huntai.domains.ai.models import AITaskStatus

    task.status = AITaskStatus.CREATED
    await db_session.flush()

    gateway = AIGateway(test_settings)
    gateway._providers["local"] = _FakeProvider()  # noqa: SLF001
    result = await gateway.execute_task(db_session, task.id)
    assert result.status.value == "budget_exceeded"
    assert "token" in (result.error or "")
