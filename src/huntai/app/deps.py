"""请求级依赖：session、认证主体、权限工厂、arq 池。

事务边界：API 每请求一个事务（成功 commit、异常 rollback，04-backend-design §1.5）。
资源经 request.app.state 注入，禁止模块级全局单例。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.errors import ProblemError
from huntai.core.security import Principal, TeamScope


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """请求级事务：成功提交、异常回滚。

    写请求的提前提交由 TransactionalAPIRoute 在响应发送前完成（见 app/routing.py），
    这里处理兜底提交/回滚与连接释放。
    """
    session = request.app.state.sessionmaker()
    request.state.db_session = session
    try:
        yield session
        if not getattr(request.state, "db_session_committed", False):
            await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        request.state.db_session = None
        await session.close()


def get_settings(request: Request):
    return request.app.state.settings


def get_arq_pool(request: Request):
    return request.app.state.arq_pool


async def get_current_user(request: Request) -> Principal:
    """认证入口：解析 bearer 并加载主体（认证实现收敛点，[TBD-INFRA]）。"""
    from huntai.core.security import get_principal as _load

    principal = getattr(request.state, "principal", None)
    if principal is None:
        header_value = request.headers.get("Authorization", "")
        if not header_value.startswith("Bearer "):
            raise ProblemError(status=401, detail="缺少 Bearer 凭据")
        bearer_value = header_value.removeprefix("Bearer ").strip()
        app_settings = request.app.state.settings
        principal = await _load(
            request.app.state.sessionmaker, bearer_value, app_settings.auth_secret
        )
        request.state.principal = principal
    return principal


def require_permission(resource: str, action: str):
    """权限依赖工厂：读 roles.permissions 判定 Y/N/T；N → 403。

    返回 TeamScope | None：T 时为限本团队过滤条件，Y 时为 None（全量）。
    """

    async def _dependency(
        principal: Principal = Depends(get_current_user),
    ) -> TeamScope | None:
        priv = principal.can(resource, action)
        if priv == "N":
            raise ProblemError(
                status=403,
                detail=f"角色 {principal.roles} 无 {resource}.{action} 权限",
            )
        if priv == "T":
            team = principal.team_scope_for(resource, action)
            if team is None:
                raise ProblemError(
                    status=403,
                    detail=f"{resource}.{action} 为限本团队权限，但用户未配置 team_scope",
                )
            return TeamScope(team=team)
        return None

    return _dependency


def resolve_team_scope(scope: TeamScope | None = None) -> TeamScope | None:
    """行级过滤直通依赖（与 require_permission 返回值联用）。"""
    return scope
