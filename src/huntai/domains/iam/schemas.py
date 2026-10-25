"""IAM DTO（契约 auth tag：AuthToken/User/Role/AuditLog）。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from huntai.core.schemas import BaseSchema, Page, UtcDateTime

# 契约 format: email；不引 email-validator（未在冻结依赖清单），以正则表达同等约束
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class AuthTokenRequest(BaseSchema):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthTokenResponse(BaseSchema):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserRoleGrantResponse(BaseSchema):
    role_code: str
    team_scope: str | None = None


class UserResponse(BaseSchema):
    id: int
    username: str
    email: str
    display_name: str
    team: str | None = None
    roles: list[UserRoleGrantResponse] = []
    is_active: bool
    created_at: UtcDateTime
    updated_at: UtcDateTime


class UserCreateRequest(BaseSchema):
    username: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=_EMAIL_PATTERN)
    display_name: str = Field(min_length=1, max_length=200)
    team: str | None = None
    roles: list[UserRoleGrantResponse] = []


class UserUpdateRequest(BaseSchema):
    model_config = dict(BaseSchema.model_config, extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    team: str | None = None
    roles: list[UserRoleGrantResponse] | None = None
    is_active: bool | None = None


class RoleResponse(BaseSchema):
    id: int
    code: str
    name: str
    permissions: dict[str, Any]
    created_at: UtcDateTime
    updated_at: UtcDateTime


class AuditLogResponse(BaseSchema):
    id: int
    actor_user_id: int | None = None
    actor_type: str
    action: str
    resource_type: str
    resource_id: str
    detail: dict[str, Any]
    cost: dict[str, Any] | None = None
    ip: str | None = None
    user_agent: str | None = None
    created_at: UtcDateTime


class UserPage(Page[UserResponse]):
    pass


class AuditLogPage(Page[AuditLogResponse]):
    pass


class MeResponse(UserResponse):
    """契约草案待补端点 GET /users/me 的响应（沿用 User 形态）。"""
