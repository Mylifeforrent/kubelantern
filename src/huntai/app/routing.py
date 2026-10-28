"""路由基类：请求级事务在响应发送前提交（04-backend-design §1.5）。"""

from __future__ import annotations

from fastapi import Request, Response
from fastapi.routing import APIRoute


class TransactionalAPIRoute(APIRoute):
    """在端点返回、响应发送之前提交请求级 session。

    FastAPI 0.117+ 把依赖的退出代码放在响应发送之后执行；若提交只发生在依赖
    teardown，客户端拿到 201 后立刻 GET 新资源会读到未提交数据而 404。
    session 由 get_session 挂在 request.state.db_session，这里在响应发出前提交。
    """

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            response = await original(request)
            session = getattr(request.state, "db_session", None)
            if session is not None:
                await session.commit()
                request.state.db_session_committed = True
            return response

        return handler
