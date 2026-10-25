"""实时推送（SSE，04-backend-design §5）。

- 发布：`XADD` 持久事件流 + `XTRIM` 保留窗口；调用方为各域 service 状态推进处（落库后发布，
  推送失败不回滚业务、仅记日志）。
- 订阅：Last-Event-ID → `XRANGE` 回放缺失事件（按团队 scope 过滤）→ 追平后 `XREAD` 实时消费；
  Stream ID 即 SSE id。心跳为 SSE comment（15s [ASSUMPTION]）。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, AsyncIterator

from redis.asyncio import Redis

from huntai.core.config import Settings

logger = logging.getLogger("huntai.realtime")

STREAM_KEY = "huntai:events"
TOPICS = ("alerts", "incidents", "candidates", "inspections", "ai-tasks", "notifications", "system")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class RealtimeEvent:
    topic: str  # 候选集见 TOPICS
    name: str  # 事件名，如 alert.updated / incident.timeline.updated / ai_task.updated
    resource: str
    resource_id: int
    team: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def payload(self) -> dict[str, Any]:
        body = {
            "resource": self.resource,
            "resource_id": self.resource_id,
            "team": self.team,
            "occurred_at": _now_iso(),
        }
        body.update(self.extra)
        return body

    def sse_frame(self, stream_id: str) -> str:
        return f"id: {stream_id}\nevent: {self.name}\ndata: {json.dumps(self.payload(), ensure_ascii=False)}\n\n"


class RealtimeHub:
    def __init__(self, redis: Redis, *, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings

    async def publish(self, event: RealtimeEvent) -> str | None:
        """落库同事务后调用；失败仅记日志，不回滚业务（[ASSUMPTION] 一致性取舍）。"""
        try:
            fields = {
                "topic": event.topic,
                "name": event.name,
                "team": event.team or "",
                "data": json.dumps(event.payload(), ensure_ascii=False),
            }
            stream_id = await self._redis.xadd(STREAM_KEY, fields)
            retention_ms = self._settings.stream_retention_minutes * 60 * 1000
            min_id = f"{int(datetime.now(UTC).timestamp() * 1000) - retention_ms}-0"
            await self._redis.xtrim(STREAM_KEY, minid=min_id, approximate=False)
            return stream_id
        except Exception:
            logger.exception("realtime publish failed", extra={"props": {"topic": event.topic}})
            return None

    async def subscribe(
        self,
        *,
        topics: set[str],
        team: str | None,
        last_event_id: str | None,
        heartbeat_seconds: int,
    ) -> AsyncIterator[str]:
        """SSE 帧生成器：回放 → 实时；team 非 None 时过滤他团队事件。"""
        cursor = last_event_id or "$"
        replaying = last_event_id is not None
        while True:
            entries: list[tuple[str, dict[str, str]]] = []
            if replaying:
                entries = await self._redis.xrange(STREAM_KEY, min=f"({cursor}", max="+", count=100)
                if not entries:
                    replaying = False
                    cursor = "$"
                    result = await self._redis.xread(
                        {STREAM_KEY: "$"}, block=heartbeat_seconds * 1000, count=100
                    )
                    entries = _xread_entries(result)
            else:
                result = await self._redis.xread(
                    {STREAM_KEY: cursor}, block=heartbeat_seconds * 1000, count=100
                )
                entries = _xread_entries(result)

            if not entries:
                yield ": ping\n\n"
                continue

            for stream_id, fields in entries:
                cursor = stream_id
                if fields.get("topic") not in topics:
                    continue
                event_team = fields.get("team") or None
                if team is not None and event_team is not None and event_team != team:
                    continue
                yield _frame(stream_id, fields)


def _xread_entries(result) -> list[tuple[str, dict[str, str]]]:
    """redis-py XREAD 返回 [(stream_key, [(id, fields), ...])]，取首个流的条目。"""
    if not result:
        return []
    for _stream_key, entries in result:
        return list(entries)
    return []


def _frame(stream_id: str, fields: dict[str, str]) -> str:
    return (
        f"id: {stream_id}\n"
        f"event: {fields.get('name', 'unknown')}\n"
        f"data: {fields.get('data', '{}')}\n\n"
    )
