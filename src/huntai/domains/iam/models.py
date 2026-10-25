"""身份与审计域：users / roles / user_roles / audit_logs（01-data-model §2.2）。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, JSON, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from huntai.core.db import Base, utcnow
from huntai.domains.bases import created_col, enum_col, id_pk, updated_col


class ActorType(str, Enum):
    USER = "user"
    SYSTEM = "system"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = id_pk()
    username: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    team: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = id_pk()
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    permissions: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()


class UserRoleGrant(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    team_scope: Mapped[str | None] = mapped_column(Text)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    granted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    # 只追加不可改（D-6）：应用层无 UPDATE/DELETE 路径 + 库级 REVOKE（见迁移）

    id: Mapped[int] = id_pk()
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    actor_type: Mapped[ActorType] = mapped_column(
        enum_col(ActorType), default=ActorType.USER, server_default="user"
    )
    action: Mapped[str] = mapped_column(Text)
    resource_type: Mapped[str] = mapped_column(Text)
    resource_id: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, server_default=text("'{}'"))
    cost: Mapped[dict | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_col()

    __table_args__ = (
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
        Index("idx_audit_logs_actor", "actor_user_id", "created_at"),
        Index("idx_audit_logs_created", "created_at"),
    )
