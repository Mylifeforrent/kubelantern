#!/usr/bin/env bash
# 05 运行端到端功能验收（覆盖告警/巡检/事件/AI NoAI/SSE/权限/演示业务）。
source "$(dirname "$0")/lib.sh"

ensure_tools
ensure_cluster

FAULT_SETTLE_SECONDS="${FAULT_SETTLE_SECONDS:-45}"
HUNTAI_WEB_URL="${HUNTAI_WEB_URL:-http://127.0.0.1:8080}"
DEMO_CONSOLE_URL="${DEMO_CONSOLE_URL:-http://127.0.0.1:18081}"

log "等待演示业务就绪"
kubectl -n "${DEMO_NAMESPACE}" rollout status deploy/java-order-service --timeout=240s
kubectl -n "${DEMO_NAMESPACE}" rollout status deploy/python-inventory-service --timeout=120s
kubectl -n "${DEMO_NAMESPACE}" rollout status deploy/react-ops-console --timeout=120s

log "等待故障资源进入目标状态（${FAULT_SETTLE_SECONDS}s；CrashLoop/ImagePull 需要退避时间）"
sleep "${FAULT_SETTLE_SECONDS}"

log "执行验收"
HUNTAI_WEB_URL="${HUNTAI_WEB_URL}" \
DEMO_CONSOLE_URL="${DEMO_CONSOLE_URL}" \
HUNTAI_BASE_URL="${HUNTAI_BASE_URL:-${HUNTAI_WEB_URL}/api/v1}" \
HUNTAI_USERNAME="${HUNTAI_USERNAME:-admin}" \
HUNTAI_PASSWORD="${HUNTAI_PASSWORD:-your-demo-auth-password}" \
HUNTAI_AI_MODE="${HUNTAI_AI_MODE:-auto}" \
KUBECTL_CHECK="${KUBECTL_CHECK:-1}" \
python3 "${DEPLOY_DIR}/tests/acceptance.py" "$@"
