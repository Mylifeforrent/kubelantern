"""告警管理域：providers / alerts / enrichment_rules / correlation_rules / maintenance_windows
（01-data-model §2.4；L1 管道核心表）。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from huntai.core.db import Base
from huntai.domains.bases import created_col, enum_col, id_pk, updated_col

from huntai.domains.iam import models as _iam  # noqa: F401 - 注册 users 表供跨域外键解析

class ProviderCategory(str, Enum):
    SOURCE = "source"
    QUERY = "query"
    ACTION = "action"


class ProviderPullMode(str, Enum):
    PUSH = "push"
    POLL = "poll"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """8 态，值域禁改（领域 §6）。"""

    RECEIVED = "received"
    DEDUPLICATED = "deduplicated"
    ENRICHED = "enriched"
    CORRELATED = "correlated"
    STANDALONE = "standalone"
    SUPPRESSED = "suppressed"
    NOTIFIED = "notified"
    RESOLVED = "resolved"


class CorrelationMode(str, Enum):
    AUTO = "auto"
    CANDIDATE = "candidate"


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = id_pk()
    name: Mapped[str] = mapped_column(Text, unique=True)
    type: Mapped[str] = mapped_column(Text)
    category: Mapped[ProviderCategory] = mapped_column(enum_col(ProviderCategory))
    pull_mode: Mapped[ProviderPullMode | None] = mapped_column(enum_col(ProviderPullMode))
    config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'"))
    credential_id: Mapped[int | None] = mapped_column(ForeignKey("credentials.id"))
    fingerprint_fields: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'")
    )
    enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = id_pk()
    fingerprint: Mapped[str] = mapped_column(Text)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    title: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[AlertSeverity] = mapped_column(enum_col(AlertSeverity))
    status: Mapped[AlertStatus] = mapped_column(
        enum_col(AlertStatus), default=AlertStatus.RECEIVED, server_default="received"
    )
    labels: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'"))
    enrichments: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'"))
    raw_payload: Mapped[dict] = mapped_column(JSONB)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    first_occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # D-10：status=suppressed 时非空（BR-07），CHECK 在迁移声明
    suppressed_by_window_id: Mapped[int | None] = mapped_column(
        ForeignKey("maintenance_windows.id")
    )
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()

    __table_args__ = (
        # D-1 部分唯一索引：活跃周期内指纹唯一（迁移手写，此处登记保 autogenerate 可审）
        Index(
            "uk_alerts_active_fingerprint",
            "fingerprint",
            unique=True,
            postgresql_where=text("status <> 'resolved'"),
        ),
        Index("idx_alerts_labels", "labels", postgresql_using="gin", postgresql_ops={"labels": "jsonb_path_ops"}),
        Index("idx_alerts_provider_time", "provider_id", "last_occurred_at"),
        Index("idx_alerts_status_severity", "status", "severity"),
    )


class EnrichmentRule(Base):
    __tablename__ = "enrichment_rules"

    id: Mapped[int] = id_pk()
    name: Mapped[str] = mapped_column(Text, unique=True)
    matchers: Mapped[list | dict] = mapped_column(JSONB)
    mappings: Mapped[list] = mapped_column(JSONB)
    priority: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()


class CorrelationRule(Base):
    __tablename__ = "correlation_rules"

    id: Mapped[int] = id_pk()
    name: Mapped[str] = mapped_column(Text, unique=True)
    conditions: Mapped[dict] = mapped_column(JSONB)
    time_window_seconds: Mapped[int] = mapped_column(Integer)
    mode: Mapped[CorrelationMode] = mapped_column(
        enum_col(CorrelationMode), default=CorrelationMode.CANDIDATE, server_default="candidate"
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirm_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    reject_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()


class MaintenanceWindow(Base):
    __tablename__ = "maintenance_windows"

    id: Mapped[int] = id_pk()
    name: Mapped[str] = mapped_column(Text)
    scope: Mapped[dict] = mapped_column(JSONB)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_col()

    __table_args__ = (Index("idx_maintenance_windows_ends", "ends_at"),)
