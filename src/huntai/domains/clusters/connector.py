"""只读 K8s 连接器（04-backend-design §3.8；BR-02 只读）。

- 凭证经 secret_ref 运行时取用、内存态使用、禁止落日志（D-2）。
- 官方 kubernetes 客户端为同步实现，经 asyncio.to_thread 包装供异步调用。
- 巡检快照为 dict 结构（key 约定见 fetch_snapshot docstring），避免与巡检域产生模块依赖。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from kubernetes import client as k8s_client
from kubernetes.client import ApiClient, Configuration
from kubernetes.client.rest import ApiException

from huntai.core.errors import ProblemError
from huntai.core.secrets import resolve_secret
from huntai.domains.clusters.models import Cluster, Credential

logger = logging.getLogger("huntai.clusters")

PROBE_TIMEOUT_SECONDS = 5


@dataclass
class ProbeResult:
    status: str  # cluster_status 值域
    k8s_version: str | None
    message: str | None


def _build_api(cluster: Cluster, cred: Credential) -> ApiClient:
    """加载 readonly 凭证（BR-02）；值只进内存与请求头，不进日志。"""
    if cred.scope != "readonly":
        raise ProblemError(status=500, detail="连接器只允许加载 readonly 凭证（BR-02）")
    bearer_material = resolve_secret(cred.secret_ref)
    config = Configuration(
        host=cluster.api_endpoint,
        api_key={"authorization": f"Bearer {bearer_material}"},
    )
    config.verify_ssl = False  # 自签集群证书（生产经 CA 配置 [TBD-INFRA]）
    config.timeout = PROBE_TIMEOUT_SECONDS
    return ApiClient(configuration=config)


def _probe_sync(cluster: Cluster, cred: Credential) -> ProbeResult:
    try:
        api_client = _build_api(cluster, cred)
    except ProblemError as exc:
        # 凭证未配置属配置态失败：探活接口按 disconnected 返回，不升级为 500
        return ProbeResult(status="disconnected", k8s_version=None, message=exc.detail)
    try:
        version = k8s_client.VersionApi(api_client).get_code()
        return ProbeResult(
            status="connected", k8s_version=getattr(version, "git_version", None), message=None
        )
    except ApiException as exc:
        return ProbeResult(
            status="degraded" if exc.status in (401, 403) else "disconnected",
            k8s_version=None,
            message=f"k8s api error: {exc.status}",
        )
    except Exception:
        return ProbeResult(status="disconnected", k8s_version=None, message="连接失败（网络/凭证不可用）")
    finally:
        api_client.rest_client.pool_manager.clear()
        api_client.close()


async def probe(cluster: Cluster, cred: Credential) -> ProbeResult:
    return await asyncio.to_thread(_probe_sync, cluster, cred)


def _fetch_snapshot_sync(cluster: Cluster, cred: Credential) -> dict[str, list[dict[str, Any]]]:
    """拉取巡检快照（只读）。返回 {kind: [item, ...]}，kind ∈ pods/deployments/pvcs/nodes。"""
    api_client = _build_api(cluster, cred)
    snapshot: dict[str, list[dict[str, Any]]] = {"pods": [], "deployments": [], "pvcs": [], "nodes": []}
    try:
        core = k8s_client.CoreV1Api(api_client)
        apps = k8s_client.AppsV1Api(api_client)
        for pod in core.list_pod_for_all_namespaces().items:
            snapshot["pods"].append({
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "phase": pod.status.phase,
                "container_statuses": [
                    {
                        "name": cs.name,
                        "ready": cs.ready,
                        "restart_count": cs.restart_count,
                        "waiting_reason": (cs.state.waiting.reason if cs.state and cs.state.waiting else None),
                    }
                    for cs in (pod.status.container_statuses or [])
                ],
            })
        for deploy in apps.list_deployment_for_all_namespaces().items:
            snapshot["deployments"].append({
                "name": deploy.metadata.name,
                "namespace": deploy.metadata.namespace,
                "replicas": deploy.spec.replicas,
                "ready_replicas": deploy.status.ready_replicas or 0,
                "available_replicas": deploy.status.available_replicas or 0,
            })
        for pvc in core.list_persistent_volume_claim_for_all_namespaces().items:
            snapshot["pvcs"].append({
                "name": pvc.metadata.name,
                "namespace": pvc.metadata.namespace,
                "phase": pvc.status.phase,
            })
        for node in core.list_node().items:
            conditions = {c.type: c.status for c in (node.status.conditions or [])}
            snapshot["nodes"].append({"name": node.metadata.name, "conditions": conditions})
        return snapshot
    finally:
        api_client.rest_client.pool_manager.clear()
        api_client.close()


async def fetch_snapshot(cluster: Cluster, cred: Credential) -> dict[str, list[dict[str, Any]]]:
    return await asyncio.to_thread(_fetch_snapshot_sync, cluster, cred)
