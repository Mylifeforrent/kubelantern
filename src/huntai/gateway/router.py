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


def route(task_type: str) -> str:
    """任务类型 → Provider 名：explain 小模型、investigate/workflow_gen 强模型（分级路由）。

    当前仅 local 一个已注册 Provider；external 注册后按 [TBD-BIZ] 默认值切换。
    """
    return "local"


_ = Completion
