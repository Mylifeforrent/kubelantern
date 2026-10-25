"""分页 / 排序 / 过滤解析（04-backend-design §4.3）。

- offset/limit：limit 上限 200、offset 上限 10000（[ASSUMPTION] P0 压测）。
- 排序：`?sort=-last_occurred_at,severity`，`-` 前缀降序；字段白名单非法即 400。
- 响应统一 `{items, total, offset, limit}`。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import ColumnExpressionArgument, asc, desc, func, select

from huntai.core.errors import ProblemError

MAX_LIMIT = 200
MAX_OFFSET = 10_000
DEFAULT_LIMIT = 50


@dataclass
class PageParams:
    offset: int = 0
    limit: int = DEFAULT_LIMIT
    sort: list[tuple[str, bool]] = field(default_factory=list)  # (字段名, 是否降序)


def clamp_page(offset: int = 0, limit: int = DEFAULT_LIMIT) -> tuple[int, int]:
    if offset < 0 or limit < 1:
        raise ProblemError(status=400, detail="offset/limit 取值非法")
    return min(offset, MAX_OFFSET), min(limit, MAX_LIMIT)


def parse_sort(sort: str | None, whitelist: dict[str, Any]) -> list[tuple[str, bool]]:
    """whitelist: 展示名 -> SQLAlchemy 列表达式。非法字段返回 400。"""
    if not sort:
        return []
    result: list[tuple[str, bool]] = []
    for part in sort.split(","):
        part = part.strip()
        if not part:
            continue
        desc_order = part.startswith("-")
        name = part[1:] if desc_order else part
        if name not in whitelist:
            raise ProblemError(
                status=400,
                detail=f"不可排序字段：{name}（允许：{','.join(sorted(whitelist))}）",
            )
        result.append((name, desc_order))
    return result


def apply_sort(stmt, sorts: list[tuple[str, bool]], whitelist: dict[str, Any]):
    for name, desc_order in sorts:
        column = whitelist[name]
        stmt = stmt.order_by(desc(column) if desc_order else asc(column))
    return stmt


def paginate(
    stmt,
    *,
    offset: int,
    limit: int,
):
    """返回 (count_stmt, page_stmt) 供同一 session 依次执行。"""
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    return count_stmt, stmt.offset(offset).limit(limit)
