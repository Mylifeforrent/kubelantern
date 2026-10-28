"""realtime tag：SSE 订阅端点（Last-Event-ID 回放 + 心跳，04-backend-design §5）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from huntai.app.deps import get_current_user
from huntai.app.routing import TransactionalAPIRoute
from huntai.core.security import Principal
from huntai.realtime.hub import TOPICS

router = APIRouter(route_class=TransactionalAPIRoute)


@router.get("/realtime/stream")
async def subscribe_realtime_stream(
    request: Request,
    topics: str | None = None,
    principal: Principal = Depends(get_current_user),
):
    """订阅主题（逗号分隔）；T 角色按 team_scope 过滤他团队事件。"""
    hub = request.app.state.hub
    settings = request.app.state.settings
    requested = {t.strip() for t in (topics or "").split(",") if t.strip()}
    effective = requested & set(TOPICS) or set(TOPICS)
    last_event_id = request.headers.get("Last-Event-ID")

    from huntai.core.security import TeamScope

    team = None
    if "developer" in principal.roles and "admin" not in principal.roles:
        team = principal.team_scope_for("alerts", "read") or principal.team

    async def event_stream():
        generator = hub.subscribe(
            topics=effective,
            team=team,
            last_event_id=last_event_id,
            heartbeat_seconds=settings.sse_heartbeat_seconds,
        )
        try:
            # hub 自身以 heartbeat_seconds 阻塞轮询并产出 ": ping"；外层不能再套 wait_for，
            # 否则超时会取消 __anext__ 并把异步生成器关闭，导致连接每 15s 被服务端断开。
            async for frame in generator:
                if await request.is_disconnected():
                    break
                yield frame
        finally:
            await generator.aclose()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
