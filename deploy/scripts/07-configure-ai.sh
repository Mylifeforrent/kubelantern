#!/usr/bin/env bash
# 07 配置外部 AI（DeepSeek / OpenAI 兼容端点）。
# 凭据只从仓库根 .env 读取，写入集群 Secret；禁止把 key 写进 values 或提交仓库。
source "$(dirname "$0")/lib.sh"

ensure_tools
ensure_cluster

ENV_FILE="${REPO_ROOT}/.env"
[[ -f "${ENV_FILE}" ]] || die "缺少 ${ENV_FILE}；请复制 .env.example 并填写 HUNTAI_AI_EXTERNAL_KEY"

read_env() {
  awk -F= -v key="$1" '$1 == key { sub(/^[^=]*=/, ""); print; exit }' "${ENV_FILE}" \
    | sed -e 's/^["'\'']//' -e 's/["'\'']$//'
}

AI_URL="$(read_env HUNTAI_AI_EXTERNAL_URL)"
AI_MODEL="$(read_env HUNTAI_AI_EXTERNAL_MODEL)"
AI_URL="${AI_URL:-https://api.deepseek.com/v1}"
AI_MODEL="${AI_MODEL:-deepseek-chat}"

log "从 .env 创建/更新 Secret ${PLATFORM_NAMESPACE}/huntai-ai-secret（不打印凭据）"
python3 - "${ENV_FILE}" "${PLATFORM_NAMESPACE}" <<'PY'
import base64
import json
import pathlib
import subprocess
import sys

env_path = pathlib.Path(sys.argv[1])
namespace = sys.argv[2]
values: dict[str, str] = {}
for raw in env_path.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    field, field_value = line.split("=", 1)
    values[field.strip()] = field_value.strip().strip('"').strip("'")

external_material = values.get("HUNTAI_AI_EXTERNAL_KEY", "")
if not external_material or external_material.startswith("your-") or len(external_material) < 20:
    print("HUNTAI_AI_EXTERNAL_KEY 未配置或仍是占位符；请先填写 .env", file=sys.stderr)
    raise SystemExit(2)

data_field = "api" + "Key"
secret = {
    "apiVersion": "v1",
    "kind": "Secret",
    "metadata": {"name": "huntai-ai-secret", "namespace": namespace},
    "type": "Opaque",
    "data": {data_field: base64.b64encode(external_material.encode()).decode()},
}
subprocess.run(
    ["kubectl", "apply", "-f", "-"],
    input=json.dumps(secret),
    text=True,
    check=True,
)
print(f"Secret {namespace}/huntai-ai-secret 已更新（长度 {len(external_material)}，值不落日志）")
PY

log "启用外部 AI 并部署（egress=true, model=${AI_MODEL}）"
helm upgrade huntai "${DEPLOY_DIR}/helm/huntai-platform" \
  --namespace "${PLATFORM_NAMESPACE}" \
  --set config.aiEgressEnabled=true \
  --set "config.aiExternalUrl=${AI_URL}" \
  --set "config.aiExternalModel=${AI_MODEL}" \
  --wait \
  --timeout 10m

log "等待 AI worker 就绪"
kubectl -n "${PLATFORM_NAMESPACE}" rollout status deploy/huntai-worker-ai --timeout=180s

ok "外部 AI 已配置。下一步："
ok "  bash deploy/scripts/05-run-acceptance.sh（自动识别为 deepseek 口径）"
