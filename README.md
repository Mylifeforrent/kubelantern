# huntai-sre

AI 原生 Kubernetes SRE 平台：告警接入与降噪、巡检诊断、事件与值班闭环、AI 能力治理，以及可观测的实时工作台。

- 后端：Python 3.12 + FastAPI + arq + PostgreSQL + Redis（`src/huntai/`）
- 前端：React 19 + TypeScript + Vite + Tailwind（`frontend/`）
- 设计文档：`docs/`（PRD、领域模型、HLD、前后端详设、API 契约、联调报告）
- 本地演示环境：`deploy/`（3 节点 kind 集群、Helm Chart、Java/Python/React 示例、故障注入、端到端验收）

## 快速开始

### 方式一：本地 kind 演示环境（推荐给新同学）

需要 Docker Desktop（建议 8 核 / 12 GB 以上）、`kind`、`kubectl`、`helm`、`python3`、`curl`。

```bash
bash deploy/scripts/00-prereqs.sh
bash deploy/scripts/01-create-cluster.sh
bash deploy/scripts/02-build-images.sh
bash deploy/scripts/03-deploy-platform.sh
bash deploy/scripts/04-deploy-demo.sh
bash deploy/scripts/05-run-acceptance.sh
```

完成后：

- HuntAI 平台：http://127.0.0.1:8080（`admin` / `your-demo-auth-password`）
- 演示业务控制台：http://127.0.0.1:18081

详细说明见 [deploy/README.md](deploy/README.md)，以及：

1. [kind 演示集群](docs/06-release/01-kind-demo-cluster.md)
2. [构建与部署](docs/06-release/02-build-and-deploy.md)
3. [功能验收与手工体验](docs/06-release/03-feature-acceptance.md)
4. [排障与清理](docs/06-release/04-troubleshooting.md)

### 方式二：本地 Compose（仅后端依赖）

```bash
cp .env.example .env       # 填入本地占位值
docker compose up -d postgres redis
uv sync
uv run alembic upgrade head
uv run python -m huntai.seed --with-alerts
uv run huntai-api
```

前端：

```bash
cd frontend
npm install
npm run dev
```

## 常用验证命令

```bash
# 后端单测（不依赖 PG/Redis）
.venv/bin/python -m pytest tests/unit -q

# 前端单测
cd frontend && npm run test

# Helm lint
helm lint deploy/helm/huntai-platform --strict
helm lint deploy/helm/huntai-demo --strict

# 凭据扫描（对文件；批量可配合 find/xargs）
python3 .zcode/scripts/secret_scan.py path deploy/README.md
```

## 文档与约定

- 文档地图：[docs/README.md](docs/README.md)
- 项目规则：[AGENTS.md](AGENTS.md)
- 安全红线：真实凭据只放 `.env` 或密钥管理服务；禁止提交 `.env`、私钥、token；禁止 `git commit --no-verify`。
- 提交前请确保相关验证命令已运行；AI 生成代码同样适用。

## 目录速览

```text
src/huntai/       后端模块化单体（app/domains/gateway/pipeline/workers/realtime）
frontend/         React SPA
docs/             设计与交付文档（docs/README.md 为唯一入口）
deploy/           kind 演示环境：kind 配置、Helm Chart、示例工程、脚本、验收
migrations/       Alembic 迁移
tests/            后端单元/集成/E2E 流程测试
```
