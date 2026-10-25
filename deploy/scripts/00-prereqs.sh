#!/usr/bin/env bash
# 00 前置检查：Docker、kind、kubectl、helm、端口。缺失时尝试用 Homebrew 安装 kind/helm。
source "$(dirname "$0")/lib.sh"

log "检查 Docker"
ensure_docker
ok "Docker $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo unknown)"

install_if_missing() {
  local cmd="$1" pkg="${2:-$1}"
  if command -v "${cmd}" >/dev/null 2>&1; then
    ok "${cmd} 已安装：$(${cmd} version --short 2>/dev/null || ${cmd} version 2>/dev/null | head -1)"
    return
  fi
  if command -v brew >/dev/null 2>&1; then
    log "安装 ${pkg}"
    brew install "${pkg}"
  else
    die "缺少 ${cmd}，且未找到 Homebrew；请手动安装"
  fi
}

install_if_missing kind
install_if_missing helm
need_cmd kubectl
ok "kubectl $(kubectl version --client -o json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["clientVersion"]["gitVersion"])' 2>/dev/null || kubectl version --client 2>/dev/null | head -1)"
need_cmd python3
ok "python3 $(python3 --version)"
need_cmd curl

for port in 8080 18081; do
  if lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    warn "宿主机端口 ${port} 已被占用；kind 创建会失败，请释放端口或修改 deploy/kind/kind-config.yaml"
  else
    ok "宿主机端口 ${port} 可用"
  fi
done

log "前置检查完成。下一步：bash deploy/scripts/01-create-cluster.sh"
