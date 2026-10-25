#!/usr/bin/env bash
# 04 部署演示业务（Java + Python + React，默认带故障注入）。
source "$(dirname "$0")/lib.sh"

ensure_tools
ensure_cluster

FAULTS_ENABLED="${FAULTS_ENABLED:-true}"
CHART_DIR="${DEPLOY_DIR}/helm/huntai-demo"
[[ -f "${CHART_DIR}/Chart.yaml" ]] || die "找不到 chart：${CHART_DIR}"

log "Helm 安装/升级演示业务（faults.enabled=${FAULTS_ENABLED}）"
# 故障 Deployment 永远不会 Ready，开启故障时不能用 Helm --wait，否则必然超时。
if [[ "${FAULTS_ENABLED}" == "false" ]]; then
  helm upgrade --install "${DEMO_RELEASE_NAME}" "${CHART_DIR}" \
    --namespace "${DEMO_NAMESPACE}" \
    --create-namespace \
    --set "faults.enabled=${FAULTS_ENABLED}" \
    --wait \
    --timeout 8m
else
  helm upgrade --install "${DEMO_RELEASE_NAME}" "${CHART_DIR}" \
    --namespace "${DEMO_NAMESPACE}" \
    --create-namespace \
    --set "faults.enabled=${FAULTS_ENABLED}"
fi

log "等待三个健康业务 Deployment 就绪"
kubectl -n "${DEMO_NAMESPACE}" rollout status deploy/java-order-service --timeout=240s
kubectl -n "${DEMO_NAMESPACE}" rollout status deploy/python-inventory-service --timeout=120s
kubectl -n "${DEMO_NAMESPACE}" rollout status deploy/react-ops-console --timeout=120s

log "演示工作负载"
kubectl -n "${DEMO_NAMESPACE}" get deploy,pods,pvc -o wide

wait_for_http "http://127.0.0.1:18081/" 120
ok "演示控制台：http://127.0.0.1:18081"
ok "下一步：bash deploy/scripts/05-run-acceptance.sh"
