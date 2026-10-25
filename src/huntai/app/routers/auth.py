"""auth tag：登录换 token、users、roles、users/me（契约草案 + 待回补端点）。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.app.deps import get_current_user, get_session, get_settings, require_permission
from huntai.core.errors import ProblemError, not_found
from huntai.core.pagination import clamp_page
from huntai.core.security import Principal
from huntai.domains.iam import repository as repo
from huntai.domains.iam import service
from huntai.domains.iam.schemas import (
    AuthTokenRequest,
    AuthTokenResponse,
    AuditLogPage,
    AuditLogResponse,
    MeResponse,
    RoleResponse,
    UserCreateRequest,
    UserPage,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(tags=["auth"])


def _user_response(user, grant_rows) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        team=user.team,
        roles=[{"role_code": code, "team_scope": grant.team_scope} for grant, code in grant_rows],
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post("/auth/token", response_model=AuthTokenResponse)
async def issue_token(
    payload: AuthTokenRequest,
    session: AsyncSession = Depends(get_session),
    settings=Depends(get_settings),
):
    access_token, expires_in = await service.issue_token(
        session, username=payload.username, password=payload.password, settings=settings
    )
    return AuthTokenResponse(access_token=access_token, expires_in=expires_in)


@router.get("/users", response_model=UserPage, dependencies=[Depends(require_permission("users", "read"))])
async def list_users(
    team: str | None = None,
    is_active: bool | None = None,
    offset: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    users, total = await repo.list_users(
        session, team=team, is_active=is_active, offset=offset, limit=limit
    )
    items = [_user_response(u, await repo.get_grants(session, u.id)) for u in users]
    return UserPage.build(items, total=total, offset=offset, limit=limit)


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=201,
    dependencies=[Depends(require_permission("users", "write"))],
)
async def create_user(
    payload: UserCreateRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_user),
):
    user = await service.create_user(session, payload, actor_id=principal.user_id)
    return _user_response(user, await repo.get_grants(session, user.id))


@router.get("/users/me", response_model=MeResponse)
async def get_me(principal: Principal = Depends(get_current_user)):
    """契约草案待补端点（前端 session 已消费）；返回当前会话用户。"""
    return MeResponse(
        id=principal.user_id,
        username=principal.username,
        email=principal.email,
        display_name=principal.display_name,
        team=principal.team,
        roles=[{"role_code": g["role_code"], "team_scope": g.get("team_scope")} for g in principal.grants],
        is_active=principal.is_active,
        created_at=principal.created_at,
        updated_at=principal.updated_at,
    )


@router.get("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(require_permission("users", "read"))])
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
):
    user = await repo.get_user(session, user_id)
    if user is None:
        raise not_found("users", user_id)
    return _user_response(user, await repo.get_grants(session, user.id))


@router.put("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(require_permission("users", "write"))])
async def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(get_current_user),
):
    user = await service.update_user(session, user_id, payload, actor_id=principal.user_id)
    return _user_response(user, await repo.get_grants(session, user.id))


@router.get("/roles", response_model=list[RoleResponse], dependencies=[Depends(require_permission("roles", "read"))])
async def list_roles(session: AsyncSession = Depends(get_session)):
    roles = await service.list_roles(session)
    return [
        RoleResponse(
            id=r.id, code=r.code, name=r.name, permissions=r.permissions,
            created_at=r.created_at, updated_at=r.updated_at,
        )
        for r in roles
    ]


def _parse_dt(value: str | None, label: str) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProblemError(status=400, detail=f"{label} 时间格式非法：{value}") from exc


@router.get(
    "/audit-logs",
    response_model=AuditLogPage,
    dependencies=[Depends(require_permission("audit_logs", "read"))],
    tags=["audit"],
)
async def list_audit_logs(
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    actor_user_id: int | None = None,
    created_since: str | None = None,
    created_until: str | None = None,
    offset: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    offset, limit = clamp_page(offset, limit)
    logs, total = await repo.list_audit_logs(
        session,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_user_id=actor_user_id,
        created_since=_parse_dt(created_since, "created_since"),
        created_until=_parse_dt(created_until, "created_until"),
        offset=offset,
        limit=limit,
    )
    items = [
        AuditLogResponse(
            id=l.id,
            actor_user_id=l.actor_user_id,
            actor_type=l.actor_type.value,
            action=l.action,
            resource_type=l.resource_type,
            resource_id=l.resource_id,
            detail=l.detail,
            cost=l.cost,
            ip=l.ip,
            user_agent=l.user_agent,
            created_at=l.created_at,
        )
        for l in logs
    ]
    return AuditLogPage.build(items, total=total, offset=offset, limit=limit)
