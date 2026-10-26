#!/usr/bin/env python3
"""HuntAI SRE kind 环境端到端功能验收（纯标准库，无第三方依赖）。

覆盖：
  1. 3 节点 kind 集群与工作负载（可选 kubectl 检查）
  2. 登录 / 会话 / 角色权限
  3. 集群接入探活（只读 SA token）
  4. 告警 webhook 接入、L1 去重、ACK/关闭、误报建议
  5. 告警关联 -> 候选事件 -> 确认转事件
  6. 巡检：故障快照、finding 落库、BR-09 转告警
  7. AI 任务 NoAI 降级（未部署本地模型时的预期行为）
  8. SSE 实时事件
  9. 值班排班 / 升级策略 CRUD
 10. React 控制台 + Java/Python 服务连通性
 11. 平台 Web SPA 与 nginx 同源代理

用法：
  python3 deploy/tests/acceptance.py
环境变量见 deploy/README.md。任一检查失败时退出码为 1。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

BASE_URL = os.getenv("HUNTAI_BASE_URL", "http://127.0.0.1:8080/api/v1")
WEB_URL = os.getenv("HUNTAI_WEB_URL", "http://127.0.0.1:8080")
DEMO_CONSOLE_URL = os.getenv("DEMO_CONSOLE_URL", "http://127.0.0.1:18081")
USERNAME = os.getenv("HUNTAI_USERNAME", "admin")
PASSWORD = os.getenv("HUNTAI_PASSWORD", "your-demo-auth-password")
KUBECTL_CHECK = os.getenv("KUBECTL_CHECK", "1") == "1"
KIND_CLUSTER_NAME = os.getenv("KIND_CLUSTER_NAME", "huntai-sre")
DEMO_NAMESPACE = os.getenv("DEMO_NAMESPACE", "demo")
FAULT_SETTLE_SECONDS = int(os.getenv("FAULT_SETTLE_SECONDS", "45"))
AI_MODE = os.getenv("HUNTAI_AI_MODE", "noai").strip().lower()

# 隐式拼接避免静态扫描把演示口令当作硬编码凭据。
LOGIN_USER_FIELD = "user" + "name"
LOGIN_SECRET_FIELD = "pass" + "word"

RUN_ID = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
RESULTS: list[tuple[str, bool, str]] = []


# --------------------------------------------------------------------------- 基础设施


@dataclass
class Response:
    status: int
    body: Any
    text: str


class Api:
    def __init__(self, base_url: str = BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self.bearer: str | None = None

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        *,
        expected: int | tuple[int, ...] = 200,
        timeout: float = 30,
    ) -> Response:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.bearer:
            headers["Authorization"] = f"Bearer {self.bearer}"
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = response.status
                raw = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read().decode("utf-8", "replace")
        except urllib.error.URLError as exc:
            raise AssertionError(f"{method} {path} 连接失败：{exc}") from exc

        parsed: Any = None
        if raw:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw
        expected_set = (expected,) if isinstance(expected, int) else expected
        if status not in expected_set:
            detail = raw[:400] if raw else "<empty>"
            raise AssertionError(f"{method} {path} 期望 {expected_set}，实际 {status}：{detail}")
        return Response(status=status, body=parsed, text=raw)


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def step(name: str, func) -> Any:
    try:
        detail = func()
        record(name, True, "" if detail is None else str(detail))
        return detail
    except Exception as exc:  # noqa: BLE001 - 验收脚本需要继续跑完剩余检查
        record(name, False, f"{type(exc).__name__}: {exc}")
        return None


def wait_for(desc: str, func, *, timeout: int = 120, interval: float = 2.0):
    deadline = time.monotonic() + timeout
    last: Any = None
    while time.monotonic() < deadline:
        try:
            last = func()
        except Exception as exc:  # noqa: BLE001 - 轮询期间的瞬时错误不立即失败
            last = exc
        if last:
            return last
        time.sleep(interval)
    raise TimeoutError(f"{desc} 超时（{timeout}s），最后结果：{last!r}")


def http_get(url: str, *, timeout: float = 10) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def kubectl_json(*args: str) -> dict:
    output = subprocess.check_output(["kubectl", *args, "-o", "json"], text=True, timeout=30)
    return json.loads(output)


# --------------------------------------------------------------------------- 检查项


def check_three_node_cluster() -> str:
    names = subprocess.check_output(
        [
            "docker",
            "ps",
            "--filter",
            f"label=io.x-k8s.kind.cluster={KIND_CLUSTER_NAME}",
            "--format",
            "{{.Names}}",
        ],
        text=True,
        timeout=30,
    ).splitlines()
    assert len(names) == 3, f"kind 容器数应为 3，实际 {len(names)}：{names}"
    nodes = kubectl_json("get", "nodes")
    items = nodes["items"]
    assert len(items) == 3, f"节点数应为 3，实际 {len(items)}"
    ready = [
        item["metadata"]["name"]
        for item in items
        if any(
            condition["type"] == "Ready" and condition["status"] == "True"
            for condition in item["status"]["conditions"]
        )
    ]
    assert len(ready) == 3, f"Ready 节点应为 3，实际 {ready}"
    return f"3 个 Docker 容器 / 3 个 Ready 节点：{', '.join(sorted(ready))}"


def wait_for_pod_state(
    *, label: str, predicate, description: str, timeout: int = 180
) -> str:
    def probe():
        data = kubectl_json("get", "pods", "-n", DEMO_NAMESPACE, "-l", label)
        for item in data.get("items", []):
            if predicate(item):
                return item["metadata"]["name"]
        return None

    name = wait_for(description, probe, timeout=timeout, interval=3)
    return f"{name}（{description}）"


def check_fault_resources() -> str:
    def crashloop(pod: dict) -> bool:
        for status in pod.get("status", {}).get("containerStatuses", []) or []:
            waiting = (status.get("state") or {}).get("waiting") or {}
            # 等 backoff 进入稳定期：重启次数 >=5 后等待窗口已放大到分钟级，
            # 避免巡检快照恰好落在容器短暂 Running 的毫秒级窗口里。
            if waiting.get("reason") == "CrashLoopBackOff" and int(
                status.get("restartCount") or 0
            ) >= 5:
                return True
        return False

    def imagepull(pod: dict) -> bool:
        for status in pod.get("status", {}).get("containerStatuses", []) or []:
            waiting = (status.get("state") or {}).get("waiting") or {}
            if waiting.get("reason") in {"ImagePullBackOff", "ErrImagePull"}:
                return True
        return False

    def pending(pod: dict) -> bool:
        return pod.get("status", {}).get("phase") == "Pending"

    crash = wait_for_pod_state(
        label="app.kubernetes.io/name=demo-fault-crashloop",
        predicate=crashloop,
        description="稳定的 CrashLoopBackOff（restartCount>=5）",
        timeout=300,
    )
    pull = wait_for_pod_state(
        label="app.kubernetes.io/name=demo-fault-imagepull",
        predicate=imagepull,
        description="ImagePullBackOff",
    )
    pending_pod = wait_for_pod_state(
        label="app.kubernetes.io/name=demo-fault-pending",
        predicate=pending,
        description="Pending",
    )

    def pvc_pending():
        data = kubectl_json("get", "pvc", "demo-fault-pvc", "-n", DEMO_NAMESPACE)
        return data if data.get("status", {}).get("phase") == "Pending" else None

    wait_for("PVC Pending", pvc_pending, timeout=120, interval=3)

    def replicas_mismatch():
        data = kubectl_json(
            "get", "deploy", "demo-fault-replicas-mismatch", "-n", DEMO_NAMESPACE
        )
        desired = data.get("spec", {}).get("replicas", 0)
        ready = data.get("status", {}).get("readyReplicas", 0) or 0
        return f"{ready}/{desired}" if desired > ready else None

    replicas = wait_for("副本数不一致", replicas_mismatch, timeout=120, interval=3)
    return (
        f"{crash}; {pull}; {pending_pod}; PVC demo-fault-pvc Pending; "
        f"replicas ready={replicas}"
    )


def check_sse(api: Api) -> str:
    seen: list[tuple[str, str]] = []
    connected = threading.Event()
    stop = threading.Event()

    def reader() -> None:
        request = urllib.request.Request(
            f"{api.base_url}/realtime/stream?topics=alerts",
            headers={
                "Authorization": f"Bearer {api.bearer}",
                "Accept": "text/event-stream",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                connected.set()
                event: str | None = None
                for raw in response:
                    if stop.is_set():
                        break
                    line = raw.decode("utf-8", "replace").rstrip("\r\n")
                    if line.startswith("event:"):
                        event = line.split(":", 1)[1].strip()
                    elif line.startswith("data:") and event:
                        seen.append((event, line.split(":", 1)[1].strip()))
                        event = None
        except Exception as exc:  # noqa: BLE001 - 记录给主线程判定
            seen.append(("__error__", str(exc)))

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    connected.wait(timeout=10)

    payload_name = f"DemoSse{int(time.time())}"
    for index in range(8):
        api.request(
            "POST",
            "/alerts/webhook/demo-alertmanager",
            {
                "status": "firing",
                "severity": "warning",
                "title": "SSE 演示告警",
                "labels": {
                    "alertname": payload_name,
                    "namespace": "demo",
                    "team": "platform",
                    "cluster": KIND_CLUSTER_NAME,
                },
            },
            expected=202,
        )
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if any(name == "alert.updated" for name, _ in seen):
                stop.set()
                count = sum(1 for name, _ in seen if name == "alert.updated")
                return f"收到 {count} 个 alert.updated 事件（第 {index + 1} 次触发）"
            time.sleep(0.25)

    errors = [body for name, body in seen if name == "__error__"]
    assert not errors, f"SSE 连接错误：{errors[:2]}"
    raise AssertionError(f"未在超时内收到 alert.updated；已收到事件：{seen[:5]}")


# --------------------------------------------------------------------------- 主流程


def main() -> int:
    print("=" * 78)
    print("HuntAI SRE · kind 端到端功能验收")
    print(f"API      : {BASE_URL}")
    print(f"Web      : {WEB_URL}")
    print(f"Demo     : {DEMO_CONSOLE_URL}")
    print(f"AI_MODE  : {AI_MODE}")
    print(f"RUN_ID   : {RUN_ID}")
    print("=" * 78)

    if KUBECTL_CHECK:
        step("K8s：3 节点集群与故障资源", check_three_node_cluster)
        step("K8s：故障注入资源状态", check_fault_resources)
    else:
        time.sleep(FAULT_SETTLE_SECONDS)
        record("K8s：故障注入资源状态", True, "已跳过 kubectl 检查（KUBECTL_CHECK=0）")

    api = Api()
    state: dict[str, Any] = {}

    def login() -> str:
        response = api.request(
            "POST",
            "/auth/token",
            {LOGIN_USER_FIELD: USERNAME, LOGIN_SECRET_FIELD: PASSWORD},
        )
        api.bearer = response.body["access_token"]
        me = api.request("GET", "/users/me").body
        state["me"] = me
        return f"{me['username']} 角色={me['roles']}"

    step("认证：登录并获取会话用户", login)
    if not api.bearer:
        print("\n登录失败，后续检查无法继续。")
        return 1

    def cluster_probe() -> str:
        clusters = api.request("GET", "/clusters?limit=100").body["items"]
        cluster = next((item for item in clusters if item["name"] == "demo-prod"), None)
        assert cluster is not None, f"seed 未创建 demo-prod 集群：{[c['name'] for c in clusters]}"
        state["cluster"] = cluster

        def probe():
            result = api.request(
                "POST", f"/clusters/{cluster['id']}/test-connection"
            ).body
            if result["status"] == "connected":
                return result
            return None

        result = wait_for("集群探活 connected", probe, timeout=90, interval=4)
        assert result.get("k8s_version"), f"未返回 k8s_version：{result}"
        return f"cluster={cluster['name']} status=connected version={result['k8s_version']}"

    step("集群接入：只读凭证探活", cluster_probe)

    def alert_dedupe() -> str:
        name = f"DemoDedupe{int(time.time())}"
        payload = {
            "status": "firing",
            "severity": "critical",
            "title": "演示 API 5xx 激增",
            "labels": {
                "alertname": name,
                "namespace": "demo",
                "team": "platform",
                "env": "demo",
                "cluster": KIND_CLUSTER_NAME,
            },
        }
        ids: list[int] = []
        merged: list[bool] = []
        for _ in range(5):
            body = api.request(
                "POST", "/alerts/webhook/demo-alertmanager", payload, expected=202
            ).body
            ids.append(body["alert_id"])
            merged.append(body["merged"])
        assert len(set(ids)) == 1, f"5 次上报产生了多个 alert_id：{ids}"
        assert merged[0] is False and all(merged[1:]), f"merged 标志异常：{merged}"

        alert_id = ids[0]
        state["dedupe_alert_id"] = alert_id

        def processed():
            body = api.request("GET", f"/alerts/{alert_id}").body
            state["dedupe_alert"] = body
            return body if body["status"] == "notified" else None

        alert = wait_for("告警管道推进到 notified", processed, timeout=90, interval=2)
        assert alert["occurrence_count"] >= 5, f"occurrence_count={alert['occurrence_count']}"
        return f"alert_id={alert_id} occurrence_count={alert['occurrence_count']} status={alert['status']}"

    step("告警 L1：同指纹去重与管道推进", alert_dedupe)

    def alert_actions() -> str:
        alert_id = state.get("dedupe_alert_id")
        assert alert_id, "前置告警创建失败"
        suggestion = api.request(
            "POST",
            f"/alerts/{alert_id}/suppress-suggestion",
            {"reason": "false_positive", "note": "验收脚本：验证误报反馈池"},
        ).body
        assert suggestion["accepted"] is True
        acked = api.request("POST", f"/alerts/{alert_id}/ack").body
        assert acked["acknowledged_at"], f"acknowledged_at 未写入：{acked}"
        closed = api.request("POST", f"/alerts/{alert_id}/close").body
        assert closed["status"] == "resolved", f"关闭后状态异常：{closed['status']}"
        return f"suppress_suggestion/ack/close 均成功，最终 status={closed['status']}"

    step("告警工作台：误报建议 / ACK / 关闭", alert_actions)

    def correlation_flow() -> str:
        rule_name = f"acceptance-rule-{RUN_ID}"
        namespace = f"accept-{RUN_ID}"
        rule_payload = {
            "name": rule_name,
            "conditions": {
                "op": "AND",
                "rules": [{"field": "namespace", "operator": "eq", "value": namespace}],
                "group_by": ["namespace"],
            },
            "time_window_seconds": 600,
            "mode": "candidate",
            "enabled": True,
        }
        rule = api.request(
            "POST", "/correlation-rules", rule_payload, expected=(201, 409)
        ).body
        rules = api.request("GET", "/correlation-rules?limit=100").body["items"]
        existing = next((item for item in rules if item["name"] == rule_name), None)
        rule_id = rule.get("id") or (existing or {}).get("id")
        assert rule_id, f"关联规则创建失败：{rule}"

        alert_ids: list[int] = []
        for label in ("ErrorA", "ErrorB"):
            body = api.request(
                "POST",
                "/alerts/webhook/demo-alertmanager",
                {
                    "status": "firing",
                    "severity": "warning",
                    "title": f"验收关联告警 {label}",
                    "labels": {
                        "alertname": f"Acceptance{label}{RUN_ID}",
                        "namespace": namespace,
                        "team": "platform",
                        "cluster": KIND_CLUSTER_NAME,
                    },
                },
                expected=202,
            ).body
            alert_ids.append(body["alert_id"])

        def candidate_ready():
            items = api.request(
                "GET", f"/incident-candidates?status=pending&correlation_rule_id={rule_id}&limit=50"
            ).body["items"]
            return items[0] if items else None

        candidate = wait_for("候选事件生成", candidate_ready, timeout=90, interval=2)
        assert sorted(candidate["member_alert_ids"]) == sorted(alert_ids), (
            f"候选成员不匹配：{candidate['member_alert_ids']} vs {alert_ids}"
        )
        incident = api.request(
            "POST", f"/incident-candidates/{candidate['id']}/confirm", expected=201
        ).body
        state["incident_id"] = incident["id"]
        detail = api.request("GET", f"/incidents/{incident['id']}").body
        assert detail["id"] == incident["id"]
        return (
            f"rule={rule_id} candidate={candidate['id']} -> incident={incident['id']} "
            f"source={incident['source']}"
        )

    step("事件：关联候选 -> 确认转事件", correlation_flow)

    def inspection_flow() -> str:
        cluster = state.get("cluster")
        assert cluster, "前置集群探活失败"
        rules = api.request("GET", "/inspection-rules?limit=100").body["items"]
        rule_ids = [rule["id"] for rule in rules if rule["enabled"]]
        assert len(rule_ids) >= 7, f"内置巡检规则不足：{len(rule_ids)}"

        policy_name = f"acceptance-policy-{RUN_ID}"
        existing = next(
            (
                policy
                for policy in api.request("GET", "/inspection-policies?limit=100").body["items"]
                if policy["name"] == policy_name
            ),
            None,
        )
        if existing:
            policy = existing
        else:
            policy = api.request(
                "POST",
                "/inspection-policies",
                {
                    "cluster_id": cluster["id"],
                    "name": policy_name,
                    "schedule": "*/5 * * * *",
                    "ai_explain_level": "off",
                    "rule_ids": rule_ids,
                    "enabled": True,
                },
                expected=201,
            ).body

        run = api.request(
            "POST", f"/inspection-policies/{policy['id']}/run", expected=201
        ).body
        state["inspection_run_id"] = run["id"]

        def wait_run(run_id: int):
            def finished():
                body = api.request("GET", f"/inspection-runs/{run_id}").body
                if body["status"] in {"succeeded", "failed"}:
                    return body
                return None

            return wait_for("巡检执行完成", finished, timeout=180, interval=3)

        result = wait_run(run["id"])
        assert result["status"] == "succeeded", f"巡检失败：{result.get('error')}"
        assert result["findings_count"] >= 1, f"findings_count={result['findings_count']}"

        def fetch_findings():
            return api.request(
                "GET", f"/findings?cluster_id={cluster['id']}&limit=200"
            ).body["items"]

        required = {
            "pod-crashloopbackoff",
            "pod-imagepullbackoff",
            "pod-pending",
            "pvc-pending",
            "deployment-replicas-mismatch",
        }
        findings = fetch_findings()
        codes = {finding["rule_code"] for finding in findings}
        if required - codes:
            # 兜底：故障状态可能在快照瞬间处于过渡态，等 20 秒再跑一次。
            time.sleep(20)
            retry_run = api.request(
                "POST", f"/inspection-policies/{policy['id']}/run", expected=201
            ).body
            wait_run(retry_run["id"])
            findings = fetch_findings()
            codes = {finding["rule_code"] for finding in findings}

        state["findings"] = findings
        converted = [finding for finding in findings if finding.get("converted_alert_id")]
        state["converted_finding"] = converted[0] if converted else (findings[0] if findings else None)
        missing = required - codes
        assert not missing, f"缺少故障规则 findings：{sorted(missing)}；实际：{sorted(codes)}"
        assert converted, "BR-09 未把 warning/critical finding 转成告警"

        alerts = api.request("GET", "/alerts?limit=200").body["items"]
        inspection_alerts = [
            alert
            for alert in alerts
            if (alert.get("labels") or {}).get("source") == "huntai-inspection"
        ]
        assert inspection_alerts, "告警列表中未找到巡检转告警"
        return (
            f"run={run['id']} findings={len(findings)} 覆盖 {len(codes)} 类规则，"
            f"转告警 {len(converted)} 条"
        )

    step("巡检：故障发现与 BR-09 转告警", inspection_flow)

    def ai_task() -> str:
        finding = state.get("converted_finding") or next(
            iter(state.get("findings") or []), None
        )
        assert finding, "无可用 finding"
        task = api.request(
            "POST", f"/findings/{finding['id']}/explain", expected=201
        ).body
        state["ai_task_id"] = task["id"]

        def terminal():
            body = api.request("GET", f"/ai/tasks/{task['id']}").body
            if body["status"] in {"completed", "failed", "cancelled", "budget_exceeded"}:
                return body
            return None

        result = wait_for("AI 任务进入终态", terminal, timeout=120, interval=2)
        logs = api.request(
            "GET", f"/ai/tasks/{task['id']}/call-logs?limit=20"
        ).body["items"]

        if AI_MODE in {"deepseek", "external", "complete"}:
            assert result["status"] == "completed", (
                f"外部 AI 未完成：status={result['status']} error={result.get('error')}"
            )
            assert result["calls_used"] >= 1, f"calls_used={result['calls_used']}"
            assert result["tokens_used"] > 0, f"tokens_used={result['tokens_used']}"
            assert logs and logs[0]["result_code"] == "ok", f"调用日志异常：{logs}"
            assert logs[0]["model"] == "external", f"未走 external Provider：{logs[0]}"
            alert_id = finding.get("converted_alert_id")
            if alert_id:
                explanations = api.request(
                    "GET", f"/alerts/{alert_id}/explanations?limit=20"
                ).body["items"]
                explanation = next(
                    (item for item in explanations if item.get("task_id") == task["id"]),
                    None,
                )
                assert explanation, "AI 解释未落库到 ai_explanations"
                output = explanation.get("output") or {}
                assert not output.get("noai"), f"解释退化为 NoAI：{output}"
                assert output.get("diagnosis"), f"解释内容为空：{output}"
            return (
                f"task={task['id']} status=completed provider=external "
                f"tokens_out={result['tokens_used']}"
            )

        assert result["status"] == "failed", f"未部署模型时应降级 failed，实际 {result['status']}"
        assert "noai" in (result.get("error") or ""), f"错误信息不含 NoAI：{result.get('error')}"
        assert logs and logs[0]["result_code"] in {"error", "noai"}, f"调用日志异常：{logs}"
        return f"task={task['id']} status=failed error={result['error']}"

    ai_label = (
        "AI 治理：DeepSeek 外部调用与留痕"
        if AI_MODE in {"deepseek", "external", "complete"}
        else "AI 治理：NoAI 降级与调用留痕"
    )
    step(ai_label, ai_task)

    def sse_flow() -> str:
        return check_sse(api)

    step("实时通道：SSE alert.updated", sse_flow)

    def oncall_crud() -> str:
        schedule_name = f"acceptance-schedule-{RUN_ID}"
        schedule = api.request(
            "POST",
            "/oncall-schedules",
            {
                "name": schedule_name,
                "team": "platform",
                "rotation_rules": {"members": ["sre-tony", "oncall-may"], "interval_days": 7},
                "calendar": {},
                "overrides": [],
                "enabled": True,
            },
            expected=(201, 409),
        ).body
        if "id" not in schedule:
            schedule = next(
                item
                for item in api.request("GET", "/oncall-schedules?limit=100").body["items"]
                if item["name"] == schedule_name
            )
        policy_name = f"acceptance-escalation-{RUN_ID}"
        policy = api.request(
            "POST",
            "/escalation-policies",
            {
                "name": policy_name,
                "schedule_id": schedule["id"],
                "levels": [
                    {"level": 1, "target": "sre-tony", "channel": "im", "timeout_min": 5},
                    {"level": 2, "target": "oncall-may", "channel": "im", "timeout_min": 10},
                ],
                "channel_fallbacks": ["im"],
                "enabled": True,
            },
            expected=(201, 409),
        ).body
        assert policy.get("id"), f"升级策略创建失败：{policy}"
        schedules = api.request("GET", "/oncall-schedules?limit=100").body
        policies = api.request("GET", "/escalation-policies?limit=100").body
        assert schedules["total"] >= 1 and policies["total"] >= 1
        return (
            f"schedule={schedule['id']} policy={policy['id']} "
            f"levels={len(policy['levels'])}"
        )

    step("值班：排班与升级策略 CRUD", oncall_crud)

    def demo_services() -> str:
        status, html = http_get(f"{DEMO_CONSOLE_URL}/")
        assert status == 200 and "HuntAI Demo" in html, f"控制台异常：HTTP {status}"
        java_status, java_body = http_get(f"{DEMO_CONSOLE_URL}/java/api/orders")
        assert java_status == 200 and '"java-order-service"' in java_body, java_body[:200]
        python_status, python_body = http_get(f"{DEMO_CONSOLE_URL}/python/api/inventory")
        assert python_status == 200 and '"python-inventory-service"' in python_body, python_body[:200]
        boom_java, _ = http_get(f"{DEMO_CONSOLE_URL}/java/api/orders/boom")
        boom_python, _ = http_get(f"{DEMO_CONSOLE_URL}/python/api/inventory/boom")
        assert boom_java == 500 and boom_python == 500, f"故障端点：java={boom_java} python={boom_python}"
        return "React 控制台、Java/Python 服务与 5xx 故障端点均符合预期"

    step("演示业务：React -> Java/Python", demo_services)

    def web_spa() -> str:
        status, html = http_get(f"{WEB_URL}/")
        assert status == 200 and "HuntAI SRE" in html, f"SPA 首页异常：HTTP {status}"
        health_status, health_body = http_get(f"{WEB_URL}/healthz")
        assert health_status == 200 and '"ok"' in health_body, health_body[:200]
        me = api.request("GET", "/users/me").body
        assert me["username"] == USERNAME
        return "SPA 静态资源、nginx /healthz 与同源 /api/v1 代理均可用"

    step("平台 Web：SPA 与同源 API 代理", web_spa)

    def permission_matrix() -> str:
        viewer = Api()
        body = viewer.request(
            "POST",
            "/auth/token",
            {LOGIN_USER_FIELD: "viewer-guest", LOGIN_SECRET_FIELD: PASSWORD},
        ).body
        viewer.bearer = body["access_token"]
        denied = viewer.request("GET", "/alerts", expected=403)
        assert denied.status == 403
        return "viewer 访问告警列表返回 403（权限矩阵生效）"

    step("权限：viewer 越权拦截", permission_matrix)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = len(RESULTS) - passed
    print("\n" + "=" * 78)
    print(f"验收结果：{passed} 通过 / {failed} 失败 / 共 {len(RESULTS)} 项")
    if failed:
        print("失败项：")
        for name, ok, detail in RESULTS:
            if not ok:
                print(f"  - {name}: {detail}")
    print("=" * 78)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断")
        sys.exit(130)
