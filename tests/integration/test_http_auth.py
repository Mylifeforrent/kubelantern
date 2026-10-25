"""集成测试：HTTP 层（认证、权限矩阵、problem 错误结构、分页包裹）。"""

from __future__ import annotations

import pytest

from tests.conftest import seed_roles, seed_user

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.fixture()
async def client(sessionmaker, db_session, test_settings):
    import httpx

    from huntai.app.main import create_app
    from tests.conftest import FakeArqPool

    app = create_app(test_settings)
    app.state.settings = test_settings  # ASGITransport 不跑 lifespan，手动装配 state
    app.state.sessionmaker = sessionmaker
    app.state.arq_pool = FakeArqPool()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


async def _login(client, username: str, password: str = "test-password"):
    response = await client.post("/api/v1/auth/token", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_login_and_me(db_session, client):
    await seed_roles(db_session)
    await seed_user(db_session, "admin", "admin")
    headers = await _login(client, "admin")
    me = await client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200
    body = me.json()
    assert body["username"] == "admin"
    assert "roles" in body and body["roles"][0]["role_code"] == "admin"


async def test_login_wrong_password_returns_401_problem(db_session, client):
    from tests.conftest import seed_roles, seed_user

    await seed_roles(db_session)
    await seed_user(db_session, "admin", "admin")
    response = await client.post(
        "/api/v1/auth/token", json={"username": "admin", "password": "wrong"}
    )
    assert response.status_code == 401
    body = response.json()
    assert body["status"] == 401 and "title" in body  # RFC 7807


async def test_permission_matrix_enforced(db_session, client):
    await seed_roles(db_session)
    await seed_user(db_session, "admin", "admin")
    await seed_user(db_session, "viewer", "viewer")
    await seed_user(db_session, "dev", "developer", team="platform", team_scope="platform")

    admin_headers = await _login(client, "admin")
    viewer_headers = await _login(client, "viewer")
    dev_headers = await _login(client, "dev")

    # viewer 无告警读权限 → 403 problem
    denied = await client.get("/api/v1/alerts", headers=viewer_headers)
    assert denied.status_code == 403
    assert denied.json()["status"] == 403

    # developer T 权限可用（无 team_scope 时 403）
    no_scope = await client.get("/api/v1/alerts", headers=dev_headers)
    assert no_scope.status_code == 200

    # 未认证 → 401
    anonymous = await client.get("/api/v1/alerts")
    assert anonymous.status_code == 401

    # admin 可读用户列表（分页包裹）
    users = await client.get("/api/v1/users", headers=admin_headers)
    assert users.status_code == 200
    payload = users.json()
    assert set(payload) == {"items", "total", "offset", "limit"}
    assert payload["total"] >= 3


async def test_validation_error_is_problem_422(db_session, client):
    await seed_roles(db_session)
    await seed_user(db_session, "admin", "admin")
    headers = await _login(client, "admin")
    response = await client.post(
        "/api/v1/users", headers=headers, json={"username": "x"}  # 缺 email/display_name
    )
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == 422 and body["title"] == "Validation error"
