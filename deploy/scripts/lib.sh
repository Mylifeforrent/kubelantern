#!/usr/bin/env bash
# 公共函数：所有脚本 source 本文件。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${DEPLOY_DIR}/.." && pwd)"

KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-huntai-sre}"
PLATFORM_NAMESPACE="${PLATFORM_NAMESPACE:-huntai}"
DEMO_NAMESPACE="${DEMO_NAMESPACE:-demo}"
RELEASE_NAME="${RELEASE_NAME:-huntai}"
DEMO_RELEASE_NAME="${DEMO_RELEASE_NAME:-huntai-demo}"
HUNTAI_IMAGE="${HUNTAI_IMAGE:-huntai-sre:dev}"
WEB_IMAGE="${WEB_IMAGE:-huntai-web:dev}"
JAVA_IMAGE="${JAVA_IMAGE:-huntai-demo/java-order-service:dev}"
PYTHON_IMAGE="${PYTHON_IMAGE:-huntai-demo/python-inventory-service:dev}"
CONSOLE_IMAGE="${CONSOLE_IMAGE:-huntai-demo/react-ops-console:dev}"

# Docker Hub 直连不稳定时使用的镜像加速器；设为空字符串则只走直连。
PULL_MIRROR="${PULL_MIRROR:-docker.1ms.run}"
KIND_NODE_IMAGE="${KIND_NODE_IMAGE:-kindest/node:v1.37.0}"

if [[ -t 1 ]]; then
  C_RESET='\033[0m'; C_BLUE='\033[1;34m'; C_GREEN='\033[1;32m'; C_YELLOW='\033[1;33m'; C_RED='\033[1;31m'
else
  C_RESET=''; C_BLUE=''; C_GREEN=''; C_YELLOW=''; C_RED=''
fi

log()  { printf "${C_BLUE}[huntai]${C_RESET} %s\n" "$*"; }
ok()   { printf "${C_GREEN}[ ok ]${C_RESET} %s\n" "$*"; }
warn() { printf "${C_YELLOW}[warn]${C_RESET} %s\n" "$*"; }
die()  { printf "${C_RED}[fail]${C_RESET} %s\n" "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令：$1（先执行 deploy/scripts/00-prereqs.sh）"
}

ensure_docker() {
  need_cmd docker
  docker info >/dev/null 2>&1 || die "Docker daemon 不可用，请先启动 Docker Desktop"
}

ensure_cluster() {
  need_cmd kind
  kind get clusters 2>/dev/null | grep -qx "${KIND_CLUSTER_NAME}" \
    || die "kind 集群 ${KIND_CLUSTER_NAME} 不存在（先执行 01-create-cluster.sh）"
  kubectl config use-context "kind-${KIND_CLUSTER_NAME}" >/dev/null
}

ensure_tools() {
  need_cmd kubectl
  need_cmd helm
  ensure_docker
}

# 拉取镜像：Docker Hub 优先走加速器；已是本地镜像则跳过。
pull_image() {
  local ref="$1" mirrored=""
  if docker image inspect "${ref}" >/dev/null 2>&1; then
    return 0
  fi
  if [[ "${ref}" != ghcr.io/* ]] && [[ -n "${PULL_MIRROR}" ]]; then
    if [[ "${ref}" == */* ]]; then
      mirrored="${PULL_MIRROR}/${ref}"
    else
      mirrored="${PULL_MIRROR}/library/${ref}"
    fi
    if docker pull "${mirrored}"; then
      docker tag "${mirrored}" "${ref}"
      return 0
    fi
    warn "加速器拉取失败，回退直连：${ref}"
  fi
  docker pull "${ref}"
}

prepare_kind_node_image() {
  log "准备 kind 节点镜像 ${KIND_NODE_IMAGE}"
  pull_image "${KIND_NODE_IMAGE}"
}

prepare_base_images() {
  local images=(
    python:3.12-slim
    node:22-alpine
    nginx:1.27-alpine
    maven:3.9-eclipse-temurin-21
    eclipse-temurin:21-jre
    postgres:16-alpine
    redis:7-alpine
    ghcr.io/astral-sh/uv:latest
  )
  local image
  for image in "${images[@]}"; do
    log "准备基础镜像 ${image}"
    pull_image "${image}"
  done
}

wait_for_http() {
  local url="$1" timeout="${2:-120}" elapsed=0
  until curl -fsS "${url}" >/dev/null 2>&1; do
    elapsed=$((elapsed + 2))
    if [[ ${elapsed} -ge ${timeout} ]]; then
      die "等待 ${url} 超时（${timeout}s）"
    fi
    sleep 2
  done
}
