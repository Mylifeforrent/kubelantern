"""AI 智能体域（P1）：ai_tasks / ai_mask_mappings / ai_explanations / ai_call_logs
（01-data-model §2.7；BR-01/BR-03/BR-10 载体）。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from huntai.core.db import Base
from huntai.domains.bases import created_col, enum_col, id_pk, updated_col

from huntai.domains.incidents import models as _incidents  # noqa: F401 - 注册 incidents/findings 表供外键解析
from huntai.domains.inspections import models as _inspections  # noqa: F401

class AITaskType(str, Enum):
    EXPLAIN = "explain"
    INVESTIGATE = "investigate"
    WORKFLOW_GEN = "workflow_gen"


class AITaskStatus(str, Enum):
    """8 态，值域禁改（领域 §6）。"""

    CREATED = "created"
    SANITIZING = "sanitizing"
    RUNNING = "running"
    PENDING_APPROVAL = "pending_approval"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
    BUDGET_EXCEEDED = "budget_exceeded"


class AICallResultCode(str, Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


class AITask(Base):
    __tablename__ = "ai_tasks"

    id: Mapped[int] = id_pk()
    type: Mapped[AITaskType] = mapped_column(enum_col(AITaskType))
    status: Mapped[AITaskStatus] = mapped_column(
        enum_col(AITaskStatus), default=AITaskStatus.CREATED, server_default="created"
    )
    context_refs: Mapped[dict] = mapped_column(JSONB)  # {finding_id?/incident_id?/alert_id?...}
    finding_id: Mapped[int | None] = mapped_column(ForeignKey("findings.id"))
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"))
    budget: Mapped[dict] = mapped_column(JSONB)  # {max_calls, max_output_tokens}
    calls_used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    requires_approval: Mapped[bool] = mapped_column(default=False, server_default="false")
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    approval_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict | None] = mapped_column(JSONB)
    is_partial: Mapped[bool] = mapped_column(default=False, server_default="false")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_ai_tasks_status", "status"),
        Index("idx_ai_tasks_incident", "incident_id"),
        Index("idx_ai_tasks_finding", "finding_id"),
    )


class AIMaskMapping(Base):
    """掩码原值：信封加密 bytea，仅存本地、严禁外发（BR-01/D-2）。"""

    __tablename__ = "ai_mask_mappings"

    id: Mapped[int] = id_pk()
    task_id: Mapped[int] = mapped_column(ForeignKey("ai_tasks.id", ondelete="CASCADE"))
    placeholder: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)  # namespace / pod / ip / credential 等
    encrypted_original: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = created_col()

    __table_args__ = (UniqueConstraint("task_id", "placeholder", name="uq_ai_mask_mappings_task_placeholder"),)


class AIExplanation(Base):
    __tablename__ = "ai_explanations"

    id: Mapped[int] = id_pk()
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id"), unique=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("ai_tasks.id"))
    sanitized_input_digest: Mapped[str] = mapped_column(Text)  # sha-256
    output: Mapped[dict] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(Text)
    tokens: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = created_col()


class AICallLog(Base):
    """AI 调用日志：只追加（D-6）；prompt 只存 sha-256 摘要，不存明文（BR-10）。"""

    __tablename__ = "ai_call_logs"

    id: Mapped[int] = id_pk()
    task_id: Mapped[int] = mapped_column(ForeignKey("ai_tasks.id"))
    model: Mapped[str] = mapped_column(Text)
    tool_used: Mapped[str | None] = mapped_column(Text)
    prompt_digest: Mapped[str] = mapped_column(Text)  # sha-256，不存明文
    tokens_in: Mapped[int] = mapped_column(Integer)
    tokens_out: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    result_code: Mapped[AICallResultCode] = mapped_column(enum_col(AICallResultCode))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_col()

    __table_args__ = (
        Index("idx_ai_call_logs_task", "task_id"),
        Index("idx_ai_call_logs_created", "created_at"),
    )
