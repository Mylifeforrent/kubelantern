"""集群接入域 service：集群/Provider CRUD、探活与连接测试、快照拉取（跨域公开接口）。"""

from __future__ import annotations

from huntai.core.db import utcnow
from huntai.core.errors import ProblemError, not_found
from huntai.domains.clusters import connector, repository as repo
from huntai.domains.clusters.models import Cluster
from huntai.domains.clusters.schemas import (
    ClusterCreateRequest,
    ClusterUpdateRequest,
)
from huntai.domains.iam.service import record_audit
from sqlalchemy.ext.asyncio import AsyncSession


async def create_cluster(session: AsyncSession, payload: ClusterCreateRequest, *, actor_id: int) -> Cluster:
    cred = await repo.get_credential(session, payload.credential_id)
    if cred is None:
        raise ProblemError(status=400, detail=f"凭证引用不存在：{payload.credential_id}")
    if await repo.name_exists(session, payload.name):
        raise ProblemError(status=409, code="CLUSTER_CONFLICT", detail=f"集群名已存在：{payload.name}")
    cluster = Cluster(
        name=payload.name,
        environment=payload.environment,
        api_endpoint=payload.api_endpoint,
        credential_id=payload.credential_id,
    )
    session.add(cluster)
    await session.flush()
    await record_audit(
        session,
        action="cluster.create",
        resource_type="clusters",
        resource_id=cluster.id,
        detail={"name": cluster.name, "environment": cluster.environment},
        actor_id=actor_id,
    )
    return cluster


async def update_cluster(
    session: AsyncSession, cluster_id: int, payload: ClusterUpdateRequest, *, actor_id: int
) -> Cluster:
    cluster = await repo.get_cluster(session, cluster_id)
    if cluster is None:
        raise not_found("clusters", cluster_id)
    changes: dict = {}
    if payload.name is not None and payload.name != cluster.name:
        if await repo.name_exists(session, payload.name):
            raise ProblemError(status=409, code="CLUSTER_CONFLICT", detail=f"集群名已存在：{payload.name}")
        cluster.name = payload.name
        changes["name"] = payload.name
    if payload.environment is not None:
        cluster.environment = payload.environment
        changes["environment"] = payload.environment
    if payload.api_endpoint is not None:
        cluster.api_endpoint = payload.api_endpoint
        changes["api_endpoint"] = payload.api_endpoint
    if payload.credential_id is not None:
        if await repo.get_credential(session, payload.credential_id) is None:
            raise ProblemError(status=400, detail=f"凭证引用不存在：{payload.credential_id}")
        cluster.credential_id = payload.credential_id
        changes["credential_id"] = payload.credential_id
    await record_audit(
        session, action="cluster.update", resource_type="clusters", resource_id=cluster.id,
        detail=changes, actor_id=actor_id,
    )
    return cluster


async def delete_cluster(session: AsyncSession, cluster_id: int, *, actor_id: int) -> None:
    cluster = await repo.get_cluster(session, cluster_id)
    if cluster is None:
        raise not_found("clusters", cluster_id)
    cluster.deleted_at = utcnow()  # 软删（D-7）
    await record_audit(
        session, action="cluster.delete", resource_type="clusters", resource_id=cluster.id,
        detail={"name": cluster.name}, actor_id=actor_id,
    )


async def test_connection(session: AsyncSession, cluster_id: int, *, actor_id: int) -> connector.ProbeResult:
    """立即探活并回写 status/k8s_version/last_checked_at（04-backend-design §3.8）。"""
    cluster = await repo.get_cluster(session, cluster_id)
    if cluster is None:
        raise not_found("clusters", cluster_id)
    cred = await repo.get_credential(session, cluster.credential_id)
    if cred is None:
        raise ProblemError(status=500, detail=f"集群 {cluster_id} 的凭证引用缺失")
    result = await connector.probe(cluster, cred)
    cluster.status = result.status
    cluster.k8s_version = result.k8s_version
    cluster.last_checked_at = utcnow()
    await record_audit(
        session, action="cluster.test_connection", resource_type="clusters", resource_id=cluster.id,
        detail={"status": result.status}, actor_id=actor_id,
    )
    return result


async def get_snapshot(session: AsyncSession, cluster_id: int) -> dict:
    """巡检 worker 用：拉取只读快照（跨域公开接口）。"""
    cluster = await repo.get_cluster(session, cluster_id)
    if cluster is None:
        raise not_found("clusters", cluster_id)
    cred = await repo.get_credential(session, cluster.credential_id)
    if cred is None:
        raise ProblemError(status=500, detail=f"集群 {cluster_id} 的凭证引用缺失")
    return await connector.fetch_snapshot(cluster, cred)
