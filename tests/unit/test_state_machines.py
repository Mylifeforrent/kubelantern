"""单元测试：状态机迁移表（合法通过 + 非法 409 语义）。"""

import pytest

from huntai.core.errors import ProblemError
from huntai.domains.incidents.service import ALLOWED_TRANSITIONS
from huntai.domains.alerts.models import AlertStatus

# 事件状态机（领域 §6，6 态）
INCIDENT_CASES = [
    ("open", "acknowledged", True),
    ("open", "cancelled", True),
    ("open", "mitigated", False),
    ("open", "resolved", False),
    ("open", "closed", False),
    ("acknowledged", "mitigated", True),
    ("acknowledged", "cancelled", True),
    ("mitigated", "resolved", True),
    ("mitigated", "cancelled", True),
    ("resolved", "closed", True),
    ("resolved", "acknowledged", False),
    ("cancelled", "open", False),
    ("closed", "open", False),
]


@pytest.mark.parametrize("src,dst,allowed", INCIDENT_CASES)
def test_incident_transitions(src, dst, allowed):
    assert (dst in ALLOWED_TRANSITIONS[src]) is allowed


def test_incident_machine_value_domain():
    assert set(ALLOWED_TRANSITIONS) == {
        "open", "acknowledged", "cancelled", "mitigated", "resolved", "closed",
    }


# 告警 8 态值域（状态机值域禁改）
def test_alert_status_value_domain():
    assert {status.value for status in AlertStatus} == {
        "received", "deduplicated", "enriched", "correlated", "standalone",
        "suppressed", "notified", "resolved",
    }


# 迁移语义异常映射（409 + code）
def test_problem_error_conflict_shape():
    err = ProblemError(status=409, code="INCIDENT_STATE_CONFLICT", detail="x → y 非法")
    assert err.status == 409 and err.code == "INCIDENT_STATE_CONFLICT"


def test_ai_task_value_domain():
    from huntai.domains.ai.models import AITaskStatus

    assert {status.value for status in AITaskStatus} == {
        "created", "sanitizing", "running", "pending_approval",
        "cancelled", "completed", "failed", "budget_exceeded",
    }


def test_finding_value_domain():
    from huntai.domains.inspections.models import FindingStatus

    assert {status.value for status in FindingStatus} == {
        "open", "acknowledged", "in_progress", "resolved", "ignored", "converted_to_alert",
    }


def test_workflow_run_value_domain():
    from huntai.domains.workflows.models import WorkflowRunStatus

    assert {status.value for status in WorkflowRunStatus} == {
        "triggered", "running", "waiting_approval", "cancelled", "succeeded", "failed", "timeout",
    }
