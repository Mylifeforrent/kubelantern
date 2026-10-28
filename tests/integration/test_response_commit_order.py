"""回归：写接口的提交必须早于响应发送。

FastAPI 0.117+ 依赖的退出代码在响应发送之后执行；若请求级事务在 teardown 才 commit，
客户端拿到 201 后立刻 GET 新资源会读到未提交数据而 404。这里用一个探针中间件在
`http.response.start` 时刻用独立 session 查询，确认数据已经可见。
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_commit_is_visible_before_response_start(sessionmaker, db_session):
    import httpx
    from fastapi import APIRouter, Depends, FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

    from huntai.app.deps import get_session
    from huntai.app.routing import TransactionalAPIRoute
    from huntai.domains.incidents.models import Incident

    app = FastAPI()
    app.state.sessionmaker = sessionmaker
    router = APIRouter(route_class=TransactionalAPIRoute)

    @router.post("/incidents")
    async def create_incident(session: AsyncSession = Depends(get_session)):
        incident = Incident(
            title="commit-order", severity="P3", status="open", source="manual"
        )
        session.add(incident)
        await session.flush()
        return {"id": incident.id}

    app.include_router(router)

    observed: dict[str, int] = {}

    async def app_with_probe(scope, receive, send):
        async def send_with_probe(message):
            if message["type"] == "http.response.start" and "visible" not in observed:
                async with sessionmaker() as probe:
                    observed["visible"] = await probe.scalar(
                        select(func.count()).select_from(Incident)
                    )
            await send(message)

        await app(scope, receive, send_with_probe)

    transport = httpx.ASGITransport(app=app_with_probe)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/incidents")

    assert response.status_code == 200, response.text
    assert observed.get("visible") == 1, "响应开始发送时事务尚未提交"
