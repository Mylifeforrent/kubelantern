"""集群接入域 DTO（契约 clusters/providers tag）。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from huntai.core.schemas import BaseSchema, Page, UtcDateTime


class ClusterResponse(BaseSchema):
    id: int
    name: str
    environment: str
    api_endpoint: str
    status: str
    k8s_version: str | None = None
    credential_id: int
    last_checked_at: UtcDateTime | None = None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class ClusterCreateRequest(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    environment: str = Field(min_length=1, max_length=100)
    api_endpoint: str = Field(min_length=1)
    credential_id: int


class ClusterUpdateRequest(BaseSchema):
    model_config = dict(BaseSchema.model_config, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    environment: str | None = Field(default=None, min_length=1, max_length=100)
    api_endpoint: str | None = Field(default=None, min_length=1)
    credential_id: int | None = None


class ConnectionTestResultResponse(BaseSchema):
    status: str
    k8s_version: str | None = None
    message: str | None = None
    checked_at: UtcDateTime


class ClusterPage(Page[ClusterResponse]):
    pass
