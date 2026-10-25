"""本地模型 Provider（Ollama / vLLM 兼容端点，BR-12 默认仅本地）。"""

from __future__ import annotations

import httpx

from huntai.core.config import Settings
from huntai.gateway.providers.base import Completion


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class LocalOllamaProvider:
    name = "local"
    is_local = True

    def __init__(self, settings: Settings) -> None:
        self._endpoint = settings.ai_local_endpoint.rstrip("/")
        self._model = settings.ai_local_model
        self._timeout = 60.0

    async def complete(self, prompt: str, *, max_tokens: int) -> Completion:
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._endpoint}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        text = str((data.get("message") or {}).get("content", ""))
        return Completion(
            text=text,
            tokens_in=int(data.get("prompt_eval_count") or _estimate_tokens(prompt)),
            tokens_out=int(data.get("eval_count") or _estimate_tokens(text)),
        )
