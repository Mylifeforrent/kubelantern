"""应用工厂与入口（04-backend-design §1.3）。

中间件注册顺序（外→内）：request_context → rate_limit(仅 webhook) → 路由。
lifespan 资源：SQLAlchemy engine/sessionmaker、Redis client、arq 池、SSE hub；挂 app.state。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from huntai.app.middleware.request_context import (
    RequestContextMiddleware,
    WebhookRateLimitMiddleware,
)
from huntai.core import context
from huntai.core.config import Settings
from huntai.core.db import create_engine_and_sessionmaker
from huntai.core.errors import ProblemError, problem_body
from huntai.core.logging import setup_logging
from huntai.core.redis import create_arq_pool, create_redis_client

logger = logging.getLogger("huntai.app")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    setup_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine, sessionmaker = create_engine_and_sessionmaker(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
        )
        app.state.settings = settings
        app.state.sessionmaker = sessionmaker
        app.state.engine = engine
        app.state.redis = create_redis_client(settings.redis_url)
        app.state.arq_pool = await create_arq_pool(settings.redis_url)
        from huntai.realtime.hub import RealtimeHub

        app.state.hub = RealtimeHub(app.state.redis, settings=settings)
        logger.info("huntai api started", extra={"props": {"env": settings.env}})
        try:
            yield
        finally:
            await app.state.arq_pool.aclose()
            await app.state.redis.aclose()
            await engine.dispose()

    app = FastAPI(
        title="huntai-sre API",
        version="0.1.0",
        lifespan=lifespan,
        # 契约 servers: /api/v1；SPA 同源部署，无 CORS 需求（02-architecture §3.4）
    )
    _register_exception_handlers(app)
    app.add_middleware(WebhookRateLimitMiddleware, settings=settings)
    app.add_middleware(RequestContextMiddleware)

    from huntai.app.routers.api import build_api_v1_router

    app.include_router(build_api_v1_router(), prefix="/api/v1")

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict:
        return {"status": "ok"}

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def _problem_handler(request: Request, exc: ProblemError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=problem_body(
                status=exc.status,
                title=exc.title,
                detail=exc.detail,
                code=exc.code,
                instance=str(request.url.path),
                trace_id=context.trace_id.get(),
            ),
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=problem_body(
                status=422,
                title="Validation error",
                detail="请求体校验失败",
                instance=str(request.url.path),
                trace_id=context.trace_id.get(),
                errors=[
                    {"loc": [str(p) for p in e.get("loc", [])], "msg": e.get("msg", "")}
                    for e in exc.errors()
                ],
            ),
            media_type="application/problem+json",
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=problem_body(
                status=exc.status_code,
                title=str(exc.detail) if exc.status_code < 500 else "Internal server error",
                instance=str(request.url.path),
                trace_id=context.trace_id.get(),
            ),
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return JSONResponse(
            status_code=500,
            content=problem_body(
                status=500,
                title="Internal server error",
                instance=str(request.url.path),
                trace_id=context.trace_id.get(),
            ),
            media_type="application/problem+json",
        )


def run() -> None:
    """huntai-api 入口脚本。"""
    import uvicorn

    settings = Settings()
    uvicorn.run(
        "huntai.app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level,
    )


app = create_app()
