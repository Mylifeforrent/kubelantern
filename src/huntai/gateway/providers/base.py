"""ModelProvider 抽象（BR-12：本地优先、默认不出域）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class Completion:
    text: str
    tokens_in: int
    tokens_out: int


class ModelProvider(Protocol):
    name: str
    is_local: bool

    async def complete(self, prompt: str, *, max_tokens: int) -> Completion: ...
