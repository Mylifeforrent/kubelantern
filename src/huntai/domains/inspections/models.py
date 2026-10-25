"""巡检诊断域：inspection_rules / inspection_policies / inspection_policy_rules /
inspection_runs / findings（01-data-model §2.6）。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from huntai.core.db import Base, utcnow
from huntai.domains.bases import created_col, enum_col, id_pk, updated_col

from huntai.domains.alerts import models as _alerts  # noqa: F401 - 注册 alerts 表供 converted_alert_id 外键解析
from huntai.domains.clusters import models as _clusters  # noqa: F401

class FindingSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class FindingStatus(str, Enum):
    """6 态，值域禁改（领域 §6）。"""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    IGNORED = "ignored"
    CONVERTED_TO_ALERT = "converted_to_alert"


class InspectionRunStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class InspectionRunTrigger(str, Enum):
    SCHEDULE = "schedule"
    MANUAL = "manual"


class AIExplainLevel(str, Enum):
    OFF = "off"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class InspectionRule(Base):
    __tablename__ = "inspection_rules"

    id: Mapped[int] = id_pk()
    code: Mapped[str] = mapped_column(Text, unique=True)  # 业务键（D-5）
    name: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    severity_default: Mapped[FindingSeverity] = mapped_column(enum_col(FindingSeverity))
    k8s_version_fit: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()


class InspectionPolicy(Base):
    __tablename__ = "inspection_policies"

    id: Mapped[int] = id_pk()
    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"))
    name: Mapped[str] = mapped_column(Text)
    schedule: Mapped[str] = mapped_column(Text)  # cron 表达式
    ai_explain_level: Mapped[AIExplainLevel] = mapped_column(
        enum_col(AIExplainLevel), default=AIExplainLevel.OFF, server_default="off"
    )
    enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()

    __table_args__ = (UniqueConstraint("cluster_id", "name", name="uq_inspection_policies_cluster_name"),)


class InspectionPolicyRule(Base):
    """策略-规则多对多（D-11）。"""

    __tablename__ = "inspection_policy_rules"

    policy_id: Mapped[int] = mapped_column(
        ForeignKey("inspection_policies.id", ondelete="CASCADE"), primary_key=True
    )
    rule_id: Mapped[int] = mapped_column(ForeignKey("inspection_rules.id"), primary_key=True)


class InspectionRun(Base):
    __tablename__ = "inspection_runs"

    id: Mapped[int] = id_pk()
    policy_id: Mapped[int] = mapped_column(ForeignKey("inspection_policies.id"))
    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"))  # 冗余，看板免 join
    trigger: Mapped[InspectionRunTrigger] = mapped_column(
        enum_col(InspectionRunTrigger),
        default=InspectionRunTrigger.SCHEDULE,
        server_default="schedule",
    )
    status: Mapped[InspectionRunStatus] = mapped_column(
        enum_col(InspectionRunStatus),
        default=InspectionRunStatus.RUNNING,
        server_default="running",
    )
    result: Mapped[dict | None] = mapped_column(JSONB)
    findings_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_inspection_runs_cluster_time", "cluster_id", "started_at"),
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = id_pk()
    run_id: Mapped[int] = mapped_column(ForeignKey("inspection_runs.id"))
    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"))  # 冗余
    rule_code: Mapped[str] = mapped_column(Text)
    resource_ref: Mapped[dict] = mapped_column(JSONB)  # {kind, namespace, name}
    severity: Mapped[FindingSeverity] = mapped_column(enum_col(FindingSeverity))
    raw_error: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[FindingStatus] = mapped_column(
        enum_col(FindingStatus), default=FindingStatus.OPEN, server_default="open"
    )
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    # D-10：ignored 必填原因，CHECK 在迁移声明
    ignored_reason: Mapped[str | None] = mapped_column(Text)
    converted_alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()

    __table_args__ = (
        UniqueConstraint("run_id", "rule_code", "resource_ref", name="uk_findings_run_rule_resource"),
        Index("idx_findings_status_severity", "status", "severity"),
        Index("idx_findings_cluster_rule", "cluster_id", "rule_code"),
    )
