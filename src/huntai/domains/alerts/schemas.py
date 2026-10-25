"""告警管理域 DTO（契约 alerts/alert-rules tag）。"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from huntai.core.schemas import BaseSchema, Page, UtcDateTime


class AlertResponse(BaseSchema):
    id: int
    fingerprint: str
    provider_id: int
    title: str | None = None
    severity: str
    status: str
    labels: dict[str, Any]
    enrichments: dict[str, Any]
    occurrence_count: int
    first_occurred_at: UtcDateTime
    last_occurred_at: UtcDateTime
    assignee_id: int | None = None
    acknowledged_at: UtcDateTime | None = None
    resolved_at: UtcDateTime | None = None
    suppressed_by_window_id: int | None = None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class SuppressSuggestionReason(str, Enum):
    """误报抑制建议原因（PRD FR-11 三原因；值域与前端弹窗一致）。"""

    FALSE_POSITIVE = "false_positive"
    EXPECTED_NOISE = "expected_noise"
    DUPLICATE_RULE = "duplicate_rule"


class SuppressSuggestionRequest(BaseSchema):
    reason: SuppressSuggestionReason
    note: str | None = Field(default=None, max_length=500)


class SuppressSuggestionResult(BaseSchema):
    accepted: bool
    alert_id: int


class AlertDetailResponse(AlertResponse):
    raw_payload: dict[str, Any]


class WebhookIngestResult(BaseSchema):
    alert_id: int
    merged: bool


class ProviderResponse(BaseSchema):
    id: int
    name: str
    type: str
    category: str
    pull_mode: str | None = None
    config: dict[str, Any]
    credential_id: int | None = None
    fingerprint_fields: list[str]
    enabled: bool
    created_at: UtcDateTime
    updated_at: UtcDateTime


class ProviderCreateRequest(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(min_length=1, max_length=100)
    category: str
    pull_mode: str | None = None
    config: dict[str, Any] = {}
    credential_id: int | None = None
    fingerprint_fields: list[str] = []
    enabled: bool = True


class ProviderUpdateRequest(BaseSchema):
    model_config = dict(BaseSchema.model_config, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: str | None = Field(default=None, min_length=1, max_length=100)
    category: str | None = None
    pull_mode: str | None = None
    config: dict[str, Any] | None = None
    credential_id: int | None = None
    fingerprint_fields: list[str] | None = None
    enabled: bool | None = None


class AIExplanationResponse(BaseSchema):
    id: int
    finding_id: int
    task_id: int | None = None
    sanitized_input_digest: str
    output: dict[str, Any]
    model: str
    tokens: int
    created_at: UtcDateTime


class EnrichmentRuleResponse(BaseSchema):
    id: int
    name: str
    matchers: Any
    mappings: Any
    priority: int
    enabled: bool
    created_at: UtcDateTime
    updated_at: UtcDateTime


class EnrichmentRuleCreateRequest(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    matchers: Any
    mappings: Any
    priority: int = 0
    enabled: bool = True


class EnrichmentRuleUpdateRequest(BaseSchema):
    model_config = dict(BaseSchema.model_config, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    matchers: Any = None
    mappings: Any = None
    priority: int | None = None
    enabled: bool | None = None


class CorrelationRuleResponse(BaseSchema):
    id: int
    name: str
    conditions: Any
    time_window_seconds: int
    mode: str
    activated_at: UtcDateTime | None = None
    confirm_count: int
    reject_count: int
    enabled: bool
    created_at: UtcDateTime
    updated_at: UtcDateTime


class CorrelationRuleCreateRequest(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    conditions: Any
    time_window_seconds: int = Field(gt=0)
    mode: str = "candidate"
    activated_at: UtcDateTime | None = None
    enabled: bool = True


class CorrelationRuleUpdateRequest(BaseSchema):
    model_config = dict(BaseSchema.model_config, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    conditions: Any = None
    time_window_seconds: int | None = Field(default=None, gt=0)
    mode: str | None = None
    enabled: bool | None = None


class MaintenanceWindowResponse(BaseSchema):
    id: int
    name: str
    scope: Any
    starts_at: UtcDateTime
    ends_at: UtcDateTime
    reason: str
    created_by: int | None = None
    created_at: UtcDateTime


class MaintenanceWindowCreateRequest(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    scope: Any
    starts_at: UtcDateTime
    ends_at: UtcDateTime
    reason: str = Field(min_length=1)


class AlertPage(Page[AlertResponse]):
    pass


class ProviderPage(Page[ProviderResponse]):
    pass


class AIExplanationPage(Page[AIExplanationResponse]):
    pass


class EnrichmentRulePage(Page[EnrichmentRuleResponse]):
    pass


class CorrelationRulePage(Page[CorrelationRuleResponse]):
    pass


class MaintenanceWindowPage(Page[MaintenanceWindowResponse]):
    pass
