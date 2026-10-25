"""NoAI 熔断（ADR-0005；参数 [ASSUMPTION] P1 校准）。

- 连续失败 N 次开路；开路时 A1 落 NoAI 结果、A2/A3 拒绝新任务。
- 半开：reset_seconds 后放行一次探测，成功闭合、失败回开路。
- 状态迁移经 SSE system 主题下发（由 gateway 调 publish）。
"""

from __future__ import annotations

import time


class CircuitBreaker:
    def __init__(self, *, failure_threshold: int = 5, reset_seconds: int = 60) -> None:
        self._threshold = failure_threshold
        self._reset_seconds = reset_seconds
        self._failures = 0
        self._opened_at: float | None = None
        self.state = "closed"  # closed / open / half_open

    def allow(self) -> bool:
        if self.state == "closed":
            return True
        if self._opened_at is not None and time.monotonic() - self._opened_at >= self._reset_seconds:
            self.state = "half_open"
            return True
        return self.state == "half_open" and self._failures < self._threshold

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self.state = "closed"

    def record_failure(self) -> str | None:
        """返回值：状态迁移事件名（closed→open / half_open→open），无迁移返回 None。"""
        self._failures += 1
        if self.state == "half_open" or self._failures >= self._threshold:
            transition = None
            if self.state != "open":
                transition = "circuit_opened"
            self.state = "open"
            self._opened_at = time.monotonic()
            return transition
        return None

    @property
    def is_open(self) -> bool:
        return self.state == "open" and not self.allow()
