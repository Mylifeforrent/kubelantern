# 功能验收与手工体验

> 状态：accepted ｜ 日期：2026-10-25 ｜ 读者：测试/演示/新同学
> 依据：`docs/02-business-design/05-prd.md` §5、`docs/03-tech-design/04-backend-design.md` §7、`deploy/tests/acceptance.py`。

## 1. 一键验收

集群、平台、演示业务都部署完成后：

```bash
bash deploy/scripts/05-run-acceptance.sh
```

脚本会先等 Java/Python/React 三个 Deployment 可用、再等 45 秒让故障资源进入目标状态，然后运行 14 项检查。AI 口径默认自动识别：开启外部出域时断言 DeepSeek 任务 `completed`，否则断言 NoAI 降级 `failed`。全部通过时输出类似：

```text
==============================================================================
KubeLantern · kind 端到端功能验收
API      : http://127.0.0.1:8080/api/v1
...
[PASS] K8s：3 节点集群与故障资源 — 3 个 Docker 容器 / 3 个 Ready 节点：...
[PASS] K8s：故障注入资源状态 — ...CrashLoopBackOff...ImagePullBackOff...Pending...
[PASS] 认证：登录并获取会话用户 — admin 角色=['admin']
[PASS] 集群接入：只读凭证探活 — cluster=demo-prod status=connected version=v1.37.0
[PASS] 告警 L1：同指纹去重与管道推进 — alert_id=... occurrence_count=5 status=notified
[PASS] 告警工作台：误报建议 / ACK / 关闭 — ...
[PASS] 事件：关联候选 -> 确认转事件 — rule=... candidate=... -> incident=...
[PASS] 巡检：故障发现与 BR-09 转告警 — run=... findings=... 覆盖 5 类规则
[PASS] AI 治理：DeepSeek 外部调用与留痕 — task=... status=completed provider=external ...
[PASS] 实时通道：SSE alert.updated — 收到 ... 个 alert.updated 事件
[PASS] 值班：排班与升级策略 CRUD — schedule=... policy=...
[PASS] 演示业务：React -> Java/Python — ...
[PASS] 平台 Web：SPA 与同源 API 代理 — ...
[PASS] 权限：viewer 越权拦截 — viewer 访问告警列表返回 403
==============================================================================
验收结果：14 通过 / 0 失败 / 共 14 项
```

任一失败退出码为 1，并在最后列出失败项与请求详情。

### 1.1 可调参数

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `HUNTAI_BASE_URL` | `http://127.0.0.1:8080/api/v1` | API 地址 |
| `HUNTAI_WEB_URL` | `http://127.0.0.1:8080` | Web SPA 地址 |
| `DEMO_CONSOLE_URL` | `http://127.0.0.1:18081` | 演示控制台 |
| `HUNTAI_USERNAME` | `admin` | 验收账号 |
| `HUNTAI_PASSWORD` | `your-demo-auth-password` | 验收口令 |
| `KUBECTL_CHECK` | `1` | 设为 `0` 跳过 Docker/kubectl 检查 |
| `FAULT_SETTLE_SECONDS` | `45` | 跳过 kubectl 检查时等待故障的时间 |
| `KIND_CLUSTER_NAME` | `huntai-sre` | kind 集群名 |
| `DEMO_NAMESPACE` | `demo` | 演示命名空间 |
| `HUNTAI_AI_MODE` | `auto` | 自动读取部署的 AI 出域开关；也可显式设为 `deepseek` / `noai` |

## 2. 自动验收覆盖了什么

| # | 检查项 | 验证的业务能力 | 关键断言 |
|---|---|---|---|
| 1 | 3 节点集群 | kind 1 control-plane + 2 worker | 恰好 3 个 Docker 容器、3 个 Ready 节点 |
| 2 | 故障资源 | 真实 K8s 故障场景 | CrashLoop/ImagePull/Pending/PVC/副本不一致均进入目标状态 |
| 3 | 登录/会话 | dev 认证 + roles | `GET /users/me` 返回 admin 与角色 |
| 4 | 集群接入 | BR-02 只读凭证、探活 | `test-connection` 返回 `connected` + `k8s_version` |
| 5 | 告警 L1 | webhook 接入、fingerprint 去重 | 5 次上报 → 1 个 alert_id、`merged` 后 4 次为 true、`occurrence_count>=5`、管道推进到 `notified` |
| 6 | 告警工作台 | 误报建议、ACK、关闭 | `accepted=true`、`acknowledged_at` 写入、关闭后 `status=resolved` |
| 7 | 事件闭环 | BR-04 关联 → 候选 → 确认 | 两条同 namespace 告警生成候选，确认后 incident.source=correlation |
| 8 | 巡检 | 快照、规则、finding、BR-09 | 命中 5 类故障规则，且 finding 已转告警 |
| 9 | AI 治理 | NoAI 降级 / DeepSeek 外部调用、预算/调用留痕 | 自动识别口径：未部署模型时 `failed` + `noai`；开启外域时 `completed`、call-log 为 ok、解释落库 |
| 10 | SSE | 实时事件通道 | 订阅后收到 `alert.updated` |
| 11 | 值班 | P2 排班/升级策略 | 排班与两级升级策略创建、列表可读 |
| 12 | 演示业务 | React → Java/Python | 控制台 200、两个服务 JSON、5xx 端点返回 500 |
| 13 | 平台 Web | SPA + nginx 同源代理 | 首页 200、`/healthz` 200、带 token 的 `/api/v1/users/me` 200 |
| 14 | 权限 | RBAC 矩阵 | viewer 访问 `/alerts` 返回 403 |

## 3. 手工体验路线（约 20 分钟）

### 3.1 登录与总览

1. 打开 http://127.0.0.1:8080；
2. 用户名 `admin`，口令 `your-demo-auth-password`；
3. 左侧进入「告警工作台」。

### 3.2 告警 L1：接入、去重、处置

平台已 seed 了 3 条演示告警（状态 `received`，seed 阶段不投递管道任务）。真正走完整管道的是 CronJob 和手工 webhook。

手工发一条告警：

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8080/api/v1/auth/token \
  -H 'content-type: application/json' \
  -d '{"username":"admin","password":"your-demo-auth-password"}' \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["access_token"])')

for i in 1 2 3; do
  curl -s -X POST http://127.0.0.1:8080/api/v1/alerts/webhook/demo-alertmanager \
    -H 'content-type: application/json' \
    -d '{
      "status":"firing",
      "severity":"critical",
      "title":"手工验收：API 5xx 激增",
      "labels":{"alertname":"ManualApi5xx","namespace":"demo","team":"platform","cluster":"huntai-sre"}
    }'
  echo
done
```

预期：

- 第一次返回 `{"alert_id":N,"merged":false}`，后两次 `merged:true`；
- 工作台出现 1 条 `ManualApi5xx`，occurrence_count 增长；
- 状态在几秒内从 `received` → `notified`；
- 打开告警抽屉可 ACK / 关闭 / 提交误报抑制建议。

SSE 验证（另开终端）：

```bash
curl -N -H "Authorization: Bearer $TOKEN" \
  'http://127.0.0.1:8080/api/v1/realtime/stream?topics=alerts'
```

再发一次告警，终端应出现：

```text
id: 175...
event: alert.updated
data: {"resource":"alert","resource_id":...}
```

### 3.3 巡检：从真实故障到 finding / 告警

1. 确认故障资源已就绪：

   ```bash
   kubectl -n demo get pods
   kubectl -n demo get pvc
   kubectl -n demo get deploy
   ```

2. 页面进入「巡检看板」；
3. 选择 `demo-prod` 集群，运行策略（或新建策略并勾选全部内置规则）；
4. 等待 run 变为 `succeeded`；
5. 打开 findings，预期看到：

| rule_code | 资源 |
|---|---|
| `pod-crashloopbackoff` | `demo-fault-crashloop-*` |
| `pod-imagepullbackoff` | `demo-fault-imagepull-*` |
| `pod-pending` | `demo-fault-pending-*` / `demo-fault-replicas-mismatch-*` |
| `pvc-pending` | `demo-fault-pvc` |
| `deployment-replicas-mismatch` | `demo-fault-replicas-mismatch` |

6. warning/critical finding 已按 BR-09 转为告警；回告警工作台按 `source=huntai-inspection` 过滤可见；
7. 可对 finding 执行 ack / ignore / AI 解释。

### 3.4 事件：关联候选

验收脚本会自动创建关联规则并确认候选。手工体验：

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/correlation-rules \
  -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{
    "name":"manual-namespace-rule",
    "conditions":{"op":"AND","rules":[{"field":"namespace","operator":"eq","value":"manual-demo"}],"group_by":["namespace"]},
    "time_window_seconds":600,
    "mode":"candidate",
    "enabled":true
  }'
```

再向 `manual-demo` namespace 发两条不同 `alertname` 的告警，进入「候选事件」页确认；确认后生成事件，详情页可见关联告警与时间线。

### 3.5 AI 任务：NoAI 降级或 DeepSeek 外部调用

**默认（未配置外部模型）**

1. 在巡检 finding 上点「AI 解释」；
2. 进入「AI 任务中心」；
3. 预期任务最终为 `failed`，错误包含 `noai: 模型不可用或熔断开路`；
4. 打开任务详情，call-log 有一条 `result_code=error`。

这是设计内的 NoAI 降级（ADR-0005），因为本环境没有部署 Ollama。

**配置 DeepSeek 后（推荐用于验证真实模型链路）**

```bash
# .env 中填写 HUNTAI_AI_EXTERNAL_KEY，然后：
bash deploy/scripts/07-configure-ai.sh
bash deploy/scripts/05-run-acceptance.sh   # 自动识别为 deepseek 口径
# 或显式指定：HUNTAI_AI_MODE=deepseek bash deploy/scripts/05-run-acceptance.sh
```

预期：

- 任务最终 `completed`；
- `calls_used=1`、`tokens_used>0`；
- call-log 的 `model=external`、`result_code=ok`；
- 告警解释接口返回 `output.diagnosis` 非空，且不含 `noai`。

> key 只保存在 `.env` 和 `huntai/huntai-ai-secret`，不会进入 values、Chart 或日志。

### 3.6 值班与权限

1. 用 `oncall-may` 登录，进入「值班」页，创建排班与升级策略；
2. 用 `viewer-guest` 登录，访问告警页面应被 403 拦截；
3. 用 `dev-lee` 登录，只能看到 `platform` 团队的告警/事件（T 权限行级过滤）。

### 3.7 演示业务控制台

打开 http://127.0.0.1:18081：

- 两张卡片分别显示 Java 订单服务、Python 库存服务的实时响应；
- 点「触发 5xx」调用 `/java/api/orders/boom` 或 `/python/api/inventory/boom`；
- 点「触发慢请求」调用 `.../slow?ms=1500`；
- 这些 5xx 目前只用于演示业务行为；如需让 HuntAI 告警，请通过 webhook 上报或接入真实监控源。

## 4. 功能覆盖矩阵

| 能力 | 阶段 | 自动验收 | 手工体验 | 备注 |
|---|---|---|---|---|
| 登录 / 会话 / RBAC | P0 | ✅ | ✅ | viewer 403、admin 全量 |
| 告警 webhook / L1 去重 / 管道 | P0 | ✅ | ✅ | 5 次重复上报合并 |
| 告警 ACK / 关闭 / 误报建议 | P0 | ✅ | ✅ | |
| 集群接入 / 只读探活 | P0 | ✅ | ✅ | in-cluster SA token |
| 巡检规则 / 策略 / run / finding | P0 | ✅ | ✅ | 5 类真实故障 |
| BR-09 finding 转告警 | P0 | ✅ | ✅ | warning/critical |
| SSE 实时事件 | P0 | ✅ | ✅ | nginx 关闭缓冲 |
| Web SPA 与 API 同源代理 | P0 | ✅ | ✅ | |
| AI 任务 / NoAI 降级 / DeepSeek 外部调用 | P1 | ✅ | ✅ | 默认 NoAI；配置 key 后走 external |
| 关联规则 / 候选事件 / 确认转事件 | P2 | ✅ | ✅ | |
| 值班排班 / 升级策略 CRUD | P2 | ✅ | ✅ | 真实 IM 渠道为 dev 直通 |
| 通知记录 / 升级执行 | P2 | — | 可观察 | 验收未断言外呼 |
| 事件状态流转 / 复盘 / 状态页 | P2 | 部分 | ✅ | 验收覆盖创建与详情 |
| Workflow（P3 薄层） | P3 | — | — | 不在本次验收范围 |
| Java / Python / React 演示业务 | — | ✅ | ✅ | 含故障端点 |

## 5. 已知边界

1. **seed 的 3 条演示告警不会自动走管道**：`seed.py` 在 `--with-alerts` 时使用 no-op enqueue，因此它们是 `received` 状态；请用 CronJob 或手工 webhook 观察完整管道。
2. **NoAI 是默认预期行为**：没有 Ollama 且未配置外部模型时 AI 任务失败并落 `noai`；配置 DeepSeek 后应变为 `completed`。若 DeepSeek 模式仍失败，见 `04-troubleshooting.md` §7。
3. **关闭 faults 不会自动关闭历史 finding/告警**：它们保留审计；需要新的巡检才不会对已删资源产生新 finding。
4. **通知渠道是 dev 实现**：`DevImChannel` 只记 sent，不真正发 IM/SMS。
5. **单控制面**：kind 集群不是高可用；控制面故障不在演示范围。
6. **webhook 未加 token**：`demo-alertmanager` Provider 未配置 credential，方便演示；生产必须启用 `X-Provider-Token`。
7. **P3 Workflow 未覆盖**：本次验收聚焦 P0–P2。

## 6. 下一步

- 遇到问题：[04-troubleshooting.md](04-troubleshooting.md)
- 回到部署：[02-build-and-deploy.md](02-build-and-deploy.md)
