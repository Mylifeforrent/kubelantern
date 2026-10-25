#!/usr/bin/env bash
# 01 创建 3 节点 kind 集群（1 control-plane + 2 worker = 3 个 Docker 容器）。
source "$(dirname "$0")/lib.sh"

ensure_tools
need_cmd kind
prepare_kind_node_image

if kind get clusters 2>/dev/null | grep -qx "${KIND_CLUSTER_NAME}"; then
  ok "kind 集群 ${KIND_CLUSTER_NAME} 已存在，跳过创建"
else
  log "创建 kind 集群 ${KIND_CLUSTER_NAME}（首次会拉取 kindest/node 镜像）"
  kind create cluster \
    --name "${KIND_CLUSTER_NAME}" \
    --config "${DEPLOY_DIR}/kind/kind-config.yaml" \
    --wait 180s
fi

kubectl config use-context "kind-${KIND_CLUSTER_NAME}" >/dev/null
log "节点列表"
kubectl get nodes -o wide

log "Docker 容器列表（应恰好 3 个 kind node 容器）"
docker ps --filter "label=io.x-k8s.kind.cluster=${KIND_CLUSTER_NAME}" \
  --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'

ok "集群就绪。下一步：bash deploy/scripts/02-build-images.sh"
