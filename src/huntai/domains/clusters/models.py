"""集群接入域：credentials / clusters（01-data-model §2.3）。

红线：凭证值永不落库（D-2），credentials 只存 secret_ref 引用。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from huntai.core.db import Base
from huntai.domains.bases import created_col, enum_col, id_pk, updated_col


class CredentialScope(str, Enum):
    READONLY = "readonly"
    WRITE = "write"


class ClusterStatus(str, Enum):
    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[int] = id_pk()
    name: Mapped[str] = mapped_column(Text, unique=True)
    secret_ref: Mapped[str] = mapped_column(Text)
    scope: Mapped[CredentialScope] = mapped_column(
        enum_col(CredentialScope), default=CredentialScope.READONLY, server_default="readonly"
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[int] = id_pk()
    name: Mapped[str] = mapped_column(Text, unique=True)
    environment: Mapped[str] = mapped_column(Text)
    api_endpoint: Mapped[str] = mapped_column(Text)
    status: Mapped[ClusterStatus] = mapped_column(
        enum_col(ClusterStatus), default=ClusterStatus.UNKNOWN, server_default="unknown"
    )
    k8s_version: Mapped[str | None] = mapped_column(Text)
    credential_id: Mapped[int] = mapped_column(ForeignKey("credentials.id"))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # 软删（D-7）
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()

    __table_args__ = (Index("idx_clusters_status", "status"),)
