#!/usr/bin/env bash
# 03 部署 HuntAI 平台到 kind（PostgreSQL/Redis/API/5 worker/Web）。
source "$(dirname "$0")/lib.sh"

ensure_tools
ensure_cluster

CHART_DIR="${DEPLOY_DIR}/helm/huntai-platform"
[[ -f "${CHART_DIR}/Chart.yaml" ]] || die "找不到 chart：${CHART_DIR}"

log "Helm 安装/升级 HuntAI 平台（namespace=${PLATFORM_NAMESPACE}）"
helm upgrade --install "${RELEASE_NAME}" "${CHART_DIR}" \
  --namespace "${PLATFORM_NAMESPACE}" \
  --create-namespace \
  --wait \
  --timeout 10m

log "工作负载状态"
kubectl -n "${PLATFORM_NAMESPACE}" get pods -o wide

log "等待 Web 入口可用"
wait_for_http "http://127.0.0.1:8080/healthz" 120
ok "HuntAI Web：http://127.0.0.1:8080（管理员 admin / values.secrets.devAuthPassword）"
ok "下一步：bash deploy/scripts/04-deploy-demo.sh"
