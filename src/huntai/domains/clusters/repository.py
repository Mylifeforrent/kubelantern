"""集群/Provider 数据访问。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.pagination import paginate
from huntai.domains.clusters.models import Cluster, Credential


async def list_clusters(
    session: AsyncSession,
    *,
    environment: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Cluster], int]:
    stmt = select(Cluster).where(Cluster.deleted_at.is_(None)).order_by(Cluster.id)
    if environment is not None:
        stmt = stmt.where(Cluster.environment == environment)
    if status is not None:
        stmt = stmt.where(Cluster.status == status)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def get_cluster(session: AsyncSession, cluster_id: int) -> Cluster | None:
    cluster = await session.get(Cluster, cluster_id)
    if cluster is not None and cluster.deleted_at is not None:
        return None  # 软删（D-7）对外不可见
    return cluster


async def name_exists(session: AsyncSession, name: str) -> bool:
    row = await session.execute(
        select(Cluster.id).where(Cluster.name == name, Cluster.deleted_at.is_(None))
    )
    return row.scalar_one_or_none() is not None


async def get_credential(session: AsyncSession, credential_id: int) -> Credential | None:
    return await session.get(Credential, credential_id)
