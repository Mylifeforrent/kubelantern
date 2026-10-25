"""单元测试：集群探活凭证不可用时的降级语义（不发起网络请求）。"""

from __future__ import annotations

from huntai.domains.clusters import connector
from huntai.domains.clusters.models import Cluster, Credential, CredentialScope


def _cluster() -> Cluster:
    return Cluster(
        name="it-cluster", environment="dev", api_endpoint="https://k8s.test", credential_id=1
    )


def test_probe_missing_env_returns_disconnected(monkeypatch):
    monkeypatch.delenv("HUNTAI_DEMO_CLUSTER_TOKEN", raising=False)
    cred = Credential(
        name="it-cred", secret_ref="env:HUNTAI_DEMO_CLUSTER_TOKEN", scope=CredentialScope.READONLY
    )

    result = connector._probe_sync(_cluster(), cred)

    assert result.status == "disconnected"
    assert result.k8s_version is None
    assert "未配置" in (result.message or "")


def test_probe_unsupported_backend_returns_disconnected():
    cred = Credential(
        name="it-cred", secret_ref="vault:secret/cluster", scope=CredentialScope.READONLY
    )

    result = connector._probe_sync(_cluster(), cred)

    assert result.status == "disconnected"
    assert "不支持" in (result.message or "")
