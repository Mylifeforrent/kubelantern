"""值班域 DTO（契约 oncall tag）。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from huntai.core.schemas import BaseSchema, Page, UtcDateTime


class OnCallScheduleResponse(BaseSchema):
    id: int
    name: str
    team: str
    rotation_rules: dict[str, Any]
    calendar: dict[str, Any]
    overrides: list[Any]
    enabled: bool
    created_at: UtcDateTime
    updated_at: UtcDateTime


class OnCallScheduleCreateRequest(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    team: str = Field(min_length=1, max_length=100)
    rotation_rules: dict[str, Any]
    calendar: dict[str, Any]
    overrides: list[Any] = []
    enabled: bool = True


class OnCallScheduleUpdateRequest(BaseSchema):
    model_config = dict(BaseSchema.model_config, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    team: str | None = Field(default=None, min_length=1, max_length=100)
    rotation_rules: dict[str, Any] | None = None
    calendar: dict[str, Any] | None = None
    overrides: list[Any] | None = None
    enabled: bool | None = None


class EscalationLevel(BaseSchema):
    level: int = Field(ge=1)
    target: str
    channel: str
    timeout_min: int = Field(gt=0)


class EscalationPolicyResponse(BaseSchema):
    id: int
    name: str
    schedule_id: int
    levels: list[Any]
    channel_fallbacks: list[Any]
    enabled: bool
    created_at: UtcDateTime
    updated_at: UtcDateTime


class EscalationPolicyCreateRequest(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    schedule_id: int
    levels: list[dict[str, Any]]
    channel_fallbacks: list[Any] = []
    enabled: bool = True


class EscalationPolicyUpdateRequest(BaseSchema):
    model_config = dict(BaseSchema.model_config, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    schedule_id: int | None = None
    levels: list[dict[str, Any]] | None = None
    channel_fallbacks: list[Any] | None = None
    enabled: bool | None = None


class NotificationRecordResponse(BaseSchema):
    id: int
    channel: str
    target: str
    content_digest: str
    status: str
    ack_action: str | None = None
    ack_at: UtcDateTime | None = None
    alert_id: int | None = None
    incident_id: int | None = None
    escalation_policy_id: int | None = None
    escalation_level: int | None = None
    error: str | None = None
    created_at: UtcDateTime


class OnCallSchedulePage(Page[OnCallScheduleResponse]):
    pass


class EscalationPolicyPage(Page[EscalationPolicyResponse]):
    pass


class NotificationRecordPage(Page[NotificationRecordResponse]):
    pass
