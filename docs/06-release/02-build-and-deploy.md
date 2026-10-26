# 构建与部署

> 状态：accepted ｜ 日期：2026-10-25 ｜ 读者：开发/测试/演示人员
> 依据：`docs/03-tech-design/02-architecture.md` §3.1/§6、`docs/03-tech-design/04-backend-design.md` §1.7、本仓库 `Dockerfile` 与 `deploy/helm/`。

## 1. 总览

一次完整部署分三步：

1. 构建 5 个本地镜像并加载进 kind；
2. Helm 部署 `huntai` 平台；
3. Helm 部署 `huntai-demo` 演示业务。

```bash
bash deploy/scripts/02-build-images.sh
bash deploy/scripts/03-deploy-platform.sh
bash deploy/scripts/04-deploy-demo.sh
```

首次构建需要下载 Python/npm/Maven 依赖，通常 8–15 分钟；后续重建会命中 Docker 层缓存。

## 2. 镜像清单

| 镜像 | 构建上下文 | 用途 |
|---|---|---|
| `huntai-sre:dev` | 仓库根 | API + 5 类 worker 同镜像多角色 |
| `huntai-web:dev` | `frontend/` | nginx + Vite 构建的 SPA |
| `huntai-demo/java-order-service:dev` | `deploy/demo-apps/java-order-service` | Spring Boot 订单服务 |
| `huntai-demo/python-inventory-service:dev` | `deploy/demo-apps/python-inventory-service` | FastAPI 库存服务 |
| `huntai-demo/react-ops-console:dev` | `deploy/demo-apps/react-ops-console` | React 演示控制台 |

`02-build-images.sh` 还会准备并加载 `postgres:16-alpine`、`redis:7-alpine`，避免 kind 节点运行时再拉取。

手动构建等价命令：

```bash
docker build -t huntai-sre:dev .
docker build -t huntai-web:dev frontend
# Java 先打 jar，再构建 JRE 运行镜像
(cd deploy/demo-apps/java-order-service && mvn -B package -DskipTests)
docker build -t huntai-demo/java-order-service:dev deploy/demo-apps/java-order-service
docker build -t huntai-demo/python-inventory-service:dev deploy/demo-apps/python-inventory-service
docker build -t huntai-demo/react-ops-console:dev deploy/demo-apps/react-ops-console

for image in \
  huntai-sre:dev huntai-web:dev \
  huntai-demo/java-order-service:dev \
  huntai-demo/python-inventory-service:dev \
  huntai-demo/react-ops-console:dev \
  postgres:16-alpine redis:7-alpine; do
  kind load docker-image "$image" --name huntai-sre
done
```

> Java 工程默认使用宿主机 Maven 打 jar，避免容器内访问 Maven Central 超时。宿主机没有 `mvn` 时，
> `02-build-images.sh` 会自动回退到 `Dockerfile.build`（多阶段 Maven 构建）。

## 3. 部署平台（namespace `huntai`）

```bash
bash deploy/scripts/03-deploy-platform.sh
```

等价的 Helm 命令：

```bash
helm upgrade --install huntai deploy/helm/huntai-platform \
  --namespace huntai --create-namespace \
  --wait --timeout 10m
```

### 3.1 Chart 做了什么

| 资源 | 说明 |
|---|---|
| `Secret/huntai-secrets` | 数据库/Redis 连接串、认证密钥、掩码密钥（仅演示占位符） |
| `StatefulSet/huntai-postgres` | PostgreSQL 16，2 Gi PVC，readiness 用 `pg_isready` |
| `Deployment/huntai-redis` | Redis 7，不持久化 |
| `Deployment/huntai-api` | FastAPI；initContainer 等 PG → `alembic upgrade head` → 等只读 token；`enableServiceLinks: false` 避免 Service 注入的 `HUNTAI_API_PORT` 覆盖配置 |
| `Deployment/huntai-worker-*` | 5 条队列：`alert-pipeline`、`notification`、`escalation`、`inspection`、`ai`；等 API ready 后启动 |
| `Deployment/huntai-web` | nginx 托管 SPA，`/api/` 反代 API，SSE 关闭缓冲 |
| `Service/huntai-web` | NodePort `30080`，映射宿主机 `8080` |
| `ServiceAccount/huntai-readonly` + `ClusterRole/huntai-readonly` + Binding | 巡检连接器只读凭证（BR-02）；只授予 pods/deployments/pvcs/nodes 的 get/list/watch |
| `Secret/huntai-readonly-token` | 长期 SA token，API/Worker 通过环境变量注入 |
| `Job/huntai-seed` | Helm post-install/post-upgrade hook：迁移完成后执行 `python -m huntai.seed --with-alerts` |

### 3.2 启动顺序与自愈

```text
PostgreSQL ready
  └─ api initContainer: alembic upgrade head
       └─ api ready (/healthz)
            ├─ worker initContainer: 等 API ready + 等只读 token
            └─ seed hook Job: 等 API ready → seed 角色/用户/演示集群/规则
```

任何一步失败，对应 Pod/Job 都会保持失败状态便于排查；`helm install --wait` 会在 10 分钟后超时报错。

### 3.3 验证

```bash
kubectl -n huntai get pods
kubectl -n huntai get svc
kubectl -n huntai logs deploy/huntai-api --tail=50
kubectl -n huntai logs job/huntai-seed --tail=50
curl -s http://127.0.0.1:8080/healthz
```

预期所有 Pod `Running` / `Ready`，`huntai-web` 的 `NodePort` 为 `30080`，`/healthz` 返回 `{"status":"ok"}`。

## 4. 部署演示业务（namespace `demo`）

```bash
bash deploy/scripts/04-deploy-demo.sh
```

等价命令（默认打开故障注入）：

```bash
helm upgrade --install huntai-demo deploy/helm/huntai-demo \
  --namespace demo --create-namespace \
  --set faults.enabled=true \
  --wait --timeout 8m
```

### 4.1 演示工程

| 工程 | 端口 | 接口 | 用途 |
|---|---|---|---|
| Java `java-order-service` | 8080 | `GET /api/orders`、`POST /api/orders`、`GET /api/orders/boom`、`GET /api/orders/slow` | 正常流量 + 可控 5xx/慢请求 |
| Python `python-inventory-service` | 8000 | `GET /api/inventory`、`POST /api/inventory`、`GET /api/inventory/boom`、`GET /api/inventory/slow` | 正常流量 + 可控 5xx/慢请求；`CRASH_ON_START=1` 用于故障注入 |
| React `react-ops-console` | 80 | `/java/*`、`/python/*` 反向代理 | 同源展示两个服务状态并触发故障 |

### 4.2 故障注入

`values.yaml` 的 `faults` 段控制 5 类真实 K8s 故障：

| 开关 | 资源 | 预期状态 | 对应巡检规则 |
|---|---|---|---|
| `crashloop` | Deployment `demo-fault-crashloop` | Pod `CrashLoopBackOff` / restartCount 增长 | `pod-crashloopbackoff` |
| `imagepull` | Deployment `demo-fault-imagepull` | Pod `ImagePullBackOff` / `ErrImagePull` | `pod-imagepullbackoff` |
| `pending` | Deployment `demo-fault-pending` | Pod `Pending`（请求 64 核） | `pod-pending` |
| `pvc` | PVC `demo-fault-pvc` | PVC `Pending`（不存在的 StorageClass） | `pvc-pending` |
| `replicasMismatch` | Deployment `demo-fault-replicas-mismatch` | ready 0 / desired 2 | `deployment-replicas-mismatch` |

打开/关闭：

```bash
# 打开（会重新创建故障资源）
helm upgrade huntai-demo deploy/helm/huntai-demo -n demo --reuse-values \
  --set faults.enabled=true

# 关闭（删除故障资源）
helm upgrade huntai-demo deploy/helm/huntai-demo -n demo --reuse-values \
  --set faults.enabled=false
```

> 关闭故障资源**不会**自动把历史 finding/告警改为 resolved；它们保留用于审计。下一次巡检不会再为已删除的资源产生新 finding。

### 4.3 演示告警源

`demo-alert-reporter` CronJob 每 2 分钟向：

```text
http://huntai-api.huntai.svc.cluster.local:8000/api/v1/alerts/webhook/demo-alertmanager
```

上报一条 `DemoServiceErrorRateHigh` 告警。相同 fingerprint 会命中 L1 去重，`occurrence_count` 持续增加，适合观察告警工作台和 SSE。

手动触发：

```bash
kubectl -n demo create job --from=cronjob/demo-alert-reporter manual-alert-$(date +%s)
```

## 5. 修改演示口令

默认值仅用于本地：

| values 键 | 默认值 |
|---|---|
| `secrets.databasePassword` | `your-demo-db-password` |
| `secrets.authSecret` | `your-demo-auth-secret` |
| `secrets.devAuthPassword` | `your-demo-auth-password` |
| `secrets.maskKey` | 固定 32 字节 base64（仅演示） |

修改示例：

```bash
helm upgrade huntai deploy/helm/huntai-platform -n huntai --reuse-values \
  --set secrets.devAuthPassword='your-new-demo-password'
```

生成新的掩码密钥（32 字节 base64）：

```bash
python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

> 更换 `maskKey` 后，旧的 `ai_mask_mappings.encrypted_original` 无法解密。演示环境可直接清库重建；生产必须走密钥轮换方案。

## 6. 外部 AI（DeepSeek）

默认 `config.aiEgressEnabled=false`，AI 任务走本地 Ollama 或 NoAI。启用外部 OpenAI 兼容模型：

1. 在仓库根 `.env` 填写（`.env` 已被 gitignore，禁止提交）：

   ```dotenv
   HUNTAI_AI_EGRESS_ENABLED=true
   HUNTAI_AI_EXTERNAL_URL=https://api.deepseek.com/v1
   HUNTAI_AI_EXTERNAL_MODEL=deepseek-chat
   HUNTAI_AI_EXTERNAL_KEY_REF=env:HUNTAI_AI_EXTERNAL_KEY
   HUNTAI_AI_EXTERNAL_KEY=<你的 DeepSeek key>
   ```

2. 执行配置脚本：

   ```bash
   bash deploy/scripts/07-configure-ai.sh
   ```

   脚本会从 `.env` 读取 key，创建/更新 `huntai-ai-secret`，再以
   `config.aiEgressEnabled=true` 执行 Helm upgrade，并等待 AI worker 就绪。
   key 不会出现在命令行参数、values、Chart 或日志中。

3. 验证：

   ```bash
   HUNTAI_AI_MODE=deepseek bash deploy/scripts/05-run-acceptance.sh
   ```

相关 values：

| 键 | 默认 | 说明 |
|---|---|---|
| `config.aiEgressEnabled` | `false` | 出域开关；`07` 会设为 `true` |
| `config.aiExternalUrl` | `https://api.deepseek.com/v1` | Provider 会追加 `/chat/completions` |
| `config.aiExternalModel` | `deepseek-chat` | 也可用 `deepseek-reasoner` |
| `config.aiExternalKeyRef` | `env:HUNTAI_AI_EXTERNAL_KEY` | secret_ref 引用 |
| `ai.externalKeySecretName` | `huntai-ai-secret` | 由 `07` 创建的集群 Secret |
| `ai.externalKeySecretKey` | `apiKey` | Secret 中的数据键 |

路由规则：`aiEgressEnabled=true` 且外部 URL/key_ref 完整时，AI 任务走
`external` Provider；否则走 `local`（不可用时降级 NoAI）。默认仍满足 BR-12「不出域」。

## 7. 代码改动后的重建

```bash
# 只改后端
docker build -t huntai-sre:dev . && kind load docker-image huntai-sre:dev --name huntai-sre
kubectl -n huntai rollout restart deploy/huntai-api
kubectl -n huntai rollout restart deploy -l app.kubernetes.io/part-of=huntai-sre

# 只改前端
docker build -t huntai-web:dev frontend && kind load docker-image huntai-web:dev --name huntai-sre
kubectl -n huntai rollout restart deploy/huntai-web

# 只改演示应用
docker build -t huntai-demo/python-inventory-service:dev deploy/demo-apps/python-inventory-service
kind load docker-image huntai-demo/python-inventory-service:dev --name huntai-sre
kubectl -n demo rollout restart deploy/python-inventory-service
```

注意：`imagePullPolicy` 为 `IfNotPresent`，重新 load 同 tag 后必须 `rollout restart` 才会用新镜像。

## 8. 升级与回滚

```bash
helm list -A
helm history huntai -n huntai
helm rollback huntai 1 -n huntai
```

演示业务同理：`helm history huntai-demo -n demo` / `helm rollback huntai-demo <REVISION> -n demo`。

## 9. 下一步

- [03-feature-acceptance.md](03-feature-acceptance.md)：自动验收与手工体验
- [04-troubleshooting.md](04-troubleshooting.md)：常见问题
