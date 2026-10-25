"""HTTP 中间件：request_context（trace_id/actor/访问日志）与 webhook 限流。"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from huntai.core import context
from huntai.core.config import Settings
from huntai.core.errors import problem_body

_access_logger = logging.getLogger("huntai.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """生成/透传 trace_id，产出访问日志（04-backend-design §6.1）。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        context.trace_id.set(trace)
        context.actor_type.set("user")
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            _access_logger.exception(
                "request failed",
                extra={"props": {
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                }},
            )
            raise
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = trace
        _access_logger.info(
            "request completed",
            extra={"props": {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            }},
        )
        return response


class _TokenBucket:
    """进程内令牌桶（webhook 每 Provider 独立限流，[ASSUMPTION] 阈值 P0 压测定）。"""

    def __init__(self, capacity: float, rate_per_second: float) -> None:
        self.capacity = capacity
        self.rate = rate_per_second
        self._state: dict[str, tuple[float, float]] = {}

    def allow(self, key: str, now: float) -> bool:
        tokens, last = self._state.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.rate)
        if tokens >= 1.0:
            self._state[key] = (tokens - 1.0, now)
            return True
        self._state[key] = (tokens, now)
        return False


class WebhookRateLimitMiddleware(BaseHTTPMiddleware):
    """仅作用于 POST /api/v1/alerts/webhook/*；超限仍执行落盘，但响应改写 429（HLD §5.3）。"""

    def __init__(self, app, *, settings: Settings) -> None:
        super().__init__(app)
        self._bucket = _TokenBucket(
            settings.rate_limit_webhook_capacity,
            settings.rate_limit_webhook_rate_per_second,
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if not (request.method == "POST" and path.startswith("/api/v1/alerts/webhook/")):
            return await call_next(request)
        provider_key = path.rsplit("/", 1)[-1]
        if self._bucket.allow(provider_key, time.time()):
            return await call_next(request)
        await call_next(request)  # 超限仍落盘（不丢告警）
        return JSONResponse(
            status_code=429,
            content=problem_body(
                status=429,
                title="Too many requests",
                code="RATE_LIMITED",
                detail=f"webhook {provider_key} 触发限流；请求已落盘待回放",
                trace_id=context.trace_id.get(),
            ),
            media_type="application/problem+json",
        )
