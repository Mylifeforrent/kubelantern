"""事件响应域 DTO（契约 incidents/incident-candidates/status-page tag）。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from huntai.core.schemas import BaseSchema, Page, UtcDateTime


class IncidentResponse(BaseSchema):
    id: int
    title: str
    severity: str
    status: str
    source: str
    candidate_id: int | None = None
    correlation_rule_id: int | None = None
    team: str | None = None
    assignee_id: int | None = None
    created_by: int | None = None
    status_page_sync: bool
    cancelled_reason: str | None = None
    acknowledged_at: UtcDateTime | None = None
    mitigated_at: UtcDateTime | None = None
    resolved_at: UtcDateTime | None = None
    closed_at: UtcDateTime | None = None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class IncidentCreateRequest(BaseSchema):
    title: str = Field(min_length=1, max_length=500)
    severity: str
    team: str | None = None
    assignee_id: int | None = None
    related_alert_ids: list[int] = []


class IncidentCancelRequest(BaseSchema):
    cancelled_reason: str = Field(min_length=1)


class IncidentTimelineItem(BaseSchema):
    occurred_at: UtcDateTime
    kind: str
    summary: str
    actor_id: int | None = None


class IncidentDetailResponse(IncidentResponse):
    timeline: list[IncidentTimelineItem] = []
    related_alerts: list[dict[str, Any]] = []
    escalation_summary: dict[str, Any] = {}


class PostmortemActionItemResponse(BaseSchema):
    id: int
    content: str
    owner_id: int | None = None
    due_date: str | None = None
    status: str
    created_at: UtcDateTime
    updated_at: UtcDateTime


class PostmortemResponse(BaseSchema):
    id: int
    incident_id: int
    timeline: list[dict[str, Any]]
    root_cause: str
    action_items: list[PostmortemActionItemResponse] = []
    created_by: int
    created_at: UtcDateTime
    updated_at: UtcDateTime


class PostmortemUpdateRequest(BaseSchema):
    root_cause: str = Field(min_length=1)
    timeline: list[dict[str, Any]] | None = None
    action_items: list[dict[str, Any]] | None = None


class IncidentCandidateResponse(BaseSchema):
    id: int
    correlation_rule_id: int
    title: str
    member_alert_ids: list[int]
    similarity: float | None = None
    status: str
    reject_reason: str | None = None
    decided_by: int | None = None
    decided_at: UtcDateTime | None = None
    created_at: UtcDateTime


class CandidateRejectRequest(BaseSchema):
    reject_reason: str
    note: str | None = None


class StatusPageEntryResponse(BaseSchema):
    id: int
    incident_id: int
    title: str
    visibility: str
    service_status: str
    created_at: UtcDateTime
    updated_at: UtcDateTime


class StatusPageEntryCreateRequest(BaseSchema):
    incident_id: int
    title: str = Field(min_length=1)
    visibility: str = "internal"
    service_status: str = Field(min_length=1)


class StatusPageUpdateRequest(BaseSchema):
    model_config = dict(BaseSchema.model_config, extra="forbid")

    title: str | None = Field(default=None, min_length=1)
    visibility: str | None = None
    service_status: str | None = Field(default=None, min_length=1)


class IncidentPage(Page[IncidentResponse]):
    pass


class IncidentCandidatePage(Page[IncidentCandidateResponse]):
    pass


class StatusPageEntryPage(Page[StatusPageEntryResponse]):
    pass
