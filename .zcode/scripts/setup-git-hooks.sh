#!/usr/bin/env bash
# 在本仓库启用 git pre-commit 凭据门禁（新克隆环境执行一次即可）。
set -euo pipefail
cd "$(dirname "$0")/../.."

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git init -q
  echo "[setup] 已初始化 git 仓库"
fi

git config core.hooksPath .githooks
echo "[setup] 已启用 .githooks/pre-commit 凭据检查（core.hooksPath=.githooks）"
