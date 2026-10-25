"""外部模型 Provider：仅 HUNTAI_AI_EGRESS_ENABLED=true 时注册（BR-12 默认不出域）。"""

from __future__ import annotations

import httpx

from huntai.core.config import Settings
from huntai.core.errors import ProblemError
from huntai.core.secrets import resolve_secret
from huntai.gateway.providers.base import Completion


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class ExternalOpenAICompatProvider:
    name = "external"
    is_local = False

    def __init__(self, settings: Settings) -> None:
        if not settings.ai_egress_enabled or not settings.ai_external_url or not settings.ai_external_key_ref:
            raise ProblemError(status=500, detail="外部模型未启用（BR-12 出域开关默认关闭）")
        self._url = settings.ai_external_url.rstrip("/")
        self._model = settings.ai_external_model
        self._key_material = resolve_secret(settings.ai_external_key_ref)
        self._timeout = 60.0

    async def complete(self, prompt: str, *, max_tokens: int) -> Completion:
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        headers = {"authorization": f"Bearer {self._key_material}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._url}/chat/completions", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()
        text = str((data.get("choices") or [{}])[0].get("message", {}).get("content", ""))
        usage = data.get("usage") or {}
        return Completion(
            text=text,
            tokens_in=int(usage.get("prompt_tokens") or _estimate_tokens(prompt)),
            tokens_out=int(usage.get("completion_tokens") or _estimate_tokens(text)),
        )
