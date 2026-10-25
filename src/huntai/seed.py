"""E2E/演示 seed（E2E seed 责任归后端，05-fe-be-boundary §3.2）。

用法：uv run python -m huntai.seed [--with-alerts]
造数：角色权限矩阵、admin/sre/oncall_manager/developer/viewer 演进用户、演示凭证引用与集群、
内置巡检 Provider 与规则、富化规则；--with-alerts 时经 ingest 服务投递若干演示告警
（保证「告警状态经管道推进」的业务正确性，不经直写 DB）。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os

from huntai.core.config import Settings
from huntai.core.db import create_engine_and_sessionmaker
from huntai.core.logging import setup_logging
from huntai.domains.alerts import service as alerts_service
from huntai.domains.clusters.models import Credential
from huntai.domains.iam.models import Role, User, UserRoleGrant
from huntai.domains.iam.permissions import ROLE_NAMES, ROLE_PERMISSIONS
from huntai.domains.iam.service import record_audit
from huntai.domains.inspections.analyzers import BUILTIN_ANALYZERS

logger = logging.getLogger("huntai.seed")

DEMO_USERS = [
    ("admin", "管理员", "admin"),
    ("sre-tony", "Tony（SRE）", "sre"),
    ("oncall-may", "May（值班经理）", "oncall_manager"),
    ("dev-lee", "Lee（研发·平台组）", "developer"),
    ("viewer-guest", "访客", "viewer"),
]

DEMO_INSPECTION_RULES = [
    ("pod-crashloopbackoff", "Pod 崩溃循环", "pod", "critical"),
    ("pod-imagepullbackoff", "镜像拉取失败", "pod", "critical"),
    ("pod-pending", "Pod 调度失败", "pod", "warning"),
    ("pod-high-restarts", "容器高频重启", "pod", "warning"),
    ("pvc-pending", "PVC 未绑定", "pvc", "warning"),
    ("deployment-replicas-mismatch", "副本数不一致", "deployment", "warning"),
    ("node-pressure", "节点资源压力", "node", "warning"),
]

DEMO_ALERTS = [
    {
        "title": "API 网关 5xx 激增",
        "severity": "critical",
        "labels": {"alertname": "ApiGateway5xxHigh", "namespace": "api-gateway", "team": "platform", "env": "prod"},
        "status": "firing",
    },
    {
        "title": "数据库连接池耗尽",
        "severity": "warning",
        "labels": {"alertname": "DbConnPoolExhausted", "namespace": "order-service", "team": "order", "env": "prod"},
        "status": "firing",
    },
    {
        "title": "节点磁盘水位高",
        "severity": "warning",
        "labels": {"alertname": "NodeDiskHigh", "cluster": "prod-cn", "team": "infra", "env": "prod"},
        "status": "firing",
    },
]


async def seed(with_alerts: bool = False) -> None:
    settings = Settings()
    setup_logging(settings.log_level, settings.log_format)
    _engine, sessionmaker = create_engine_and_sessionmaker(settings.database_url)
    async with sessionmaker() as session:
        # 角色 + 权限矩阵
        for code, name in ROLE_NAMES.items():
            role = (
                await session.execute(
                    Role.__table__.select().where(Role.code == code)
                )
            ).first()
            if role is None:
                session.add(Role(code=code, name=name, permissions=ROLE_PERMISSIONS[code]))
        await session.flush()

        # 演示用户（密码走 dev 占位认证 HUNTAI_DEV_AUTH_PASSWORD）
        from sqlalchemy import select

        admin_id: int | None = None
        for username, display_name, role_code in DEMO_USERS:
            exists = (
                await session.execute(select(User.id).where(User.username == username))
            ).scalar_one_or_none()
            if exists is not None:
                if username == "admin":
                    admin_id = exists
                continue
            user = User(
                username=username,
                email=f"{username}@huntai.example",
                display_name=display_name,
                team="platform" if role_code in {"developer"} else None,
            )
            session.add(user)
            await session.flush()
            role_row = (
                await session.execute(select(Role).where(Role.code == role_code))
            ).scalar_one()
            session.add(UserRoleGrant(user_id=user.id, role_id=role_row.id, team_scope="platform" if role_code == "developer" else None))
            if username == "admin":
                admin_id = user.id
        await session.flush()

        # 演示凭证引用（secret_ref 指向 env: 占位；值不入库 D-2）
        cred = (
            await session.execute(select(Credential).where(Credential.name == "demo-cluster-readonly"))
        ).scalar_one_or_none()
        if cred is None:
            cred = Credential(name="demo-cluster-readonly", secret_ref="env:HUNTAI_DEMO_CLUSTER_TOKEN")
            session.add(cred)
            await session.flush()

        # 演示集群（探活前状态 unknown）
        from huntai.domains.clusters.models import Cluster

        cluster = (
            await session.execute(select(Cluster).where(Cluster.name == "demo-prod"))
        ).scalar_one_or_none()
        if cluster is None:
            session.add(
                Cluster(
                    name="demo-prod", environment="prod",
                    api_endpoint="https://kubernetes.default.svc", credential_id=cred.id,
                )
            )

        # 内置巡检 Provider（BR-09 转告警入口）
        from huntai.domains.alerts.models import Provider

        provider = (
            await session.execute(select(Provider).where(Provider.name == "huntai-inspection"))
        ).scalar_one_or_none()
        if provider is None:
            session.add(Provider(name="huntai-inspection", type="huntai", category="source", pull_mode="poll"))
        demo_provider = (
            await session.execute(select(Provider).where(Provider.name == "demo-alertmanager"))
        ).scalar_one_or_none()
        if demo_provider is None:
            session.add(
                Provider(
                    name="demo-alertmanager", type="alertmanager", category="source",
                    pull_mode="push", fingerprint_fields=["alertname", "namespace", "cluster"],
                )
            )
        await session.flush()

        # 内置巡检规则（code ↔ BUILTIN_ANALYZERS 对齐）
        from huntai.domains.inspections.models import InspectionRule

        for code, name, category, severity in DEMO_INSPECTION_RULES:
            exists = (
                await session.execute(select(InspectionRule.id).where(InspectionRule.code == code))
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    InspectionRule(
                        code=code, name=name, category=category,
                        severity_default=severity, k8s_version_fit=">=1.20",
                        description=f"内置规则 {name}（k8sgpt 移植）",
                    )
                )

        # 演示富化规则：namespace 前缀映射团队
        from huntai.domains.alerts.models import EnrichmentRule

        enrichment = (
            await session.execute(select(EnrichmentRule.id).where(EnrichmentRule.name == "namespace-to-team"))
        ).scalar_one_or_none()
        if enrichment is None:
            session.add(
                EnrichmentRule(
                    name="namespace-to-team",
                    matchers=[{"field": "namespace", "operator": "exists"}],
                    mappings=[{"type": "extraction", "source": "team", "target": "team"}],
                    priority=10,
                )
            )

        if admin_id is not None:
            await record_audit(
                session, action="seed.run", resource_type="system", resource_id="seed",
                detail={"with_alerts": with_alerts}, actor_id=admin_id,
            )
        await session.commit()

        if with_alerts:
            provider_row = (
                await session.execute(select(Provider).where(Provider.name == "demo-alertmanager"))
            ).scalar_one()
            async def _no_enqueue(*args, **kwargs):
                return None

            for payload in DEMO_ALERTS:
                alert_id, merged = await alerts_service.ingest(
                    session, provider=provider_row, payload=payload, enqueue=_no_enqueue
                )
                logger.info(
                    "demo alert ingested",
                    extra={"props": {"resource": f"alerts:{alert_id}", "merged": merged}},
                )
            await session.commit()

    await _engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="后端 seed：角色/用户/演示配置（E2E 造数入口）")
    parser.add_argument("--with-alerts", action="store_true", help="投递演示告警（经 ingest 服务）")
    args = parser.parse_args()
    asyncio.run(seed(with_alerts=args.with_alerts))
    print("seed 完成")


if __name__ == "__main__":
    os.environ.setdefault("HUNTAI_ENV", "dev")
    main()
