# kind 演示集群（3 节点）

> 状态：accepted ｜ 日期：2026-10-25 ｜ 读者：第一次接触本项目的开发/测试/演示人员
> 依据：`docs/03-tech-design/02-architecture.md` §3.4 部署形态、§6 进程拓扑；本机资源实测。

## 1. 目标形态

```text
宿主机
├── Docker Desktop
│   ├── huntai-sre-control-plane   (kind 节点，承载控制面)
│   ├── huntai-sre-worker          (kind 节点，承载工作负载)
│   └── huntai-sre-worker2         (kind 节点，承载工作负载)
│
├── host:8080  ──► nodePort 30080 ──► huntai-web (nginx + React SPA)
│                                      └── /api/ ──► huntai-api:8000
└── host:18081 ──► nodePort 30081 ──► react-ops-console (演示控制台)
                                       ├── /java/   ──► java-order-service:8080
                                       └── /python/ ──► python-inventory-service:8000
```

集群内命名空间：

| Namespace | 内容 |
|---|---|
| `huntai` | PostgreSQL、Redis、API、5 类 arq worker、Web SPA、只读 RBAC、seed Job |
| `demo` | Java 订单服务、Python 库存服务、React 控制台、故障注入资源、告警上报 CronJob |

## 2. 资源建议

| 项目 | 最低 | 推荐 |
|---|---|---|
| Docker CPU | 6 核 | 8 核及以上 |
| Docker 内存 | 10 GB | 12–16 GB |
| 磁盘 | 15 GB 空闲 | 25 GB |

实测：1 个 control-plane + 2 个 worker、平台 8 个 Pod、演示业务约 8–10 个 Pod，在 24 GB / 12 核的 macOS 上可稳定运行。故障注入的 Pending Pod 不占实际 CPU，但会显示在调度队列中。

## 3. 创建集群

```bash
bash deploy/scripts/00-prereqs.sh
bash deploy/scripts/01-create-cluster.sh
```

脚本会：

1. 检查 Docker daemon、kind、kubectl、helm、python3、curl；
2. 检查宿主机 8080 / 18081 是否被占用；
3. 准备 `kindest/node:v1.37.0` 镜像；
4. 用 `deploy/kind/kind-config.yaml` 创建集群；
5. 输出节点列表和 3 个 Docker 容器。

预期输出：

```text
NAME                       STATUS   ROLES           AGE   VERSION
huntai-sre-control-plane   Ready    control-plane   ...   v1.37.0
huntai-sre-worker          Ready    <none>          ...   v1.37.0
huntai-sre-worker2         Ready    <none>          ...   v1.37.0

NAMES                      STATUS   IMAGE
huntai-sre-control-plane   Up ...   kindest/node:v1.37.0
huntai-sre-worker2         Up ...   kindest/node:v1.37.0
huntai-sre-worker          Up ...   kindest/node:v1.37.0
```

> 集群刚创建时 worker 可能短暂 `NotReady`，CNI 初始化完成后会变成 `Ready`。可执行
> `kubectl wait --for=condition=Ready nodes --all --timeout=120s` 等待。

## 4. 端口映射

`deploy/kind/kind-config.yaml` 中固定了：

| 宿主机 | 节点 NodePort | 服务 |
|---|---|---|
| `8080` | `30080` | HuntAI Web（SPA + `/api` 同源代理） |
| `18081` | `30081` | 演示业务控制台 |

如果宿主机端口被占用：

1. 修改 `kind-config.yaml` 的 `hostPort`；
2. 修改 `deploy/helm/huntai-platform/values.yaml` 的 `web.nodePort` 和 `deploy/helm/huntai-demo/values.yaml` 的 `console.nodePort`；
3. 用 `HUNTAI_WEB_URL`、`DEMO_CONSOLE_URL` 环境变量覆盖验收脚本地址；
4. 删除并重建集群（`kind delete cluster --name huntai-sre`）。

## 5. 网络与镜像加速

Docker Hub 直连不稳定时，脚本默认使用 `PULL_MIRROR=docker.1ms.run`：

```bash
# 使用默认加速器
bash deploy/scripts/01-create-cluster.sh

# 强制直连（网络良好时）
PULL_MIRROR="" bash deploy/scripts/01-create-cluster.sh
```

当前 kind 0.33 的默认节点镜像是 `kindest/node:v1.37.0`。若你升级了 kind 且默认版本变化，用环境变量覆盖：

```bash
KIND_NODE_IMAGE=kindest/node:v1.36.0 bash deploy/scripts/01-create-cluster.sh
```

## 6. 验证集群

```bash
kubectl cluster-info
kubectl get nodes -o wide
kubectl get storageclass
docker ps --filter label=io.x-k8s.kind.cluster=huntai-sre
```

`storageclass` 应包含 kind 默认的 `standard`（供 PostgreSQL PVC 使用）。

## 7. 下一步

- 构建与部署：[02-build-and-deploy.md](02-build-and-deploy.md)
- 功能验收：[03-feature-acceptance.md](03-feature-acceptance.md)
- 排障与清理：[04-troubleshooting.md](04-troubleshooting.md)
