"""运行配置：pydantic-settings 读仓库根 .env，前缀 HUNTAI_（04-backend-design §6.3）。

启动即 fail-fast 校验连接串格式；一切密钥类值只允许出现在 .env 或密钥管理服务。
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Queue:
    """5 条队列名常量（HLD §6.1），禁止散落字符串。"""

    ALERT_PIPELINE = "q-alert-pipeline"
    NOTIFICATION = "q-notification"
    ESCALATION = "q-escalation"
    INSPECTION = "q-inspection"
    AI = "q-ai"

    ALL = (ALERT_PIPELINE, NOTIFICATION, ESCALATION, INSPECTION, AI)


# 任务名 → 队列（入队侧统一路由；显式 _queue 优先）
QUEUE_BY_JOB = {
    "alert.process_pipeline": Queue.ALERT_PIPELINE,
    "replay.scan": Queue.ALERT_PIPELINE,
    "maintenance.close_windows": Queue.ALERT_PIPELINE,
    "notify.dispatch": Queue.NOTIFICATION,
    "escalation.check_ack": Queue.ESCALATION,
    "inspection.run": Queue.INSPECTION,
    "inspection.schedule_tick": Queue.INSPECTION,
    "cluster.probe": Queue.INSPECTION,
    "ai.execute_task": Queue.AI,
    "approval.scan_timeouts": Queue.AI,
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="HUNTAI_", extra="ignore")

    env: str = "dev"

    api_host: str = "127.0.0.1"
    api_port: int = 8000

    database_url: str = "postgresql+asyncpg://huntai:your-password@127.0.0.1:5433/huntai"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    redis_url: str = "redis://127.0.0.1:6380/0"

    log_level: str = "info"
    log_format: str = "json"

    # dev 占位认证（[TBD-INFRA]：SSO/LDAP/本地定稿后替换 core/security.py 实现）
    auth_secret: str = "your-auth-secret"
    auth_token_ttl_minutes: int = 720
    dev_auth_password: str = "your-dev-password"

    # 密钥后端：dev 仅支持 env:VAR 引用；生产后端 [TBD-INFRA]
    secret_backend: str = "env"
    mask_encryption_key_ref: str = "env:HUNTAI_MASK_KEY"

    # AI 网关（BR-03/BR-12/ADR-0005）
    ai_local_endpoint: str = "http://127.0.0.1:11434"
    ai_local_model: str = "llama3.1"
    ai_egress_enabled: bool = False
    ai_external_url: str | None = None
    ai_external_model: str = "gpt-4o-mini"
    ai_external_key_ref: str | None = None
    ai_budget_default_calls: int = 40
    ai_budget_default_tokens: int = 100_000
    ai_circuit_failures: int = 5
    ai_circuit_reset_seconds: int = 60
    approval_timeout_minutes: int = 30

    # 管道 / 限流 / SSE（阈值 [ASSUMPTION]，P0 压测校准）
    replay_stale_seconds: int = 60
    replay_scan_seconds: int = 30
    rate_limit_webhook_capacity: int = 100
    rate_limit_webhook_rate_per_second: float = 10.0
    sse_heartbeat_seconds: int = 15
    stream_retention_minutes: int = 30

    @field_validator("database_url")
    @classmethod
    def _check_database_url(cls, v: str) -> str:
        if not v.startswith(("postgresql+asyncpg://", "postgresql://")):
            raise ValueError("database_url 必须是 postgresql(+asyncpg):// 连接串")
        return v

    @field_validator("redis_url")
    @classmethod
    def _check_redis_url(cls, v: str) -> str:
        if not v.startswith("redis://"):
            raise ValueError("redis_url 必须是 redis:// 连接串")
        return v
