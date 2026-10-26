"""Provider 注册表（模型路由 BR-12：任务类型分级路由，默认值 [TBD-BIZ]）。"""

from __future__ import annotations

from huntai.core.config import Settings
from huntai.gateway.providers.base import Completion, ModelProvider
from huntai.gateway.providers.local import LocalOllamaProvider


def build_providers(settings: Settings) -> dict[str, ModelProvider]:
    providers: dict[str, ModelProvider] = {}
    local = LocalOllamaProvider(settings)
    providers[local.name] = local
    if settings.ai_egress_enabled:
        from huntai.gateway.providers.external import ExternalOpenAICompatProvider

        external = ExternalOpenAICompatProvider(settings)
        providers[external.name] = external
    return providers


def route(task_type: str, settings: Settings | None = None) -> str:
    """任务类型 → Provider 名。

    只有显式开启出域且外部端点/密钥引用完整时才走 external；否则保持 local。
    这样默认行为仍满足 BR-12「不出域」，运维配置 DeepSeek 等 OpenAI 兼容端点后
    AI 任务才会调用外部模型。task_type 预留给后续分级路由（explain 小模型 /
    investigate 强模型）。
    """
    if (
        settings is not None
        and settings.ai_egress_enabled
        and settings.ai_external_url
        and settings.ai_external_key_ref
    ):
        return "external"
    return "local"


_ = Completion
