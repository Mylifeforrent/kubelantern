"""认证与权限抽象（04-backend-design §4.2）。

- 认证实现为 dev 占位（[TBD-INFRA]：SSO/LDAP/本地定稿后只改本文件），service 层不感知具体机制。
- 权限读 roles.permissions JSONB（Y 允许 / N 拒绝 / T 限本团队），多角色合并取最高（Y > T > N）。
- T = 行级过滤：TeamScope(team=...)，由 service 查询自动附加团队条件。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from huntai.core.errors import ProblemError

ROLE_ADMIN = "admin"
ROLE_SRE = "sre"
ROLE_ONCALL_MANAGER = "oncall_manager"
ROLE_DEVELOPER = "developer"
ROLE_VIEWER = "viewer"

_PRIV_ORDER = {"N": 0, "T": 1, "Y": 2}


@dataclass
class TeamScope:
    """T 列行级过滤：仅返回该团队（或无团队归属）的数据。"""

    team: str


@dataclass
class Principal:
    """已认证主体：用户 + 合并后的权限矩阵 + 授予层带的 team_scope。"""

    user_id: int
    username: str
    email: str
    display_name: str
    team: str | None
    is_active: bool
    created_at: object
    updated_at: object
    roles: list[str]
    grants: list[dict]  # [{role_code, team_scope}]
    permissions: dict[str, dict[str, str]]

    def can(self, resource: str, action: str) -> str:
        actions = self.permissions.get(resource, {})
        return actions.get(action, "N")

    def team_scope_for(self, resource: str, action: str) -> str | None:
        if self.can(resource, action) != "T":
            return None
        for grant in self.grants:
            if grant.get("team_scope"):
                return grant["team_scope"]
        return self.team


# ---------- token：HMAC 签名不透明 bearer（dev 占位，[TBD-INFRA]） ----------


def _sign(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def create_token(user_id: int, *, secret: str, ttl_minutes: int) -> tuple[str, int]:
    expires_at = int(time.time()) + ttl_minutes * 60
    payload = json.dumps({"uid": user_id, "exp": expires_at}, separators=(",", ":")).encode()
    body = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{body}.{_sign(payload, secret)}", expires_at


def parse_token(token: str, *, secret: str) -> int:
    try:
        body, sig = token.rsplit(".", 1)
        payload = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
    except ValueError as exc:
        raise ProblemError(status=401, detail="malformed token") from exc
    if not hmac.compare_digest(_sign(payload, secret), sig):
        raise ProblemError(status=401, detail="invalid token signature")
    data = json.loads(payload)
    if data.get("exp", 0) < time.time():
        raise ProblemError(status=401, detail="token expired")
    uid = data.get("uid")
    if not isinstance(uid, int):
        raise ProblemError(status=401, detail="invalid token payload")
    return uid


# ---------- 权限计算 ----------


def merge_permissions(role_permissions: list[dict]) -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for matrix in role_permissions:
        for resource, actions in matrix.items():
            target = merged.setdefault(resource, {})
            for action, value in actions.items():
                if _PRIV_ORDER.get(value, 0) > _PRIV_ORDER.get(target.get(action, "N"), 0):
                    target[action] = value
    return merged


def load_principal(session: AsyncSession, user_id: int) -> Principal:
    """同步加载主体（查询小、单次往返）；供依赖与 worker 共用。"""
    from huntai.domains.iam.models import Role, User, UserRoleGrant

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise ProblemError(status=401, detail="user inactive or not found")
    rows = session.execute(
        select(Role, UserRoleGrant)
        .join(UserRoleGrant, UserRoleGrant.role_id == Role.id)
        .where(UserRoleGrant.user_id == user_id)
    ).all()
    grants = [
        {"role_code": role.code, "team_scope": grant.team_scope} for role, grant in rows
    ]
    permissions = merge_permissions([role.permissions for role, _ in rows])
    return Principal(
        user_id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        team=user.team,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=sorted({role.code for role, _ in rows}),
        grants=grants,
        permissions=permissions,
    )


async def get_principal(sessionmaker: async_sessionmaker, token: str, secret: str) -> Principal:
    user_id = parse_token(token, secret=secret)
    async with sessionmaker() as session:
        return await session.run_sync(load_principal, user_id)
