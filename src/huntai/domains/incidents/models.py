"""事件响应域（P2）：incident_candidates / incidents / incident_alerts / postmortems /
postmortem_action_items / status_page_entries / status_page_updates（01-data-model §2.5）。"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from huntai.core.db import Base
from huntai.domains.bases import created_col, enum_col, id_pk, updated_col

from huntai.domains.alerts import models as _alerts  # noqa: F401 - 注册 correlation_rules/alerts/users 表
from huntai.domains.iam import models as _iam_2  # noqa: F401

class IncidentSeverity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class IncidentStatus(str, Enum):
    """6 态，值域禁改（领域 §6）。"""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    CANCELLED = "cancelled"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentSource(str, Enum):
    CORRELATION = "correlation"
    MANUAL = "manual"


class IncidentCandidateStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class StatusPageVisibility(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"


class ActionItemStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class IncidentCandidate(Base):
    """候选事件独立表（D-8）：确认后才写 incidents。"""

    __tablename__ = "incident_candidates"

    id: Mapped[int] = id_pk()
    correlation_rule_id: Mapped[int] = mapped_column(ForeignKey("correlation_rules.id"))
    title: Mapped[str] = mapped_column(Text)
    member_alert_ids: Mapped[list] = mapped_column(JSONB)
    similarity: Mapped[float | None] = mapped_column(Numeric)
    status: Mapped[IncidentCandidateStatus] = mapped_column(
        enum_col(IncidentCandidateStatus),
        default=IncidentCandidateStatus.PENDING,
        server_default="pending",
    )
    reject_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_col()


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = id_pk()
    title: Mapped[str] = mapped_column(Text)
    severity: Mapped[IncidentSeverity] = mapped_column(enum_col(IncidentSeverity))
    status: Mapped[IncidentStatus] = mapped_column(
        enum_col(IncidentStatus), default=IncidentStatus.OPEN, server_default="open"
    )
    source: Mapped[IncidentSource] = mapped_column(enum_col(IncidentSource))
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("incident_candidates.id"))
    correlation_rule_id: Mapped[int | None] = mapped_column(ForeignKey("correlation_rules.id"))
    team: Mapped[str | None] = mapped_column(Text)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status_page_sync: Mapped[bool] = mapped_column(default=False, server_default="false")
    # D-10：cancelled 必填原因，CHECK 在迁移声明
    cancelled_reason: Mapped[str | None] = mapped_column(Text)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mitigated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()

    __table_args__ = (
        Index("idx_incidents_status_severity", "status", "severity"),
        Index("idx_incidents_team", "team"),
    )


class IncidentAlert(Base):
    __tablename__ = "incident_alerts"

    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), primary_key=True)
    correlation_rule_id: Mapped[int | None] = mapped_column(ForeignKey("correlation_rules.id"))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("idx_incident_alerts_alert", "alert_id"),)


class Postmortem(Base):
    __tablename__ = "postmortems"

    id: Mapped[int] = id_pk()
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), unique=True)
    timeline: Mapped[list] = mapped_column(JSONB)
    root_cause: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()


class PostmortemActionItem(Base):
    __tablename__ = "postmortem_action_items"

    id: Mapped[int] = id_pk()
    postmortem_id: Mapped[int] = mapped_column(
        ForeignKey("postmortems.id", ondelete="CASCADE")
    )
    content: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[ActionItemStatus] = mapped_column(
        enum_col(ActionItemStatus), default=ActionItemStatus.PENDING, server_default="pending"
    )
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()


class StatusPageEntry(Base):
    __tablename__ = "status_page_entries"

    id: Mapped[int] = id_pk()
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), unique=True)
    title: Mapped[str] = mapped_column(Text)
    visibility: Mapped[StatusPageVisibility] = mapped_column(
        enum_col(StatusPageVisibility),
        default=StatusPageVisibility.INTERNAL,
        server_default="internal",
    )
    service_status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()


class StatusPageUpdate(Base):
    __tablename__ = "status_page_updates"

    id: Mapped[int] = id_pk()
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("status_page_entries.id", ondelete="CASCADE")
    )
    message: Mapped[str] = mapped_column(Text)
    status_snapshot: Mapped[str | None] = mapped_column(Text)
    posted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_revoked: Mapped[bool] = mapped_column(default=False, server_default="false")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
