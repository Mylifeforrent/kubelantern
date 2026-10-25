"""HuntAI SRE kind 演示：Python / FastAPI 库存服务。

CRASH_ON_START=1 时进程立即退出，用于制造 CrashLoopBackOff 故障场景。
"""

from __future__ import annotations

import os
import sys
import time
from datetime import UTC, datetime
from typing import Any

if os.getenv("CRASH_ON_START") == "1":
    print("injected crash: CRASH_ON_START=1", flush=True)
    sys.exit(1)

from fastapi import FastAPI  # noqa: E402  (故障注入必须先执行)
from fastapi.responses import JSONResponse  # noqa: E402

app = FastAPI(title="python-inventory-service", version="0.1.0")

_INVENTORY: list[dict[str, Any]] = [
    {"sku": "SKU-001", "name": "机械键盘", "quantity": 42, "warehouse": "cn-east-1"},
    {"sku": "SKU-002", "name": "显示器", "quantity": 7, "warehouse": "cn-east-2"},
]


def _now() -> str:
    return datetime.now(UTC).isoformat()


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"status": "ok", "service": "python-inventory-service", "checked_at": _now()}


@app.get("/api/inventory")
def list_inventory() -> dict[str, Any]:
    return {
        "service": "python-inventory-service",
        "language": "python",
        "items": _INVENTORY,
        "count": len(_INVENTORY),
        "checked_at": _now(),
    }


@app.post("/api/inventory", status_code=201)
def create_item(payload: dict[str, Any]) -> dict[str, Any]:
    item = {
        "sku": str(payload.get("sku", "SKU-DEMO")),
        "name": str(payload.get("name", "演示物料")),
        "quantity": int(payload.get("quantity", 0)),
        "warehouse": str(payload.get("warehouse", "cn-east-1")),
    }
    _INVENTORY.append(item)
    return item


@app.get("/api/inventory/boom")
def boom() -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "service": "python-inventory-service",
            "error": "injected 500 for HuntAI demo",
            "checked_at": _now(),
        },
    )


@app.get("/api/inventory/slow")
def slow(ms: int = 1500) -> dict[str, Any]:
    bounded = max(0, min(ms, 10_000))
    time.sleep(bounded / 1000)
    return {"service": "python-inventory-service", "delay_ms": bounded, "checked_at": _now()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
