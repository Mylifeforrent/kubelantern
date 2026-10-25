"""权限矩阵：以契约 x-roles 标注机械推导（[ASSUMPTION] 结构，P0 权限模块详设评审）。

Y 允许 / N 拒绝 / T 限本团队（行级过滤）。资源-动作命名与路由 require_permission 一一对应。
"""

from __future__ import annotations

ROLE_NAMES = {
    "admin": "管理员",
    "sre": "SRE 工程师",
    "oncall_manager": "值班经理",
    "developer": "研发（限本团队）",
    "viewer": "只读观察者",
}

_Y = "Y"
_T = "T"
_N = "N"

ROLE_PERMISSIONS: dict[str, dict[str, dict[str, str]]] = {
    "admin": {},  # 下方由 _expand 生成全 Y
    "sre": {
        "users": {"read": _N, "write": _N},
        "roles": {"read": _N},
        "audit_logs": {"read": _N},
        "clusters": {"read": _Y, "write": _N, "test": _N},
        "providers": {"read": _N, "write": _N},
        "alerts": {"read": _Y, "acknowledge": _Y, "close": _Y, "convert": _Y},
        "enrichment_rules": {"read": _Y, "write": _Y},
        "correlation_rules": {"read": _Y, "write": _Y},
        "maintenance_windows": {"read": _Y, "write": _Y},
        "incident_candidates": {"read": _Y, "decide": _Y},
        "incidents": {
            "read": _Y,
            "write": _Y,
            "transition": _Y,
            "status_page": _Y,
            "postmortem_read": _Y,
            "postmortem_write": _Y,
        },
        "status_page": {"read": _Y, "write": _Y},
        "inspection_rules": {"read": _Y, "write": _Y},
        "inspection_policies": {"read": _Y, "write": _Y, "run": _Y},
        "inspection_runs": {"read": _Y},
        "findings": {"read": _Y, "acknowledge": _Y, "ignore": _Y, "reopen": _Y, "explain": _Y},
        "ai_tasks": {"read": _T, "approve": _T, "cancel": _T, "call_logs": _T},
        "oncall_schedules": {"read": _N, "write": _N},
        "escalation_policies": {"read": _N, "write": _N},
        "notification_records": {"read": _Y},
        "workflows": {"read": _Y, "write": _Y},
        "workflow_runs": {"read": _Y, "write": _Y},
    },
    "oncall_manager": {
        "users": {"read": _N, "write": _N},
        "roles": {"read": _N},
        "audit_logs": {"read": _N},
        "clusters": {"read": _N, "write": _N, "test": _N},
        "providers": {"read": _N, "write": _N},
        "alerts": {"read": _Y, "acknowledge": _N, "close": _N, "convert": _N},
        "enrichment_rules": {"read": _N, "write": _N},
        "correlation_rules": {"read": _N, "write": _N},
        "maintenance_windows": {"read": _N, "write": _N},
        "incident_candidates": {"read": _Y, "decide": _N},
        "incidents": {
            "read": _Y,
            "write": _N,
            "transition": _N,
            "status_page": _N,
            "postmortem_read": _N,
            "postmortem_write": _N,
        },
        "status_page": {"read": _Y, "write": _N},
        "inspection_rules": {"read": _N, "write": _N},
        "inspection_policies": {"read": _N, "write": _N, "run": _N},
        "inspection_runs": {"read": _N},
        "findings": {"read": _N, "acknowledge": _N, "ignore": _N, "reopen": _N, "explain": _N},
        "ai_tasks": {"read": _N, "approve": _N, "cancel": _N, "call_logs": _N},
        "oncall_schedules": {"read": _Y, "write": _Y},
        "escalation_policies": {"read": _Y, "write": _Y},
        "notification_records": {"read": _Y},
        "workflows": {"read": _N, "write": _N},
        "workflow_runs": {"read": _N, "write": _N},
    },
    "developer": {
        "users": {"read": _N, "write": _N},
        "roles": {"read": _N},
        "audit_logs": {"read": _N},
        "clusters": {"read": _N, "write": _N, "test": _N},
        "providers": {"read": _N, "write": _N},
        "alerts": {"read": _T, "acknowledge": _T, "close": _N, "convert": _T},
        "enrichment_rules": {"read": _N, "write": _N},
        "correlation_rules": {"read": _N, "write": _N},
        "maintenance_windows": {"read": _N, "write": _N},
        "incident_candidates": {"read": _T, "decide": _T},
        "incidents": {
            "read": _T,
            "write": _T,
            "transition": _T,
            "status_page": _N,
            "postmortem_read": _T,
            "postmortem_write": _N,
        },
        "status_page": {"read": _Y, "write": _N},
        "inspection_rules": {"read": _Y, "write": _N},
        "inspection_policies": {"read": _N, "write": _N, "run": _N},
        "inspection_runs": {"read": _Y},
        # findings 团队数据边界 [TBD-UX]：findings 无团队列，T 暂按放行全量（不阻断看板）
        "findings": {"read": _T, "acknowledge": _T, "ignore": _N, "reopen": _N, "explain": _N},
        "ai_tasks": {"read": _N, "approve": _N, "cancel": _N, "call_logs": _N},
        "oncall_schedules": {"read": _N, "write": _N},
        "escalation_policies": {"read": _N, "write": _N},
        "notification_records": {"read": _N},
        "workflows": {"read": _N, "write": _N},
        "workflow_runs": {"read": _N, "write": _N},
    },
    "viewer": {
        "users": {"read": _N, "write": _N},
        "roles": {"read": _N},
        "audit_logs": {"read": _N},
        "clusters": {"read": _N, "write": _N, "test": _N},
        "providers": {"read": _N, "write": _N},
        "alerts": {"read": _N, "acknowledge": _N, "close": _N, "convert": _N},
        "enrichment_rules": {"read": _N, "write": _N},
        "correlation_rules": {"read": _N, "write": _N},
        "maintenance_windows": {"read": _N, "write": _N},
        "incident_candidates": {"read": _N, "decide": _N},
        "incidents": {
            "read": _N,
            "write": _N,
            "transition": _N,
            "status_page": _N,
            "postmortem_read": _N,
            "postmortem_write": _N,
        },
        # viewer 仅可见 public 条目（服务层过滤，矩阵层面允许 read）
        "status_page": {"read": _Y, "write": _N},
        "inspection_rules": {"read": _N, "write": _N},
        "inspection_policies": {"read": _N, "write": _N, "run": _N},
        "inspection_runs": {"read": _N},
        "findings": {"read": _N, "acknowledge": _N, "ignore": _N, "reopen": _N, "explain": _N},
        "ai_tasks": {"read": _N, "approve": _N, "cancel": _N, "call_logs": _N},
        "oncall_schedules": {"read": _N, "write": _N},
        "escalation_policies": {"read": _N, "write": _N},
        "notification_records": {"read": _N},
        "workflows": {"read": _N, "write": _N},
        "workflow_runs": {"read": _N, "write": _N},
    },
}


def _expand_admin() -> None:
    admin: dict[str, dict[str, str]] = {}
    for role, matrix in ROLE_PERMISSIONS.items():
        if role == "admin":
            continue
        for resource, actions in matrix.items():
            admin.setdefault(resource, {}).update({action: _Y for action in actions})
    ROLE_PERMISSIONS["admin"] = dict(sorted(admin.items()))


_expand_admin()


def all_resources() -> dict[str, list[str]]:
    """资源 -> 动作全集（can() 全组合单测的遍历基）。"""
    merged: dict[str, set[str]] = {}
    for matrix in ROLE_PERMISSIONS.values():
        for resource, actions in matrix.items():
            merged.setdefault(resource, set()).update(actions)
    return {r: sorted(a) for r, a in sorted(merged.items())}
