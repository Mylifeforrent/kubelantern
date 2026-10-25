"""集成测试：迁移产物（D-1/D-6/D-10/枚举 CHECK/索引）。"""

from __future__ import annotations

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_migration_indexes_and_constraints(db_session):
    checks = {
        "uk_alerts_active_fingerprint": "partial unique（D-1）",
        "idx_alerts_labels": "GIN（D-3）",
        "uk_findings_run_rule_resource": "业务键唯一（D-5）",
        "uk_workflows_current": "部分唯一索引",
    }
    rows = (
        await db_session.execute(
            text("SELECT indexname FROM pg_indexes WHERE schemaname='public'")
        )
    ).scalars().all()
    for index_name in checks:
        assert index_name in rows, f"缺少索引 {index_name}（{checks[index_name]}）"


async def test_d6_revoke_no_update_delete_grants(db_session):
    """audit_logs/ai_call_logs/notification_records 无 UPDATE/DELETE 授权行（D-6）。

    注：表 owner 天然持有全权（PG 语义）；生产以「迁移角色 ≠ 应用角色」落地（[TBD-INFRA]）。
    """
    for table in ("audit_logs", "ai_call_logs", "notification_records"):
        count = (
            await db_session.execute(
                text(
                    "SELECT count(*) FROM information_schema.table_privileges"
                    " WHERE table_name = :t AND grantee = current_user"
                    " AND privilege_type IN ('UPDATE','DELETE')"
                ),
                {"t": table},
            )
        ).scalar_one()
        assert count == 0, f"{table} 不应有 UPDATE/DELETE 授权"


async def test_d10_check_constraints_enforced(db_session):
    from huntai.core.db import utcnow
    from huntai.domains.inspections.models import Finding, InspectionPolicy, InspectionRun
    from huntai.domains.clusters.models import Cluster, Credential
    from sqlalchemy.exc import IntegrityError

    async def _base_rows(tag: str):
        cred = Credential(name=f"c-{tag}", secret_ref="env:X")
        db_session.add(cred)
        await db_session.flush()
        cluster = Cluster(name=f"chk-{tag}", environment="prod", api_endpoint="https://x", credential_id=cred.id)
        db_session.add(cluster)
        await db_session.flush()
        policy = InspectionPolicy(cluster_id=cluster.id, name=f"p-{tag}", schedule="* * * * *")
        db_session.add(policy)
        await db_session.flush()
        run = InspectionRun(policy_id=policy.id, cluster_id=cluster.id)
        db_session.add(run)
        await db_session.flush()
        return cluster, run

    # D-10：ignored 必填原因 → 违反 CHECK 报错
    cluster, run = await _base_rows("a")
    finding = Finding(
        run_id=run.id, cluster_id=cluster.id, rule_code="x",
        resource_ref={"kind": "Pod", "namespace": "default", "name": "p"},
        severity="warning", raw_error={}, status="ignored",  # 缺 ignored_reason
    )
    db_session.add(finding)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()  # 回滚连同父行，第二场景重建

    # 枚举 CHECK：绕过 ORM 枚举校验，直测库层约束
    cluster, run = await _base_rows("b")
    from sqlalchemy import text

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO findings (run_id, cluster_id, rule_code, resource_ref, severity,"
                " raw_error, status) VALUES (:r, :c, 'x', '{\"kind\":\"Pod\"}'::jsonb,"
                " 'warning', '{}'::jsonb, 'not-a-state')"
            ),
            {"r": run.id, "c": cluster.id},
        )
    await db_session.rollback()
