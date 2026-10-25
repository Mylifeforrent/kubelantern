"""结构化 JSON 日志（标准库实现；structlog 为候选依赖，P0 评审通过前不引入）。

字段基线：timestamp / level / logger / event / trace_id / actor / resource。
日志红线：凭据值、secret_ref 解析结果、掩码原值、明文 prompt、.env 值禁止入日志。
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from huntai.core import context

_REDACT_KEYS = {
    "password",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "encrypted_original",
    "prompt",
    "raw_secret",
    "mask_original",
}


def _redact(payload: dict) -> dict:
    return {
        k: ("[REDACTED]" if any(part in k.lower() for part in _REDACT_KEYS) else v)
        for k, v in payload.items()
    }


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        if context.trace_id.get():
            payload["trace_id"] = context.trace_id.get()
        actor = context.actor_id.get()
        if actor is not None:
            payload["actor"] = str(actor)
        elif context.actor_name.get():
            payload["actor"] = f"system:{context.actor_name.get()}"
        extra = getattr(record, "props", None)
        if isinstance(extra, dict):
            payload.update(_redact(extra))
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "info", fmt: str = "json") -> None:
    handler = logging.StreamHandler()
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
