"""路由聚合：/api/v1 全量路由在此注册（新增域路由时在此追加）。"""

from __future__ import annotations

from fastapi import APIRouter


def build_api_v1_router() -> APIRouter:
    from huntai.app.routers.ai_tasks import router as ai_tasks_router
    from huntai.app.routers.alerts import router as alerts_router
    from huntai.app.routers.auth import router as auth_router
    from huntai.app.routers.clusters import router as clusters_router
    from huntai.app.routers.incidents import router as incidents_router
    from huntai.app.routers.inspections import router as inspections_router
    from huntai.app.routers.oncall import router as oncall_router
    from huntai.app.routers.stream import router as stream_router

    api = APIRouter()
    api.include_router(auth_router)
    api.include_router(clusters_router)
    api.include_router(alerts_router)
    api.include_router(incidents_router)
    api.include_router(inspections_router)
    api.include_router(ai_tasks_router)
    api.include_router(oncall_router)
    api.include_router(stream_router)
    return api
