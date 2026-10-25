"""5 条队列的 WorkerSettings（队列名常量收敛 core/config，不新增队列名，HLD §6.1）。"""

from __future__ import annotations

import sys

from arq import cron
from arq.connections import RedisSettings

from huntai.core.config import Queue, Settings
from huntai.workers.tasks.alert_pipeline import (
    alert_process_pipeline,
    maintenance_close_windows,
    replay_scan,
)
from huntai.workers.tasks.ai_tasks import ai_execute_task, approval_scan_timeouts
from huntai.workers.tasks.inspection import cluster_probe, inspection_run, inspection_schedule_tick
from huntai.workers.tasks.notification import escalation_check_ack, notify_dispatch

_JOB_TIMEOUT_SECONDS = 60  # [ASSUMPTION] P0 压测校准
# arq 约定：redis_settings 为类属性实例（worker 进程 import 时解析 .env，启动即 fail-fast）
_REDIS_SETTINGS = RedisSettings.from_dsn(Settings().redis_url)


class BaseWorkerSettings:
    functions: list = []
    cron_jobs: list = []
    job_timeout = _JOB_TIMEOUT_SECONDS
    max_tries = 3
    redis_settings = _REDIS_SETTINGS


class AlertPipelineWorker(BaseWorkerSettings):
    """q-alert-pipeline（高）：管道 + 回放 + 维护窗口扫描。"""

    redis_settings = _REDIS_SETTINGS
    max_tries = 3

    queue_name = Queue.ALERT_PIPELINE
    functions = [alert_process_pipeline]
    cron_jobs = [
        cron(replay_scan, minute=None, unique=True),
        cron(maintenance_close_windows, minute=None, unique=True),
    ]


class NotificationWorker(BaseWorkerSettings):
    """q-notification（高）：通知投递。"""

    redis_settings = _REDIS_SETTINGS
    max_tries = 3

    queue_name = Queue.NOTIFICATION
    functions = [notify_dispatch]


class EscalationWorker(BaseWorkerSettings):
    """q-escalation（中）：升级超时。"""

    redis_settings = _REDIS_SETTINGS
    max_tries = 3

    queue_name = Queue.ESCALATION
    functions = [escalation_check_ack]


class InspectionWorker(BaseWorkerSettings):
    """q-inspection（低，长任务）：巡检执行 + 调度 tick + 探活。"""

    redis_settings = _REDIS_SETTINGS
    max_tries = 3

    queue_name = Queue.INSPECTION
    functions = [inspection_run, inspection_schedule_tick, cluster_probe]
    job_timeout = 300  # 巡检长任务放宽（[ASSUMPTION] 压测校准）
    cron_jobs = [
        cron(inspection_schedule_tick, minute=None, unique=True),
        cron(cluster_probe, minute=None, unique=True),
    ]


class AIWorker(BaseWorkerSettings):
    """q-ai（低，长调用）：AI 任务 + 审批超时扫描。"""

    redis_settings = _REDIS_SETTINGS
    max_tries = 3

    queue_name = Queue.AI
    functions = [ai_execute_task, approval_scan_timeouts]
    job_timeout = 300
    max_tries = 1  # AI 任务不框架级自动重试（预算语义 BR-03）
    cron_jobs = [cron(approval_scan_timeouts, minute=None, unique=True)]


WORKER_GROUPS: dict[str, type[BaseWorkerSettings]] = {
    "alert-pipeline": AlertPipelineWorker,
    "notification": NotificationWorker,
    "escalation": EscalationWorker,
    "inspection": InspectionWorker,
    "ai": AIWorker,
}


def main() -> None:
    """huntai-worker <group> 入口：同镜像多角色（ADR-0009 [ASSUMPTION]）。"""
    group = sys.argv[1] if len(sys.argv) > 1 else "alert-pipeline"
    settings_cls = WORKER_GROUPS.get(group)
    if settings_cls is None:
        print(f"未知队列组：{group}（可选：{'/'.join(WORKER_GROUPS)}）", file=sys.stderr)
        raise SystemExit(2)
    from arq.worker import create_worker

    create_worker(settings_cls).run()
