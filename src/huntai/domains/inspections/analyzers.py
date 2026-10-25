"""内置巡检 Analyzer（k8sgpt analyzer 移植风格；纯函数，code ↔ inspection_rules.code）。

快照结构见 domains/clusters/connector.fetch_snapshot：
  {"pods": [...], "deployments": [...], "pvcs": [...], "nodes": [...]}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class FindingDraft:
    rule_code: str
    resource_ref: dict[str, str | None]
    severity: str | None = None  # None → 取 inspection_rules.severity_default
    raw_error: dict[str, Any] = field(default_factory=dict)


class Analyzer(Protocol):
    code: str
    category: str

    def analyze(self, snapshot: dict[str, list[dict[str, Any]]]) -> list[FindingDraft]: ...


class PodCrashLoopBackOffAnalyzer:
    code = "pod-crashloopbackoff"
    category = "pod"

    def analyze(self, snapshot):
        drafts = []
        for pod in snapshot.get("pods", []):
            for cs in pod.get("container_statuses", []):
                if cs.get("waiting_reason") in {"CrashLoopBackOff", "Error"}:
                    drafts.append(
                        FindingDraft(
                            rule_code=self.code,
                            resource_ref={"kind": "Pod", "namespace": pod["namespace"], "name": pod["name"]},
                            raw_error={"container": cs["name"], "reason": cs["waiting_reason"]},
                        )
                    )
        return drafts


class PodImagePullBackOffAnalyzer:
    code = "pod-imagepullbackoff"
    category = "pod"

    def analyze(self, snapshot):
        drafts = []
        for pod in snapshot.get("pods", []):
            for cs in pod.get("container_statuses", []):
                if cs.get("waiting_reason") in {"ImagePullBackOff", "ErrImagePull"}:
                    drafts.append(
                        FindingDraft(
                            rule_code=self.code,
                            resource_ref={"kind": "Pod", "namespace": pod["namespace"], "name": pod["name"]},
                            raw_error={"container": cs["name"], "reason": cs["waiting_reason"]},
                        )
                    )
        return drafts


class PodPendingAnalyzer:
    code = "pod-pending"
    category = "pod"

    def analyze(self, snapshot):
        return [
            FindingDraft(
                rule_code=self.code,
                resource_ref={"kind": "Pod", "namespace": pod["namespace"], "name": pod["name"]},
                raw_error={"phase": pod.get("phase")},
            )
            for pod in snapshot.get("pods", [])
            if pod.get("phase") == "Pending"
        ]


class PodHighRestartsAnalyzer:
    RESTART_THRESHOLD = 10

    code = "pod-high-restarts"
    category = "pod"

    def analyze(self, snapshot):
        drafts = []
        for pod in snapshot.get("pods", []):
            for cs in pod.get("container_statuses", []):
                if int(cs.get("restart_count") or 0) >= self.RESTART_THRESHOLD:
                    drafts.append(
                        FindingDraft(
                            rule_code=self.code,
                            resource_ref={"kind": "Pod", "namespace": pod["namespace"], "name": pod["name"]},
                            raw_error={"container": cs["name"], "restart_count": cs["restart_count"]},
                        )
                    )
        return drafts


class PvcPendingAnalyzer:
    code = "pvc-pending"
    category = "pvc"

    def analyze(self, snapshot):
        return [
            FindingDraft(
                rule_code=self.code,
                resource_ref={"kind": "PersistentVolumeClaim", "namespace": pvc["namespace"], "name": pvc["name"]},
                raw_error={"phase": pvc.get("phase")},
            )
            for pvc in snapshot.get("pvcs", [])
            if pvc.get("phase") != "Bound"
        ]


class DeploymentReplicasMismatchAnalyzer:
    code = "deployment-replicas-mismatch"
    category = "deployment"

    def analyze(self, snapshot):
        return [
            FindingDraft(
                rule_code=self.code,
                resource_ref={"kind": "Deployment", "namespace": deploy["namespace"], "name": deploy["name"]},
                raw_error={
                    "replicas": deploy.get("replicas"),
                    "ready_replicas": deploy.get("ready_replicas"),
                },
            )
            for deploy in snapshot.get("deployments", [])
            if int(deploy.get("replicas") or 0) > int(deploy.get("ready_replicas") or 0)
        ]


class NodePressureAnalyzer:
    code = "node-pressure"
    category = "node"

    def analyze(self, snapshot):
        drafts = []
        for node in snapshot.get("nodes", []):
            pressure = [
                condition
                for condition, status in (node.get("conditions") or {}).items()
                if condition in {"MemoryPressure", "DiskPressure", "PIDPressure"} and status == "True"
            ]
            if pressure:
                drafts.append(
                    FindingDraft(
                        rule_code=self.code,
                        resource_ref={"kind": "Node", "namespace": None, "name": node["name"]},
                        raw_error={"conditions": pressure},
                    )
                )
        return drafts


BUILTIN_ANALYZERS: dict[str, Analyzer] = {
    analyzer.code: analyzer
    for analyzer in (
        PodCrashLoopBackOffAnalyzer(),
        PodImagePullBackOffAnalyzer(),
        PodPendingAnalyzer(),
        PodHighRestartsAnalyzer(),
        PvcPendingAnalyzer(),
        DeploymentReplicasMismatchAnalyzer(),
        NodePressureAnalyzer(),
    )
}
