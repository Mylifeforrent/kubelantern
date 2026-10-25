"""值班响应域（P2）：oncall_schedules / escalation_policies（01-data-model §2.8）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from huntai.core.db import Base
from huntai.domains.bases import created_col, id_pk, updated_col


class OnCallSchedule(Base):
    """排班表：rotation_rules / calendar / overrides 结构先以 JSONB 承载（[ASSUMPTION]）。"""

    __tablename__ = "oncall_schedules"

    id: Mapped[int] = id_pk()
    name: Mapped[str] = mapped_column(Text, unique=True)
    team: Mapped[str] = mapped_column(Text)
    rotation_rules: Mapped[dict] = mapped_column(JSONB)
    calendar: Mapped[dict] = mapped_column(JSONB)
    overrides: Mapped[list] = mapped_column(JSONB, default=list, server_default="'[]'")
    enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()


class EscalationPolicy(Base):
    """升级策略：levels [{level,target,channel,timeout_min}]；降级链 BR-13。"""

    __tablename__ = "escalation_policies"

    id: Mapped[int] = id_pk()
    name: Mapped[str] = mapped_column(Text, unique=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("oncall_schedules.id"))
    levels: Mapped[list] = mapped_column(JSONB)
    channel_fallbacks: Mapped[list] = mapped_column(JSONB, default=list, server_default="'[]'")
    enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    created_at: Mapped[datetime] = created_col()
    updated_at: Mapped[datetime] = updated_col()
