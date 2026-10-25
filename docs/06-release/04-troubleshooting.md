# 排障与清理

> 状态：accepted ｜ 日期：2026-10-25 ｜ 读者：遇到部署/验收问题的人
> 先按「症状 → 快速定位 → 处理」执行；每条命令都可直接复制。

## 1. 一分钟定位

```bash
kubectl get nodes
kubectl -n huntai get pods -o wide
kubectl -n huntai get jobs,pvc
kubectl -n demo get deploy,pods,pvc -o wide
kubectl -n huntai logs deploy/huntai-api --tail=80
kubectl -n huntai logs job/huntai-seed --tail=80
```

| 现象 | 优先看 |
|---|---|
| 无法访问 8080 | `kubectl -n huntai get svc huntai-web`、`docker ps`、端口占用 |
| 平台 Pod Pending | `kubectl -n huntai describe pod <pod>` 的 Events |
| Pod `CreateContainerConfigError` | Secret/SA token 是否就绪 |
| 巡检 run failed | 集群探活是否 connected、inspection worker 日志 |
| AI 任务 failed + noai | 预期行为，不是故障 |
| 镜像拉取失败 | Docker Hub/加速器、`kind load` 是否执行 |

## 2. Docker / kind

### 2.1 `docker pull` TLS handshake timeout

Docker Hub 直连不稳定：

```bash
# 使用脚本内置加速器
PULL_MIRROR=docker.1ms.run bash deploy/scripts/01-create-cluster.sh

# 或者先手动拉取再重跑
docker pull docker.1ms.run/kindest/node:v1.37.0
docker tag docker.1ms.run/kindest/node:v1.37.0 kindest/node:v1.37.0
bash deploy/scripts/01-create-cluster.sh
```

如果 kind 版本与节点镜像不匹配，显式指定：

```bash
KIND_NODE_IMAGE=kindest/node:v1.37.0 bash deploy/scripts/01-create-cluster.sh
```

### 2.2 宿主机端口被占用

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN
lsof -nP -iTCP:18081 -sTCP:LISTEN
```

处理方式：

1. 停掉占用端口的进程；或
2. 修改 `deploy/kind/kind-config.yaml` 的 `hostPort`；
3. 同步修改两个 chart 的 `nodePort`；
4. 删除并重建集群。

### 2.3 节点 NotReady

刚创建时等 30–60 秒；仍 NotReady 时：

```bash
kubectl describe node huntai-sre-worker | tail -40
docker logs huntai-sre-worker --tail=100
```

若 Docker Desktop 内存不足，调大 Resources → Memory 后重建集群。

### 2.4 想彻底重来

```bash
bash deploy/scripts/06-teardown.sh
# 或保留集群只删 release
KEEP_CLUSTER=1 bash deploy/scripts/06-teardown.sh
kind delete cluster --name huntai-sre
```

## 3. 镜像构建

### 3.1 后端构建报 `Readme file does not exist: frontend/README.md`

`Dockerfile` 已包含：

```dockerfile
COPY frontend/README.md ./frontend/README.md
```

如果自行改过 Dockerfile 导致该行丢失，补回即可。

### 3.2 Java 构建在容器内访问 Maven Central 超时

`02-build-images.sh` 已改为**宿主机 Maven 先打 jar**，再构建 JRE 运行镜像：

```bash
cd deploy/demo-apps/java-order-service && mvn -B package -DskipTests
```

没有宿主机 Maven 时，脚本会回退到 `Dockerfile.build`（多阶段 Maven）。若容器内网络仍不稳定，可配置 Maven 镜像后再重试。

### 3.3 重新 load 镜像后 Pod 还是旧代码

`imagePullPolicy: IfNotPresent` 不会自动拉同 tag 的新镜像：

```bash
kind load docker-image huntai-sre:dev --name huntai-sre
kubectl -n huntai rollout restart deploy/huntai-api
```

## 4. Helm 平台部署

### 4.1 `helm upgrade --install` 10 分钟超时

```bash
kubectl -n huntai get pods
kubectl -n huntai describe pod <未 Ready 的 pod>
kubectl -n huntai logs <pod> --previous
```

常见原因：

- PostgreSQL 没起来 → PVC 未绑定 / 资源不足；
- API initContainer 迁移失败 → 数据库连接串或迁移脚本错误；
- seed hook 等 API 超时 → API 未 Ready。

修复后直接重跑：

```bash
bash deploy/scripts/03-deploy-platform.sh
```

### 4.2 登录提示「用户不存在或已停用」

seed 没执行成功：

```bash
kubectl -n huntai get jobs
kubectl -n huntai logs job/huntai-seed
```

手动重跑：

```bash
kubectl -n huntai delete job huntai-seed --ignore-not-found
helm upgrade huntai deploy/helm/huntai-platform -n huntai --reuse-values
```

### 4.3 集群探活为 `disconnected`

说明只读 token 没有注入成功。

```bash
kubectl -n huntai get sa huntai-readonly
kubectl -n huntai get secret huntai-readonly-token
kubectl -n huntai get secret huntai-readonly-token -o jsonpath='{.data.token}' | wc -c
kubectl -n huntai exec deploy/huntai-api -- sh -c 'test -n "$HUNTAI_DEMO_CLUSTER_TOKEN" && echo token-present'
```

若 token 为空：等待 controller 填充，再重启 API/worker：

```bash
kubectl -n huntai rollout restart deploy/huntai-api
kubectl -n huntai rollout restart deploy/huntai-worker-inspection
```

### 4.4 API/worker 启动即退出

```bash
kubectl -n huntai logs deploy/huntai-api --previous
```

重点检查：

- `HUNTAI_DATABASE_URL`/`HUNTAI_REDIS_URL` 是否指向正确 Service；
- `HUNTAI_MASK_KEY` 是否是 32 字节 base64；
- PostgreSQL/Redis 是否 Ready。

## 5. 演示业务

### 5.1 Java/Python Pod CrashLoopBackOff

先确认是不是故意注入的故障：

```bash
kubectl -n demo get pods -l huntai.io/fault
kubectl -n demo get pods -l app.kubernetes.io/name=java-order-service
```

- `demo-fault-*` 的 CrashLoop 是预期；
- 正常业务 Pod 请 `kubectl -n demo logs deploy/java-order-service` 查看启动错误。

### 5.2 演示控制台 502

```bash
kubectl -n demo get pods
kubectl -n demo logs deploy/react-ops-console --tail=50
kubectl -n demo get svc java-order-service python-inventory-service
```

nginx 代理依赖两个 Service 名称；如果改名，同步修改 `templates/react-console.yaml` 的 ConfigMap。

### 5.3 故障资源没有出现

```bash
kubectl -n demo get deploy | grep demo-fault
helm get values huntai-demo -n demo | grep -A8 faults
```

`faults.enabled` 必须为 `true`。重新打开：

```bash
helm upgrade huntai-demo deploy/helm/huntai-demo -n demo --reuse-values \
  --set faults.enabled=true
```

ImagePullBackOff 需要节点实际尝试拉取后才能进入该状态，通常 30–60 秒。

## 6. 巡检与告警

### 6.1 巡检 run failed

```bash
kubectl -n huntai logs deploy/huntai-worker-inspection --tail=100
```

常见原因：

- 集群探活不是 `connected`（先修 4.3）；
- 只读 SA 权限不足（`huntai-readonly` ClusterRole 是否绑定、是否包含 `nodes` 列表权限）；
- 快照拉取网络失败。

### 6.2 巡检成功但没有 finding

```bash
kubectl -n demo get pods,pvc,deploy
helm get values huntai-demo -n demo | grep -A8 faults
```

- 故障资源是否已进入目标状态；
- 策略是否勾选了对应规则；
- 同一资源同一规则的 **open finding 会被复用**，不会重复计数；先处理旧 finding 或换资源。

### 6.3 告警一直 `received`

```bash
kubectl -n huntai get pods | grep alert-pipeline
kubectl -n huntai logs deploy/huntai-worker-alert-pipeline --tail=100
```

- seed 的 3 条演示告警是 no-op enqueue，保持 `received` 属预期；
- 手工 webhook/CronJob 产生的告警应推进到 `notified`；
- 检查 Redis/PG 是否健康。

### 6.4 SSE 没有事件

```bash
curl -N -H "Authorization: Bearer $TOKEN" \
  'http://127.0.0.1:8080/api/v1/realtime/stream?topics=alerts'
```

- 先用 `$TOKEN` 确认已登录；
- SSE 默认从订阅时刻开始推（无 `Last-Event-ID`），先连接再触发告警；
- nginx 已配置 `proxy_buffering off`，若自行改 ConfigMap 不要删掉；
- 心跳每 15 秒一次，看到 `: ping` 说明连接正常。

## 7. AI 任务

看到：

```text
status = failed
error  = noai: 模型不可用或熔断开路（ADR-0005）
```

这是**预期**：本环境没有 Ollama。若要接真实模型：

```bash
helm upgrade huntai deploy/helm/huntai-platform -n huntai --reuse-values \
  --set config.aiLocalEndpoint='http://<ollama-service>:11434' \
  --set config.aiLocalModel='llama3.1'
kubectl -n huntai rollout restart deploy/huntai-api deploy/huntai-worker-ai
```

## 8. 验收脚本失败

```bash
# 查看完整请求/断言
python3 deploy/tests/acceptance.py

# 跳过 kubectl 检查（例如没有 kubectl 权限）
KUBECTL_CHECK=0 python3 deploy/tests/acceptance.py
```

常见原因：

- 平台/演示 Pod 未 Ready；
- 口令与 `secrets.devAuthPassword` 不一致；
- 端口不是 8080/18081（用 `HUNTAI_WEB_URL`/`DEMO_CONSOLE_URL` 覆盖）；
- 故障资源还没进入目标状态（加大 `FAULT_SETTLE_SECONDS`）。

## 9. 收集诊断包

```bash
mkdir -p /tmp/huntai-diag
kubectl -n huntai get all,pvc,secret -o wide > /tmp/huntai-diag/platform.txt
kubectl -n demo   get all,pvc        -o wide > /tmp/huntai-diag/demo.txt
kubectl -n huntai describe pods > /tmp/huntai-diag/platform-pods.txt
kubectl -n demo   describe pods > /tmp/huntai-diag/demo-pods.txt
docker ps --filter label=io.x-k8s.kind.cluster=huntai-sre > /tmp/huntai-diag/docker.txt
```

分享前请检查文件，**不要包含真实 token/凭据**。
