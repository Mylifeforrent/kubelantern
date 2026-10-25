"""clusters/providers tag 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.app.deps import get_current_user, get_session, require_permission
from huntai.core.pagination import clamp_page
from huntai.core.security import Principal
from huntai.domains.alerts import repository as alerts_repo
from huntai.domains.alerts import service as provider_service
from huntai.domains.alerts.schemas import (
    ProviderCreateRequest,
    ProviderPage,
    ProviderResponse,
    ProviderUpdateRequest,
)
from huntai.domains.clusters import repository as repo
from huntai.domains.clusters import service
from huntai.domains.clusters.schemas import (
    ClusterCreateRequest,
    ClusterPage,
    ClusterResponse,
    ClusterUpdateRequest,
    ConnectionTestResultResponse,
)

router = APIRouter()


def _cluster_response(c) -> ClusterResponse:
    return ClusterResponse(
        id=c.id, name=c.name, environment=c.environment, api_endpoint=c.api_endpoint,
        status=c.status.value if hasattr(c.status, "value") else c.status,
        k8s_version=c.k8s_version, credential_id=c.credential_id,
        last_checked_at=c.last_checked_at, created_at=c.created_at, updated_at=c.updated_at,
    )


def _provider_response(p) -> ProviderResponse:
    return ProviderResponse(
        id=p.id, name=p.name, type=p.type,
        category=p.category.value if hasattr(p.category, "value") else p.category,
        pull_mode=p.pull_mode.value if hasattr(p.pull_mode, "value") else p.pull_mode,
        config=p.config, credential_id=p.credential_id, fingerprint_fields=p.fingerprint_fields,
        enabled=p.enabled, created_at=p.created_at, updated_at=p.updated_at,
    )


@router.get("/clusters", response_model=ClusterPage, dependencies=[Depends(require_permission("clusters", "read"))])
async def list_clusters(
    environment: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    clusters, total = await repo.list_clusters(
        session, environment=environment, status=status, offset=offset, limit=limit
    )
    return ClusterPage.build(
        [_cluster_response(c) for c in clusters], total=total, offset=offset, limit=limit
    )


@router.post(
    "/clusters",
    response_model=ClusterResponse,
    status_code=201,
    dependencies=[Depends(require_permission("clusters", "write"))],
)
async def create_cluster(
    payload: ClusterCreateRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_user),
):
    return _cluster_response(await service.create_cluster(session, payload, actor_id=principal.user_id))


@router.get("/clusters/{cluster_id}", response_model=ClusterResponse, dependencies=[Depends(require_permission("clusters", "read"))])
async def get_cluster(cluster_id: int, session: AsyncSession = Depends(get_session)):
    cluster = await repo.get_cluster(session, cluster_id)
    if cluster is None:
        from huntai.core.errors import not_found

        raise not_found("clusters", cluster_id)
    return _cluster_response(cluster)


@router.put("/clusters/{cluster_id}", response_model=ClusterResponse, dependencies=[Depends(require_permission("clusters", "write"))])
async def update_cluster(
    cluster_id: int,
    payload: ClusterUpdateRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_user),
):
    return _cluster_response(
        await service.update_cluster(session, cluster_id, payload, actor_id=principal.user_id)
    )


@router.delete("/clusters/{cluster_id}", status_code=204, dependencies=[Depends(require_permission("clusters", "write"))])
async def delete_cluster(
    cluster_id: int,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_user),
):
    await service.delete_cluster(session, cluster_id, actor_id=principal.user_id)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.post(
    "/clusters/{cluster_id}/test-connection",
    response_model=ConnectionTestResultResponse,
    dependencies=[Depends(require_permission("clusters", "test"))],
)
async def test_cluster_connection(
    cluster_id: int,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_user),
):
    from huntai.core.db import utcnow

    result = await service.test_connection(session, cluster_id, actor_id=principal.user_id)
    return ConnectionTestResultResponse(
        status=result.status, k8s_version=result.k8s_version,
        message=result.message, checked_at=utcnow(),
    )


@router.get("/providers", response_model=ProviderPage, dependencies=[Depends(require_permission("providers", "read"))])
async def list_providers(
    category: str | None = None,
    enabled: bool | None = None,
    offset: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    providers, total = await alerts_repo.list_providers(
        session, category=category, enabled=enabled, offset=offset, limit=limit
    )
    return ProviderPage.build(
        [_provider_response(p) for p in providers], total=total, offset=offset, limit=limit
    )


@router.post(
    "/providers",
    response_model=ProviderResponse,
    status_code=201,
    dependencies=[Depends(require_permission("providers", "write"))],
)
async def create_provider(
    payload: ProviderCreateRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_user),
):
    return _provider_response(await provider_service.create_provider(session, payload, actor_id=principal.user_id))


@router.get("/providers/{provider_id}", response_model=ProviderResponse, dependencies=[Depends(require_permission("providers", "read"))])
async def get_provider(provider_id: int, session: AsyncSession = Depends(get_session)):
    provider = await alerts_repo.get_provider(session, provider_id)
    if provider is None:
        from huntai.core.errors import not_found

        raise not_found("providers", provider_id)
    return _provider_response(provider)


@router.put("/providers/{provider_id}", response_model=ProviderResponse, dependencies=[Depends(require_permission("providers", "write"))])
async def update_provider(
    provider_id: int,
    payload: ProviderUpdateRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_user),
):
    return _provider_response(
        await provider_service.update_provider(session, provider_id, payload, actor_id=principal.user_id)
    )


@router.delete("/providers/{provider_id}", status_code=204, dependencies=[Depends(require_permission("providers", "write"))])
async def delete_provider(
    provider_id: int,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_user),
):
    await provider_service.delete_provider(session, provider_id, actor_id=principal.user_id)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
