"""AIGateway 主流程：脱敏 → 路由 → 预算 → 调用 → 回填 → 审计（04-backend-design §3.4）。

任务状态机：created → sanitizing → running → (pending_approval) → completed / failed /
budget_exceeded（8 态禁改）。BR-03 超限 graceful 终止：is_partial=true + 显式标注未完成。
"""

from __future__ import annotations

import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from huntai.core.config import Settings
from huntai.core.db import utcnow
from huntai.core.masks import mask_decrypt, mask_encrypt
from huntai.domains.ai import repository as ai_repo
from huntai.domains.ai import service as ai_service
from huntai.domains.ai.models import AITaskStatus, AITaskType
from huntai.domains.iam.service import record_audit
from huntai.gateway import router as model_router
from huntai.gateway import sanitizer
from huntai.gateway.budget import check_before_call
from huntai.gateway.circuit import CircuitBreaker

logger = logging.getLogger("huntai.gateway")

_MAX_OUTPUT_TOKENS_PER_CALL = 2048


class AIGateway:
    def __init__(self, settings: Settings, *, circuit: CircuitBreaker | None = None) -> None:
        self.settings = settings
        self.circuit = circuit or CircuitBreaker(
            failure_threshold=settings.ai_circuit_failures,
            reset_seconds=settings.ai_circuit_reset_seconds,
        )
        self._providers = model_router.build_providers(settings)

    async def execute_task(
        self, session: AsyncSession, task_id: int, *, publish=None
    ):
        task = await ai_repo.get_task(session, task_id)
        if task is None:
            return None
        if task.status not in {AITaskStatus.CREATED, AITaskStatus.PENDING_APPROVAL}:
            return task  # 幂等：非起始态不重复执行

        # sanitizing：构建上下文并脱敏（出域文本仅含占位符）
        task.status = AITaskStatus.SANITIZING
        await session.flush()
        prompt_plain, known_terms = await self._build_context(session, task)
        sanitized = sanitizer.sanitize(prompt_plain, known_terms=known_terms)
        for mapping in sanitized.mappings:
            from sqlalchemy import select

            from huntai.domains.ai.models import AIMaskMapping

            exists = (
                await session.execute(
                    select(AIMaskMapping).where(
                        AIMaskMapping.task_id == task.id,
                        AIMaskMapping.placeholder == mapping.placeholder,
                    )
                )
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    AIMaskMapping(
                        task_id=task.id,
                        placeholder=mapping.placeholder,
                        kind=mapping.kind,
                        encrypted_original=mask_encrypt(
                            mapping.original, key_ref=self.settings.mask_encryption_key_ref
                        ),
                    )
                )
        await session.flush()

        task.status = AITaskStatus.RUNNING
        await session.flush()

        provider = self._providers.get(model_router.route(task.type.value))
        if provider is None or not self.circuit.allow():
            await self._finish_noai(session, task, publish=publish)
            return task

        # 预算检查（每次调用前）
        verdict = check_before_call(
            task.budget, calls_used=task.calls_used, tokens_used=task.tokens_used
        )
        if not verdict.allowed:
            task.status = AITaskStatus.BUDGET_EXCEEDED
            task.is_partial = True
            task.error = verdict.reason
            task.finished_at = utcnow()
            await record_audit(
                session, action="ai_task.budget_exceeded", resource_type="ai_tasks",
                resource_id=task.id, detail={"calls_used": task.calls_used}, actor_type="system",
            )
            await session.flush()
            return task

        started = time.perf_counter()
        try:
            completion = await provider.complete(
                sanitized.text, max_tokens=_MAX_OUTPUT_TOKENS_PER_CALL
            )
        except Exception as exc:  # noqa: BLE001 - 模型不可用属正常降级路径
            transition = self.circuit.record_failure()
            latency_ms = int((time.perf_counter() - started) * 1000)
            ai_service.append_call_log(
                session, task_id=task.id, model=provider.name,
                prompt_digest=sanitizer.digest(sanitized.text), tokens_in=0, tokens_out=0,
                latency_ms=latency_ms, result_code="error", error=str(exc)[:500],
            )
            await ai_repo.consume_budget(session, task.id, calls=1)
            await session.flush()
            if transition and publish is not None:
                from huntai.realtime.hub import RealtimeEvent

                await publish(
                    RealtimeEvent(topic="system", name="system.noai", resource="system", resource_id=0)
                )
            await self._finish_noai(session, task, publish=publish)
            return task

        self.circuit.record_success()
        latency_ms = int((time.perf_counter() - started) * 1000)
        ai_service.append_call_log(
            session, task_id=task.id, model=provider.name,
            prompt_digest=sanitizer.digest(sanitized.text),
            tokens_in=completion.tokens_in, tokens_out=completion.tokens_out,
            latency_ms=latency_ms, result_code="ok",
        )
        await ai_repo.consume_budget(
            session, task.id, calls=1, tokens=completion.tokens_out
        )

        # 回填：还原占位符后落本地库（还原结果不出域，BR-01）
        restored = sanitizer.restore(completion.text, sanitized.mappings)
        if task.type == AITaskType.EXPLAIN and task.finding_id is not None:
            existing = await ai_repo.get_explanation_for_finding(session, task.finding_id)
            ai_service.upsert_explanation(
                session, existing, finding_id=task.finding_id, task_id=task.id,
                sanitized_input_digest=sanitizer.digest(sanitized.text),
                output={"diagnosis": restored}, model=provider.name, tokens=completion.tokens_out,
            )
            task.result = {"finding_id": task.finding_id}
        else:
            task.result = {"output": restored}
        task.status = AITaskStatus.COMPLETED
        task.finished_at = utcnow()
        await record_audit(
            session, action="ai_task.complete", resource_type="ai_tasks", resource_id=task.id,
            detail={"tokens_out": completion.tokens_out}, actor_type="system",
            cost={"tokens": completion.tokens_out},
        )
        await session.flush()
        if publish is not None:
            from huntai.realtime.hub import RealtimeEvent

            await publish(
                RealtimeEvent(topic="ai-tasks", name="ai_task.updated", resource="ai_task", resource_id=task.id)
            )
        return task

    async def _finish_noai(self, session: AsyncSession, task, *, publish=None) -> None:
        """NoAI 熔断语义：A1 落 NoAI 结果（透出 raw_error），A2/A3 失败落库可重发。"""
        task.status = AITaskStatus.FAILED
        task.error = "noai: 模型不可用或熔断开路（ADR-0005）"
        task.finished_at = utcnow()
        if task.type == AITaskType.EXPLAIN and task.finding_id is not None:
            existing = await ai_repo.get_explanation_for_finding(session, task.finding_id)
            ai_service.upsert_explanation(
                session, existing, finding_id=task.finding_id, task_id=task.id,
                sanitized_input_digest="noai",
                output={"noai": True, "raw_error": task.error}, model="noai", tokens=0,
            )
        await record_audit(
            session, action="ai_task.noai", resource_type="ai_tasks", resource_id=task.id,
            detail={}, actor_type="system",
        )
        await session.flush()
        if publish is not None:
            from huntai.realtime.hub import RealtimeEvent

            await publish(
                RealtimeEvent(topic="ai-tasks", name="ai_task.updated", resource="ai_task", resource_id=task.id)
            )

    async def _build_context(self, session: AsyncSession, task) -> tuple[str, dict[str, str]]:
        """按任务类型构建 prompt 明文与已知敏感词（namespace/pod 名）。"""
        from huntai.domains.inspections import repository as inspection_repo

        known: dict[str, str] = {}
        if task.type == AITaskType.EXPLAIN and task.finding_id is not None:
            finding = await inspection_repo.get_finding(session, task.finding_id)
            if finding is not None:
                ref = finding.resource_ref or {}
                for key, kind in (("namespace", "namespace"), ("name", "pod")):
                    if ref.get(key):
                        known[str(ref[key])] = kind
                body = (
                    f"Kubernetes 巡检发现异常，请给出诊断与修复建议。\n"
                    f"规则: {finding.rule_code}\n"
                    f"资源: {ref.get('kind')} {ref.get('namespace', '')}/{ref.get('name', '')}\n"
                    f"错误: {finding.raw_error}"
                )
                return body, known
            return "巡检发现已不存在，请说明无法诊断。", known
        if task.type == AITaskType.INVESTIGATE and task.incident_id is not None:
            from huntai.domains.incidents import repository as incident_repo

            incident = await incident_repo.get_incident(session, task.incident_id)
            title = incident.title if incident else str(task.incident_id)
            return f"事件调查：{title}。请输出根因假设与下一步排查动作清单。", known
        description = (task.context_refs or {}).get("description", "")
        return (
            f"根据以下描述生成一个运维 Workflow YAML 草稿（步骤：诊断→处置→通知）：\n{description}",
            known,
        )


def decrypt_mapping(blob: bytes, *, settings: Settings) -> str:
    """测试与审计用途：解密掩码映射（仅本地，不外发）。"""
    return mask_decrypt(blob, key_ref=settings.mask_encryption_key_ref)
