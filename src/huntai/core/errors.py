"""RFC 7807 problem 错误模型（04-backend-design §4.4；契约 components Problem）。

- 400 参数/过滤字段非法；401 未认证；403 权限矩阵拒绝；404 资源不存在（团队隔离越权一律 404）；
- 409 状态机非法迁移；422 请求体校验失败；429 webhook 限流；500 内部错误（detail 不泄内部信息）。
- type URL 域名占位 [TBD-INFRA]；detail 是面向开发者的诊断信息，不是 UI 文案。
"""

from __future__ import annotations

from typing import Any

PROBLEM_TYPE_BASE = "https://huntai.example/problems"

_TITLES = {
    400: "Bad request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not found",
    409: "Conflict",
    422: "Validation error",
    429: "Too many requests",
    500: "Internal server error",
    501: "Not implemented",
    503: "Service unavailable",
}


class ProblemError(Exception):
    """业务层统一异常；app 异常处理器转 problem+json 响应。"""

    def __init__(
        self,
        *,
        status: int = 400,
        title: str | None = None,
        code: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.status = status
        self.title = title or _TITLES.get(status, "Error")
        self.code = code
        self.detail = detail
        super().__init__(detail or self.title)


def not_found(resource: str, resource_id: Any) -> ProblemError:
    # 越权访问与不存在同形（防资源探测）
    return ProblemError(status=404, detail=f"{resource} {resource_id} not found")


def state_conflict(code: str, detail: str) -> ProblemError:
    return ProblemError(status=409, code=code, detail=detail)


def problem_body(
    *,
    status: int,
    title: str,
    detail: str | None = None,
    code: str | None = None,
    instance: str | None = None,
    trace_id: str | None = None,
    errors: list[dict] | None = None,
) -> dict:
    body: dict = {
        "type": f"{PROBLEM_TYPE_BASE}/{_slug(title)}",
        "title": title,
        "status": status,
    }
    if detail:
        body["detail"] = detail
    if instance:
        body["instance"] = instance
    if code:
        body["code"] = code
    if trace_id:
        body["trace_id"] = trace_id
    if errors:
        body["errors"] = errors
    return body


def _slug(title: str) -> str:
    return (
        "".join(c if c.isalnum() else "-" for c in title.lower())
        .strip("-")
        .replace("--", "-")
    )
