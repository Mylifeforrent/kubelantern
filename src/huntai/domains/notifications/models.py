"""通知中心域（P2）：notification_records（01-data-model §2.8；BR-08/BR-13，只追加 D-6）。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from huntai.core.db import Base
from huntai.domains.bases import created_col, enum_col, id_pk

from huntai.domains.alerts import models as _alerts  # noqa: F401 - 注册 alerts/incidents/escalation_policies 表供外键解析
from huntai.domains.incidents import models as _incidents  # noqa: F401
from huntai.domains.oncall import models as _oncall  # noqa: F401

class NotificationStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    ACKED = "acked"


class NotificationRecord(Base):
    """每次投递尝试独立一行（含降级、升级投递）；content 只存摘要不存全文。"""

    __tablename__ = "notification_records"

    id: Mapped[int] = id_pk()
    channel: Mapped[str] = mapped_column(Text)  # im / sms / voice（[TBD-BIZ] 组合）
    target: Mapped[str] = mapped_column(Text)
    content_digest: Mapped[str] = mapped_column(Text)
    status: Mapped[NotificationStatus] = mapped_column(
        enum_col(NotificationStatus), default=NotificationStatus.QUEUED, server_default="queued"
    )
    ack_action: Mapped[str | None] = mapped_column(Text)  # ack / escalate / resolve
    ack_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"))
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"))
    escalation_policy_id: Mapped[int | None] = mapped_column(ForeignKey("escalation_policies.id"))
    escalation_level: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_col()

    __table_args__ = (
        Index("idx_notification_records_alert", "alert_id"),
        Index("idx_notification_records_incident", "incident_id"),
        Index("idx_notification_records_status", "status", "created_at"),
    )
