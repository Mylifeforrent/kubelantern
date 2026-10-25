"""巡检诊断域 DTO（契约 inspections/findings tag）。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from huntai.core.schemas import BaseSchema, Page, UtcDateTime


class InspectionRuleResponse(BaseSchema):
    id: int
    code: str
    name: str
    category: str
    severity_default: str
    k8s_version_fit: str
    description: str | None = None
    enabled: bool
    created_at: UtcDateTime
    updated_at: UtcDateTime


class InspectionRuleCreateRequest(BaseSchema):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    severity_default: str
    k8s_version_fit: str = ">=1.20"
    description: str | None = None
    enabled: bool = True


class InspectionRuleUpdateRequest(BaseSchema):
    model_config = dict(BaseSchema.model_config, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = None
    severity_default: str | None = None
    k8s_version_fit: str | None = None
    description: str | None = None
    enabled: bool | None = None


class InspectionPolicyResponse(BaseSchema):
    id: int
    cluster_id: int
    name: str
    schedule: str
    ai_explain_level: str
    rule_ids: list[int] = []
    enabled: bool
    created_at: UtcDateTime
    updated_at: UtcDateTime


class InspectionPolicyCreateRequest(BaseSchema):
    cluster_id: int
    name: str = Field(min_length=1, max_length=200)
    schedule: str = Field(min_length=1)
    ai_explain_level: str = "off"
    rule_ids: list[int] = []
    enabled: bool = True


class InspectionPolicyUpdateRequest(BaseSchema):
    model_config = dict(BaseSchema.model_config, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    schedule: str | None = Field(default=None, min_length=1)
    ai_explain_level: str | None = None
    rule_ids: list[int] | None = None
    enabled: bool | None = None


class InspectionRunResponse(BaseSchema):
    id: int
    policy_id: int
    cluster_id: int
    trigger: str
    status: str
    result: dict[str, Any] | None = None
    findings_count: int
    error: str | None = None
    started_at: UtcDateTime
    finished_at: UtcDateTime | None = None


class ResourceRef(BaseSchema):
    kind: str
    namespace: str | None = None
    name: str


class FindingResponse(BaseSchema):
    id: int
    run_id: int
    cluster_id: int
    rule_code: str
    resource_ref: dict[str, Any]
    severity: str
    raw_error: dict[str, Any]
    status: str
    assignee_id: int | None = None
    ignored_reason: str | None = None
    converted_alert_id: int | None = None
    resolved_at: UtcDateTime | None = None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class FindingIgnoreRequest(BaseSchema):
    ignored_reason: str = Field(min_length=1)


class InspectionRulePage(Page[InspectionRuleResponse]):
    pass


class InspectionPolicyPage(Page[InspectionPolicyResponse]):
    pass


class InspectionRunPage(Page[InspectionRunResponse]):
    pass


class FindingPage(Page[FindingResponse]):
    pass
