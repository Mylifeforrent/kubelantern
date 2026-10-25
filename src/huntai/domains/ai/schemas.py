"""AI 智能体域 DTO（契约 ai-tasks tag；路径按契约 /ai/tasks，C3）。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from huntai.core.schemas import BaseSchema, Page, UtcDateTime


class AITaskBudget(BaseSchema):
    max_calls: int
    max_output_tokens: int


class AITaskResponse(BaseSchema):
    id: int
    type: str
    status: str
    context_refs: dict[str, Any]
    finding_id: int | None = None
    incident_id: int | None = None
    budget: AITaskBudget
    calls_used: int
    tokens_used: int
    requires_approval: bool
    requested_by: int
    approval_deadline_at: UtcDateTime | None = None
    approved_by: int | None = None
    decided_at: UtcDateTime | None = None
    result: dict[str, Any] | None = None
    is_partial: bool
    error: str | None = None
    created_at: UtcDateTime
    updated_at: UtcDateTime
    finished_at: UtcDateTime | None = None


class AICallLogResponse(BaseSchema):
    id: int
    task_id: int
    model: str
    tool_used: str | None = None
    prompt_digest: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    result_code: str
    error: str | None = None
    created_at: UtcDateTime


class AITaskCancelRequest(BaseSchema):
    reason: str | None = Field(default=None, max_length=500)


class AITaskPage(Page[AITaskResponse]):
    pass


class AICallLogPage(Page[AICallLogResponse]):
    pass
