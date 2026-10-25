"""共享 pydantic 基座：响应模型基类、UTC 时间序列化、分页包裹。

- 列表响应统一 `{items, total, offset, limit}`（契约 PageMeta）。
- 时间序列化为 UTC ISO 8601 带 Z 后缀（契约约定）。
- 禁止 ORM 模型直接充当 response model（AP-7）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer

T = TypeVar("T")


def _serialize_utc(v: datetime) -> str:
    if v.tzinfo is None:
        v = v.replace(tzinfo=UTC)
    return v.astimezone(UTC).isoformat().replace("+00:00", "Z")


UtcDateTime = Annotated[datetime, PlainSerializer(_serialize_utc, return_type=str)]


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PageMeta(BaseSchema):
    total: int
    offset: int
    limit: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int

    @classmethod
    def build(cls, items: list[T], *, total: int, offset: int, limit: int) -> "Page[T]":
        return cls(items=items, total=total, offset=offset, limit=limit)
