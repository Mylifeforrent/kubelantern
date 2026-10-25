"""IAM service：用户/角色管理与审计写入（审计与业务变更同事务，04-backend-design §6.2）。"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core import context
from huntai.core.config import Settings
from huntai.core.errors import ProblemError
from huntai.core.security import create_token
from huntai.domains.iam import repository as repo
from huntai.domains.iam.models import AuditLog, Role, User, UserRoleGrant
from huntai.domains.iam.permissions import ROLE_NAMES, ROLE_PERMISSIONS
from huntai.domains.iam.schemas import UserCreateRequest, UserUpdateRequest


async def issue_token(
    session: AsyncSession, *, username: str, password: str, settings: Settings
) -> tuple[str, int]:
    """dev 占位认证（[TBD-INFRA]）：用户存在且启用、口令匹配 HUNTAI_DEV_AUTH_PASSWORD。"""
    user = await repo.get_user_by_username(session, username)
    if user is None or not user.is_active:
        raise ProblemError(status=401, detail="用户不存在或已停用")
    if password != settings.dev_auth_password:
        raise ProblemError(status=401, detail="口令错误")
    token, expires_at = create_token(
        user.id, secret=settings.auth_secret, ttl_minutes=settings.auth_token_ttl_minutes
    )
    return token, max(0, expires_at - int(time.time()))


async def create_user(
    session: AsyncSession, payload: UserCreateRequest, *, actor_id: int | None
) -> User:
    if await repo.username_exists(session, payload.username):
        raise ProblemError(status=409, code="USER_CONFLICT", detail=f"用户名已存在：{payload.username}")
    if await repo.email_exists(session, str(payload.email)):
        raise ProblemError(status=409, code="USER_CONFLICT", detail=f"邮箱已存在：{payload.email}")
    user = User(
        username=payload.username,
        email=str(payload.email),
        display_name=payload.display_name,
        team=payload.team,
    )
    session.add(user)
    await session.flush()
    await _apply_grants(session, user.id, payload.roles)
    await record_audit(
        session,
        action="user.create",
        resource_type="users",
        resource_id=str(user.id),
        detail={"username": user.username, "roles": [g.role_code for g in payload.roles]},
    )
    return user


async def update_user(
    session: AsyncSession, user_id: int, payload: UserUpdateRequest, *, actor_id: int | None
) -> User:
    user = await repo.get_user(session, user_id)
    if user is None:
        raise ProblemError(status=404, detail=f"users {user_id} not found")
    changes: dict[str, Any] = {}
    if payload.display_name is not None:
        user.display_name = payload.display_name
        changes["display_name"] = payload.display_name
    if payload.team is not None:
        user.team = payload.team
        changes["team"] = payload.team
    if payload.is_active is not None:
        user.is_active = payload.is_active
        changes["is_active"] = payload.is_active
    if payload.roles is not None:
        for grant in await repo.get_grants(session, user.id):
            await session.delete(grant)
        await session.flush()
        await _apply_grants(session, user.id, payload.roles)
        changes["roles"] = [g.role_code for g in payload.roles]
    await record_audit(
        session,
        action="user.update",
        resource_type="users",
        resource_id=str(user.id),
        detail=changes,
    )
    return user


async def _apply_grants(session: AsyncSession, user_id: int, grants) -> None:
    for grant in grants:
        role = await repo.get_role_by_code(session, grant.role_code)
        if role is None:
            raise ProblemError(status=400, detail=f"未知角色：{grant.role_code}")
        session.add(
            UserRoleGrant(
                user_id=user_id, role_id=role.id, team_scope=grant.team_scope, granted_by=None
            )
        )
    await session.flush()


async def list_roles(session: AsyncSession) -> list[Role]:
    return await repo.list_roles(session)


async def record_audit(
    session: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: str | int,
    detail: dict[str, Any] | None = None,
    cost: dict[str, Any] | None = None,
    actor_id: int | None = None,
    actor_type: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """全模块共用审计写入；只追加（D-6），detail 排除凭据字段。"""
    log = AuditLog(
        actor_user_id=actor_id if actor_id is not None else context.actor_id.get(),
        actor_type=actor_type or context.actor_type.get(),
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        detail=detail or {},
        cost=cost,
        ip=ip,
        user_agent=user_agent,
    )
    session.add(log)
    return log


def seed_role_rows() -> list[dict]:
    """角色 + 权限矩阵 seed 行（供 seed 脚本/测试建库）。"""
    return [
        {"code": code, "name": ROLE_NAMES[code], "permissions": matrix}
        for code, matrix in sorted(ROLE_PERMISSIONS.items())
    ]
