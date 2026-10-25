"""单元测试：can() 权限位对契约 x-roles 全组合（M0 验收项）。"""

import pytest

from huntai.core.security import Principal, merge_permissions
from huntai.domains.iam.permissions import ROLE_PERMISSIONS, all_resources


def _principal(role_code: str, *, team_scope: str | None = None) -> Principal:
    matrix = ROLE_PERMISSIONS[role_code]
    return Principal(
        user_id=1, username="u", email="u@example", display_name="u", team=None,
        is_active=True, created_at=None, updated_at=None, roles=[role_code],
        grants=[{"role_code": role_code, "team_scope": team_scope}],
        permissions=matrix,
    )


# 契约 x-roles 抽样核对（operation → 资源.动作 → 各角色期望 Y/T/N）
CONTRACT_EXPECTATIONS = [
    ("alerts.read", {"admin": "Y", "sre": "Y", "oncall_manager": "Y", "developer": "T", "viewer": "N"}),
    ("alerts.acknowledge", {"admin": "Y", "sre": "Y", "oncall_manager": "N", "developer": "T", "viewer": "N"}),
    ("alerts.close", {"admin": "Y", "sre": "Y", "oncall_manager": "N", "developer": "N", "viewer": "N"}),
    ("clusters.read", {"admin": "Y", "sre": "Y", "oncall_manager": "N", "developer": "N", "viewer": "N"}),
    ("clusters.write", {"admin": "Y", "sre": "N", "oncall_manager": "N", "developer": "N", "viewer": "N"}),
    ("users.read", {"admin": "Y", "sre": "N", "oncall_manager": "N", "developer": "N", "viewer": "N"}),
    ("audit_logs.read", {"admin": "Y", "sre": "N", "oncall_manager": "N", "developer": "N", "viewer": "N"}),
    ("incidents.read", {"admin": "Y", "sre": "Y", "oncall_manager": "Y", "developer": "T", "viewer": "N"}),
    ("incidents.transition", {"admin": "Y", "sre": "Y", "oncall_manager": "N", "developer": "T", "viewer": "N"}),
    ("findings.read", {"admin": "Y", "sre": "Y", "oncall_manager": "N", "developer": "T", "viewer": "N"}),
    ("findings.ignore", {"admin": "Y", "sre": "Y", "oncall_manager": "N", "developer": "N", "viewer": "N"}),
    ("ai_tasks.read", {"admin": "Y", "sre": "T", "oncall_manager": "N", "developer": "N", "viewer": "N"}),
    ("ai_tasks.approve", {"admin": "Y", "sre": "T", "oncall_manager": "N", "developer": "N", "viewer": "N"}),
    ("oncall_schedules.read", {"admin": "Y", "sre": "N", "oncall_manager": "Y", "developer": "N", "viewer": "N"}),
    ("escalation_policies.write", {"admin": "Y", "sre": "N", "oncall_manager": "Y", "developer": "N", "viewer": "N"}),
    ("notification_records.read", {"admin": "Y", "sre": "Y", "oncall_manager": "Y", "developer": "N", "viewer": "N"}),
    ("status_page.read", {"admin": "Y", "sre": "Y", "oncall_manager": "Y", "developer": "Y", "viewer": "Y"}),
    ("workflows.read", {"admin": "Y", "sre": "Y", "oncall_manager": "N", "developer": "N", "viewer": "N"}),
    ("inspection_rules.read", {"admin": "Y", "sre": "Y", "oncall_manager": "N", "developer": "Y", "viewer": "N"}),
    ("inspection_policies.run", {"admin": "Y", "sre": "Y", "oncall_manager": "N", "developer": "N", "viewer": "N"}),
]


@pytest.mark.parametrize("resource_action,expectations", CONTRACT_EXPECTATIONS)
def test_permission_matrix_matches_contract(resource_action, expectations):
    resource, action = resource_action.split(".")
    for role_code, expected in expectations.items():
        assert _principal(role_code).can(resource, action) == expected, (
            f"{role_code}.{resource_action} 期望 {expected}"
        )


def test_admin_is_all_yes():
    admin = _principal("admin")
    for resource, actions in all_resources().items():
        for action in actions:
            assert admin.can(resource, action) == "Y", f"admin {resource}.{action}"


def test_team_scope_resolution_for_t_permission():
    developer = _principal("developer", team_scope="platform")
    assert developer.team_scope_for("alerts", "read") == "platform"
    assert developer.team_scope_for("alerts", "close") is None  # N 权限无 scope 概念


def test_merge_permissions_takes_max_privilege():
    merged = merge_permissions([
        {"alerts": {"read": "N", "close": "Y"}},
        {"alerts": {"read": "T"}},
    ])
    assert merged["alerts"]["read"] == "T"
    assert merged["alerts"]["close"] == "Y"


def test_every_resource_action_defined_for_every_role():
    resources = all_resources()
    for role_code, matrix in ROLE_PERMISSIONS.items():
        assert set(matrix) == set(resources), f"{role_code} 资源矩阵不完整"
        for resource, actions in resources.items():
            assert set(matrix[resource]) == set(actions), f"{role_code}.{resource} 动作矩阵不完整"
