"""pytest 公共夹具。

- async 测试走 anyio 自带插件（pytest-asyncio 为候选依赖，不引入）。
- integration 标记：需要 compose 起的 PG/Redis；不可达时自动 skip。
- DB 夹具放根 conftest，integration 与 e2e_flows 共用；anyio 每用例独立事件循环，
  asyncpg 连接不可跨循环复用，因此 engine 按用例创建。
"""

from __future__ import annotations

import base64
import os
import socket
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

os.environ.setdefault("HUNTAI_MASK_KEY", base64.urlsafe_b64encode(b"x" * 32).decode())
os.environ.setdefault("HUNTAI_AUTH_SECRET", "test-auth-secret-material")
os.environ.setdefault("HUNTAI_DEV_AUTH_PASSWORD", "test-password")

PG_PORT = int(os.environ.get("HUNTAI_TEST_PG_PORT", "5433"))
REDIS_PORT = int(os.environ.get("HUNTAI_TEST_REDIS_PORT", "6380"))
TEST_DB_URL = os.environ.get(
    "HUNTAI_TEST_DATABASE_URL",
    f"postgresql+asyncpg://huntai:your-password@127.0.0.1:{PG_PORT}/huntai_test",
)
TEST_REDIS_URL = os.environ.get("HUNTAI_TEST_REDIS_URL", f"redis://127.0.0.1:{REDIS_PORT}/1")


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(config, items):
    """PG/Redis 不可达时跳过 integration 用例（单测始终可跑）。"""
    if _port_open(PG_PORT) and _port_open(REDIS_PORT):
        return
    skip = pytest.mark.skip(reason="compose PG/Redis 未启动（docker compose up -d postgres redis）")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture()
def test_settings():
    from huntai.core.config import Settings

    return Settings(
        database_url=TEST_DB_URL,
        redis_url=TEST_REDIS_URL,
        dev_auth_password="test-password",
        auth_secret="test-auth-secret-material",
    )


_TRUNCATE_TABLES = (
    "audit_logs, ai_call_logs, ai_explanations, ai_mask_mappings, ai_tasks,"
    " alerts, correlation_rules, credentials, enrichment_rules, findings, incident_alerts,"
    " incident_candidates, incidents, inspection_policies, inspection_policy_rules,"
    " inspection_rules, inspection_runs, maintenance_windows, notification_records,"
    " oncall_schedules, escalation_policies, postmortem_action_items, postmortems,"
    " providers, roles, status_page_entries, status_page_updates, user_roles, users,"
    " workflow_runs, workflows"
)


@pytest.fixture()
async def sessionmaker() -> AsyncIterator[async_sessionmaker]:
    from huntai.core.db import create_engine_and_sessionmaker

    engine, maker = create_engine_and_sessionmaker(TEST_DB_URL, pool_size=5, max_overflow=5)
    try:
        yield maker
    finally:
        await engine.dispose()


@pytest.fixture()
async def db_session(sessionmaker: async_sessionmaker) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        await session.execute(text(f"TRUNCATE TABLE {_TRUNCATE_TABLES} RESTART IDENTITY CASCADE"))
        await session.commit()
        try:
            yield session
        finally:
            await session.rollback()


async def seed_roles(session: AsyncSession) -> None:
    from sqlalchemy import select

    from huntai.domains.iam.models import Role
    from huntai.domains.iam.permissions import ROLE_NAMES, ROLE_PERMISSIONS

    for code, name in ROLE_NAMES.items():
        existing = (
            await session.execute(select(Role).where(Role.code == code))
        ).scalar_one_or_none()
        if existing is None:
            session.add(Role(code=code, name=name, permissions=ROLE_PERMISSIONS[code]))
    await session.commit()


async def seed_user(
    session: AsyncSession, username: str, role_code: str, *,
    team: str | None = None, team_scope: str | None = None,
) -> int:
    from sqlalchemy import select

    from huntai.domains.iam.models import Role, User, UserRoleGrant

    user = User(username=username, email=f"{username}@test.example", display_name=username, team=team)
    session.add(user)
    await session.flush()
    role = (await session.execute(select(Role).where(Role.code == role_code))).scalar_one()
    session.add(UserRoleGrant(user_id=user.id, role_id=role.id, team_scope=team_scope))
    await session.commit()
    return user.id


class FakeArqPool:
    """记录入队调用的假池（集成断言用）。"""

    def __init__(self) -> None:
        self.jobs: list[tuple] = []
        self.deferred: list[dict] = []

    async def enqueue_job(self, name, *args, _queue_name=None, _defer_by=None):
        self.jobs.append((name, args, _queue_name))
        if _defer_by is not None:
            self.deferred.append({"name": name, "args": args, "defer_by": _defer_by})
        return f"job-{len(self.jobs)}"


def capture_enqueue(jobs: list):
    async def enqueue(job_name: str, *args, **kwargs):
        jobs.append((job_name, args))
        return f"job-{len(jobs)}"

    return enqueue


def capture_publish(events: list):
    async def publish(event) -> None:
        events.append(event)

    return publish
