"""请求与任务上下文：actor / trace_id 经 contextvar 贯穿 API 与 worker 日志。

trace_id 传播链：API 入口生成（或透传 X-Request-ID）→ contextvar → 入队载荷 →
worker 续带（04-backend-design §6.1）。
"""

from __future__ import annotations

from contextvars import ContextVar, Token

actor_id: ContextVar[int | None] = ContextVar("actor_id", default=None)
actor_type: ContextVar[str] = ContextVar("actor_type", default="user")
actor_name: ContextVar[str | None] = ContextVar("actor_name", default=None)
trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def set_actor(user_id: int | None, *, actor_kind: str = "user", name: str | None = None) -> None:
    actor_id.set(user_id)
    actor_type.set(actor_kind)
    actor_name.set(name)


def system_actor(task_name: str) -> None:
    """worker 任务入口统一置 system actor（04-backend-design §6.2）。"""
    actor_id.set(None)
    actor_type.set("system")
    actor_name.set(task_name)


def reset(token: tuple[Token, ...]) -> None:
    for t in reversed(token):
        t.var.reset(t)
