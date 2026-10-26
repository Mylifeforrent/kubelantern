# HuntAI SRE · 本地 kind 演示环境

本目录把 HuntAI SRE 平台、3 个演示业务工程（Java / Python / React）和故障注入场景打包成一套**可重复、可验证、可清理**的本地环境，用于：

- 新同学从零体验 HuntAI 的告警、巡检、事件、AI 治理、SSE 与权限能力；
- 开发自测前后端联调；
- 面试/演示时快速搭建一套真实 Kubernetes 环境。

> 仅用于本地学习与演示。所有口令都是占位符，禁止直接用于生产。

## 1. 六条命令跑起来

前置要求：Docker Desktop 正在运行；macOS/Linux 有 `brew`（或已安装 `kind`、`kubectl`、`helm`、`python3`、`curl`）。

```bash
bash deploy/scripts/00-prereqs.sh       # 检查工具、端口
bash deploy/scripts/01-create-cluster.sh # 3 节点 kind 集群
bash deploy/scripts/02-build-images.sh   # 构建 5 个镜像并 kind load
bash deploy/scripts/03-deploy-platform.sh # Helm 部署 HuntAI 平台
bash deploy/scripts/04-deploy-demo.sh     # Helm 部署演示业务（含故障）
bash deploy/scripts/05-run-acceptance.sh  # 端到端验收
```

完成后访问：

| 入口 | 地址 | 说明 |
|---|---|---|
| HuntAI 平台 | http://127.0.0.1:8080 | 用 `admin` / `your-demo-auth-password` 登录 |
| 演示业务控制台 | http://127.0.0.1:18081 | React 页面，可探测 Java/Python 服务并触发 5xx |
| 演示告警源 | 每 2 分钟自动上报 | 由 `demo-alert-reporter` CronJob 调用 HuntAI webhook |

演示账号（口令均为 `your-demo-auth-password`，可在 Helm values 覆盖）：

| 用户名 | 角色 | 用途 |
|---|---|---|
| `admin` | 管理员 | 全量功能与验收脚本 |
| `sre-tony` | SRE | 告警处置、巡检、事件 |
| `oncall-may` | 值班经理 | 排班/升级策略 |
| `dev-lee` | 研发（platform 团队） | 团队级行级过滤 |
| `viewer-guest` | 只读访客 | 验证越权拦截（告警列表 403） |

## 2. 目录结构

```text
deploy/
├── kind/
│   └── kind-config.yaml          # 1 control-plane + 2 worker，端口映射
├── helm/
│   ├── huntai-platform/          # PostgreSQL/Redis/API/5 worker/Web/RBAC/seed
│   └── huntai-demo/              # Java/Python/React + 故障注入 + 告警上报
├── demo-apps/
│   ├── java-order-service/       # Spring Boot 3 / Java 21
│   ├── python-inventory-service/ # FastAPI / Python 3.12
│   └── react-ops-console/        # React 19 + Vite
├── scripts/                      # 00~06 分步脚本（可单独执行）
└── tests/
    └── acceptance.py             # 端到端功能验收（纯标准库）
```

详细说明：

1. [kind 集群与端口](../docs/06-release/01-kind-demo-cluster.md)
2. [构建与部署](../docs/06-release/02-build-and-deploy.md)
3. [功能验收与手工体验](../docs/06-release/03-feature-acceptance.md)
4. [排障与清理](../docs/06-release/04-troubleshooting.md)

## 3. 常用操作

```bash
# 查看 3 个 kind 容器
docker ps --filter label=io.x-k8s.kind.cluster=huntai-sre

# 查看工作负载
kubectl -n huntai get pods,svc
kubectl -n demo    get deploy,pods,pvc

# 重新打开验收（不重建集群）
bash deploy/scripts/05-run-acceptance.sh

# 只跑 Python 验收脚本
HUNTAI_BASE_URL=http://127.0.0.1:8080/api/v1 \
HUNTAI_WEB_URL=http://127.0.0.1:8080 \
DEMO_CONSOLE_URL=http://127.0.0.1:18081 \
python3 deploy/tests/acceptance.py

# 关闭故障注入（观察巡检不再产生新 finding）
helm upgrade huntai-demo deploy/helm/huntai-demo -n demo --reuse-values \
  --set faults.enabled=false

# 清理
bash deploy/scripts/06-teardown.sh
```

## 4. 设计取舍

- **不用镜像仓库**：镜像构建后 `kind load docker-image` 直接进节点，离线/弱网更稳。
- **平台也部署在集群内**：巡检连接器使用只读 ServiceAccount token 访问同一个集群，能真实演示 BR-02 只读凭证与告警/巡检闭环。
- **故障注入是 Helm 开关**：`faults.enabled=true` 时创建 CrashLoop/ImagePull/Pending/PVC/副本不一致资源；关闭后资源删除，但历史 finding/告警保留。
- **AI 默认 NoAI**：不部署 Ollama；AI 任务会以 `failed` + `noai` 留痕，这是设计内的降级路径，不是故障。
- **演示口令是占位符**：`values.yaml` 中的口令仅用于本地，生产必须改用密钥管理。

## 5. 使用 DeepSeek 外部模型（可选）

默认 AI 走本地 Ollama；未部署本地模型时任务会落 `NoAI`。如果要接 DeepSeek：

1. 在仓库根 `.env` 填写（仅本地文件，已被 gitignore）：

   ```dotenv
   HUNTAI_AI_EGRESS_ENABLED=true
   HUNTAI_AI_EXTERNAL_URL=https://api.deepseek.com/v1
   HUNTAI_AI_EXTERNAL_MODEL=deepseek-chat
   HUNTAI_AI_EXTERNAL_KEY_REF=env:HUNTAI_AI_EXTERNAL_KEY
   HUNTAI_AI_EXTERNAL_KEY=<你的 DeepSeek key>
   ```

2. 创建集群 Secret 并开启外部路由：

   ```bash
   bash deploy/scripts/07-configure-ai.sh
   ```

   脚本从 `.env` 读取 key，创建 `huntai/huntai-ai-secret`，再执行 Helm upgrade；
   key 不会打印到终端，也不会写入 values/Chart。

3. 用 DeepSeek 模式验收：

   ```bash
   HUNTAI_AI_MODE=deepseek bash deploy/scripts/05-run-acceptance.sh
   ```

   AI 步骤应显示 `status=completed provider=external`，并能在 AI 任务详情看到
   `ai_explanations` 中的诊断文本。

## 6. 安全与提交

```bash
# 手工扫描新增文件（仓库护栏）
python3 .zcode/scripts/secret_scan.py path deploy/README.md

# 新克隆环境安装 git hooks
bash .zcode/scripts/setup-git-hooks.sh
```

禁止把 `.env`、kubeconfig、token、真实凭据提交进仓库。
