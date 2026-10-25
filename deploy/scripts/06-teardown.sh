#!/usr/bin/env bash
# 06 清理：删除 Helm release 与 kind 集群（可选保留集群）。
source "$(dirname "$0")/lib.sh"

KEEP_CLUSTER="${KEEP_CLUSTER:-0}"
ensure_tools

if helm status "${DEMO_RELEASE_NAME}" -n "${DEMO_NAMESPACE}" >/dev/null 2>&1; then
  log "卸载演示业务"
  helm uninstall "${DEMO_RELEASE_NAME}" -n "${DEMO_NAMESPACE}"
fi
if helm status "${RELEASE_NAME}" -n "${PLATFORM_NAMESPACE}" >/dev/null 2>&1; then
  log "卸载 HuntAI 平台"
  helm uninstall "${RELEASE_NAME}" -n "${PLATFORM_NAMESPACE}"
fi

if [[ "${KEEP_CLUSTER}" == "1" ]]; then
  warn "KEEP_CLUSTER=1，保留 kind 集群 ${KIND_CLUSTER_NAME}"
  exit 0
fi

if kind get clusters 2>/dev/null | grep -qx "${KIND_CLUSTER_NAME}"; then
  log "删除 kind 集群 ${KIND_CLUSTER_NAME}"
  kind delete cluster --name "${KIND_CLUSTER_NAME}"
fi
ok "清理完成"
