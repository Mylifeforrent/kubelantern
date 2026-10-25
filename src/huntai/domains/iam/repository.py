"""IAM 数据访问（纯查询，无业务规则）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.pagination import paginate
from huntai.domains.iam.models import AuditLog, Role, User, UserRoleGrant


async def list_users(
    session: AsyncSession,
    *,
    team: str | None = None,
    is_active: bool | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[User], int]:
    stmt = select(User).order_by(User.id)
    if team is not None:
        stmt = stmt.where(User.team == team)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    return (await session.execute(select(User).where(User.username == username))).scalar_one_or_none()


async def get_grants(session: AsyncSession, user_id: int) -> list[tuple[UserRoleGrant, str]]:
    """返回 (授予行, role_code) 列表（路由序列化需要角色代码）。"""
    rows = await session.execute(
        select(UserRoleGrant, Role.code)
        .join(Role, Role.id == UserRoleGrant.role_id)
        .where(UserRoleGrant.user_id == user_id)
    )
    return [(grant, code) for grant, code in rows.all()]


async def list_roles(session: AsyncSession) -> list[Role]:
    rows = await session.execute(select(Role).order_by(Role.id))
    return list(rows.scalars().all())


async def get_role_by_code(session: AsyncSession, code: str) -> Role | None:
    return (await session.execute(select(Role).where(Role.code == code))).scalar_one_or_none()


async def username_exists(session: AsyncSession, username: str) -> bool:
    count = (
        await session.execute(select(func.count()).select_from(User).where(User.username == username))
    ).scalar_one()
    return count > 0


async def email_exists(session: AsyncSession, email: str) -> bool:
    count = (
        await session.execute(select(func.count()).select_from(User).where(User.email == email))
    ).scalar_one()
    return count > 0


async def list_audit_logs(
    session: AsyncSession,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    actor_user_id: int | None = None,
    created_since: datetime | None = None,
    created_until: datetime | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[AuditLog], int]:
    stmt = select(AuditLog).order_by(AuditLog.id.desc())
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type is not None:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if resource_id is not None:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if created_since is not None:
        stmt = stmt.where(AuditLog.created_at >= created_since)
    if created_until is not None:
        stmt = stmt.where(AuditLog.created_at <= created_until)
    count_stmt, page_stmt = paginate(stmt, offset=offset, limit=limit)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total
