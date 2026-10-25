#!/usr/bin/env bash
# 02 构建镜像并加载进 kind（无需镜像仓库）。
source "$(dirname "$0")/lib.sh"

ensure_tools
ensure_cluster
prepare_base_images

build_and_load() {
  local image="$1" context="$2" dockerfile="${3:-}"
  log "构建 ${image}（context=${context}）"
  if [[ -n "${dockerfile}" ]]; then
    docker build -t "${image}" -f "${dockerfile}" "${context}"
  else
    docker build -t "${image}" "${context}"
  fi
  log "加载 ${image} 到 kind 集群"
  kind load docker-image "${image}" --name "${KIND_CLUSTER_NAME}"
  ok "${image} 已就绪"
}

# 平台后端与 Web
build_and_load "${HUNTAI_IMAGE}" "${REPO_ROOT}"
build_and_load "${WEB_IMAGE}" "${REPO_ROOT}/frontend"

# 三个演示工程
# Java 先在宿主机打 jar，避免容器内 Maven Central 超时；无 mvn 时回退多阶段 Dockerfile.build。
if command -v mvn >/dev/null 2>&1; then
  log "Maven 构建 java-order-service jar"
  (cd "${DEPLOY_DIR}/demo-apps/java-order-service" && mvn -q -B package -DskipTests)
  build_and_load "${JAVA_IMAGE}" "${DEPLOY_DIR}/demo-apps/java-order-service"
else
  warn "未找到 mvn，回退到 Dockerfile.build 多阶段构建"
  build_and_load "${JAVA_IMAGE}" "${DEPLOY_DIR}/demo-apps/java-order-service" \
    "${DEPLOY_DIR}/demo-apps/java-order-service/Dockerfile.build"
fi
build_and_load "${PYTHON_IMAGE}" "${DEPLOY_DIR}/demo-apps/python-inventory-service"
build_and_load "${CONSOLE_IMAGE}" "${DEPLOY_DIR}/demo-apps/react-ops-console"

# 集群内基础镜像（提前加载，避免节点拉取受网络影响）
for image in postgres:16-alpine redis:7-alpine; do
  kind load docker-image "${image}" --name "${KIND_CLUSTER_NAME}"
done

ok "全部镜像已加载。下一步：bash deploy/scripts/03-deploy-platform.sh"
