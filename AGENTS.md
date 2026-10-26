# KubeLantern — 项目规则

## 语言与技术栈

- 回复、commit subject、文档用简体中文；代码标识符用英文。
- 后端 Python + FastAPI + uv；前端 React + TypeScript + Vite + Tailwind + shadcn/ui。Python 用 uv，Node 用 npm。配置走仓库根 `.env`。

## 工作方式

- 复杂任务先出 Plan（目标、文件、步骤、验证），确认后再改文件。
- 评审用 Checklist：每条 Pass / Fail / N/A + 证据，禁止「总体感觉可以」。
- 缺失的业务事实标 `[ASSUMPTION]` / `[TBD-*]`，不编造。

## 安全红线（凭据防泄漏由 hooks 与 pre-commit 强制拦截，非提示词约束）

- 真实凭据只放 `.env`（已 gitignore）或密钥管理服务；代码、文档、命令、日志中一律用 `$ENV_VAR` 或占位符（`your-api-key`、`sk-xxxx`）。
- 禁止 `git commit --no-verify`；禁止提交 `.env`、`*.pem`、`*.key`、`credentials.json` 等敏感文件。
- 新克隆环境执行一次：`bash .zcode/scripts/setup-git-hooks.sh`
- 手工扫描文件：`python3 .zcode/scripts/secret_scan.py path <文件>`
- 规则误报需调整时，由维护者人工修改 `.zcode/scripts/secret_scan.py`。

## Agent Teams（`.zcode/agents/`）

`sre-commander` 应急指挥 ｜ `sec-auditor` 安全审计 ｜ `infra-reviewer` 变更评审 ｜ `runbook-writer` 文档沉淀
