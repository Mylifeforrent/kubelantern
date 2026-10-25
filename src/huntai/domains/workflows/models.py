"""流程编排域（P3）：workflows / workflow_runs（01-data-model §2.9；BR-05 载体）。

引擎语义随 P3 详设另立文档（HLD §6.3）；本期仅薄存储层。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from huntai.core.db import Base, utcnow
from huntai.domains.bases import created_col, enum_col, id_pk, updated_col

from huntai.domains.alerts import models as _alerts  # noqa: F401 - 注册 alerts/incidents/users 表供外键解析
from huntai.domains.incidents import models as _incidents  # noqa: F401

class WorkflowSource(str, Enum):
    MANUAL = "manual"
    AI_GENERATED = "ai_generated"


class WorkflowRunTrigger(str, Enum):
    ALERT = "alert"
    MANUAL = "manual"
    SCHEDULE = "schedule"


class WorkflowRunStatus(str, Enum):
    """7 态，值域禁改（领域 §6）。"""

    TRIGGERED = "triggered"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"


class Workflow(Base):
    """一版本一行实现版本历史（[ASSUMPTION]）；uk_workflows_current 部分唯一索引在迁移声明。"""

    __tablename__ = "workflows"

    id: Mapped[int] = id_pk()
    name: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    yaml: Mapped[str] = mapped_column(Text)
    source: Mapped[WorkflowSource] = mapped_column(enum_col(WorkflowSource))
    # D-10：source='ai_generated' 时必填（BR-05），CHECK 在迁移声明
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    is_current: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_workflows_name_version"),
        Index(
            "uk_workflows_current",
            "name",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = id_pk()
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"))
    workflow_version: Mapped[int] = mapped_column(Integer)
    yaml_snapshot: Mapped[str] = mapped_column(Text)
    trigger_type: Mapped[WorkflowRunTrigger] = mapped_column(enum_col(WorkflowRunTrigger))
    triggered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"))
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"))
    status: Mapped[WorkflowRunStatus] = mapped_column(
        enum_col(WorkflowRunStatus),
        default=WorkflowRunStatus.TRIGGERED,
        server_default="triggered",
    )
    steps_log: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'"))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_col()

    __table_args__ = (
        Index("idx_workflow_runs_workflow", "workflow_id", "created_at"),
        Index("idx_workflow_runs_status", "status"),
    )
