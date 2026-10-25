# API 契约说明（04-api）

| 元信息 | |
|---|---|
| 状态 | accepted |
| 日期 | 2026-10-24 |
| 依据 | `../03-tech-design/05-fe-be-boundary.md`（§2 两阶段契约流程、§2.4 通用字段约定）、`../03-tech-design/04-backend-design.md`（§4 API 层约定、§4.5 spec 同步、§5 SSE）、`../03-tech-design/01-data-model.md`（§2 表字段与 §3 枚举字典——schema 唯一来源）、`../02-business-design/01-domain-model.md`（§3 权限矩阵与 BR-xx）、`../02-business-design/02-interaction-flows.md`（§4.1 八页面与 §4.2 三操作流） |
| 读者 | 全栈研发、评审 |
| 关联 | 端点细节唯一事实源为同目录 `openapi.yaml`，本文只做说明与链接，不复制字段级定义 |

---

## 1. 本目录内容

| 文件 | 角色 |
|---|---|
| `openapi.yaml` | OpenAPI 3.1 契约草案——**阶段一临时单一事实源**（见 §2） |
| `README.md` | 本文件：治理说明、端点总览、约定速览、验证方法 |
| `archive/`（切换后创建） | 草案退役归档目录（`05-fe-be-boundary.md` §2.2「草案的死亡」） |

## 2. 治理：两阶段契约流程

流程唯一事实源为 `05-fe-be-boundary.md` §2，此处只做导读：

- **阶段一（当前）**：仓库尚无后端代码，`openapi.yaml` 手写草案是**唯一的临时契约源**——前端 `api:gen` 生成类型并 mock 开发，后端按草案实现路由与 DTO，实现偏差回修草案（独立 PR，spec diff 为审查面；合入后前端必须重跑 `api:gen`）。
- **阶段二（切换后，永久）**：后端 `create_app()` 可稳定导出 spec 且覆盖前端已消费的全部草案资源时，事实源切换为 FastAPI 导出的 `openapi.json`（`uv run python -m huntai.app.openapi`），CI 以 `git diff --exit-code` 强制同步（`04-backend-design.md` §4.5）；切换 PR 内草案一次性退役归档，禁止复活、禁止「导出物 + 残留草案」拼接使用（`05-fe-be-boundary.md` §2.3/AP-8）。

### 2.1 文件命名例外声明

本目录 spec 文件名固定为 `openapi.yaml`（阶段二为 `openapi.json`），**不带两位序号前缀**，是对 `docs/README.md` §3「目录内两位序号 + kebab-case」约定的一次显式偏离。理由：spec 是机器消费物（api:gen、mock server、CI diff、swagger 渲染），文件名必须是工具链稳定路径，`05-fe-be-boundary.md` §2.2 已按此引用（`docs/04-api/openapi.yaml`）；编号前缀会让所有工具引用与外部链接随目录内文档数量变化。**请台账（`docs/README.md`）接受本例外**；本 README 是目录内唯一带序号语义的说明文档，但同样为工具稳定路径保留 `README.md` 专名。

### 2.2 契约变更流程（阶段一）

草案变更走独立 PR（不与页面代码混提），评审以 spec diff 为审查面；破坏性变更（删字段/改语义/改状态码/改枚举值域）必须在 PR 描述标注 `BREAKING`，枚举值域变更还须先修订领域文档状态机并同步 `01-data-model.md` §3（`05-fe-be-boundary.md` §5.1）。

## 3. 端点总览

下表从 `openapi.yaml` 提炼（一行一端点）；**字段级定义、请求/响应 schema、过滤参数以 yaml 为准**。分期列 = `x-phase`；角色列 = `x-roles`（取自领域文档 §3 权限矩阵；`(T)` = 限本团队行级过滤；`公开` = 不走用户认证；`全部角色` = 五角色均可，按 scope 过滤）。

| 分组 | 方法 | 路径 | 用途 | 分期 | 角色 |
|---|---|---|---|---|---|
| 认证 | POST | /auth/token | 登录换取访问令牌（占位 `[TBD-INFRA]`） | P0 | 公开 |
| 用户 | GET | /users | 用户列表 | P0 | admin |
| 用户 | POST | /users | 创建用户（含角色授予） | P0 | admin |
| 用户 | GET | /users/me | 当前会话用户（联调补录） | P0 | 全部角色 |
| 用户 | GET | /users/{id} | 用户详情 | P0 | admin |
| 用户 | PUT | /users/{id} | 更新用户 / 停用 | P0 | admin |
| 角色 | GET | /roles | 角色与权限矩阵列表 | P0 | admin |
| 集群 | GET | /clusters | 集群列表（含健康状态） | P0 | admin, sre |
| 集群 | POST | /clusters | 接入集群 | P0 | admin |
| 集群 | GET | /clusters/{id} | 集群详情 | P0 | admin, sre |
| 集群 | PUT | /clusters/{id} | 更新集群配置 | P0 | admin |
| 集群 | DELETE | /clusters/{id} | 移除集群（软删） | P0 | admin |
| 集群 | POST | /clusters/{id}/test-connection | 测试集群连接（探活） | P0 | admin |
| Provider | GET | /providers | 告警源列表 | P0 | admin |
| Provider | POST | /providers | 创建告警源 | P0 | admin |
| Provider | GET | /providers/{id} | 告警源详情 | P0 | admin |
| Provider | PUT | /providers/{id} | 更新告警源 | P0 | admin |
| Provider | DELETE | /providers/{id} | 删除告警源（软删） | P0 | admin |
| 接入 | POST | /alerts/webhook/{provider_key} | 告警 webhook 接入（先落盘即返 202）`[CONFLICT-C1]` | P0 | 公开（Provider 令牌） |
| 告警 | GET | /alerts | 告警列表（合并计数/过滤） | P0 | admin, sre, oncall_manager, developer(T) |
| 告警 | GET | /alerts/{id} | 告警详情（payload/富化/降噪归因） | P0 | admin, sre, oncall_manager, developer(T) |
| 告警 | POST | /alerts/{id}/ack | 认领告警（Ack）`[CONFLICT-C2]` | P0 | admin, sre, developer(T) |
| 告警 | POST | /alerts/{id}/close | 关闭告警 | P0 | admin, sre |
| 告警 | POST | /alerts/{id}/suppress-suggestion | 提交误报抑制建议（联调补录） | P0 | admin, sre, developer(T) |
| 告警 | POST | /alerts/{id}/convert-to-incident | 一键转事件（人工立项） | P2 | admin, sre, developer(T) |
| 告警 | GET | /alerts/{id}/explanations | 告警 AI 解释 | P1 | admin, sre, developer(T) |
| 富化规则 | GET | /enrichment-rules | 富化规则列表 | P0 | admin, sre |
| 富化规则 | POST | /enrichment-rules | 创建富化规则 | P0 | admin, sre |
| 富化规则 | GET | /enrichment-rules/{id} | 富化规则详情 | P0 | admin, sre |
| 富化规则 | PUT | /enrichment-rules/{id} | 更新富化规则 | P0 | admin, sre |
| 富化规则 | DELETE | /enrichment-rules/{id} | 删除富化规则（软删） | P0 | admin, sre |
| 关联规则 | GET | /correlation-rules | 关联规则列表 | P2 | admin, sre |
| 关联规则 | POST | /correlation-rules | 创建关联规则（默认 candidate） | P2 | admin, sre |
| 关联规则 | GET | /correlation-rules/{id} | 关联规则详情 | P2 | admin, sre |
| 关联规则 | PUT | /correlation-rules/{id} | 更新关联规则（auto 准入校验） | P2 | admin, sre |
| 关联规则 | DELETE | /correlation-rules/{id} | 删除关联规则（软删） | P2 | admin, sre |
| 维护窗口 | GET | /maintenance-windows | 维护窗口列表（BR-07） | P2 | admin, sre |
| 维护窗口 | POST | /maintenance-windows | 创建维护窗口 | P2 | admin, sre |
| 候选事件 | GET | /incident-candidates | 候选事件确认队列（BR-04） | P2 | admin, sre, oncall_manager, developer(T) |
| 候选事件 | POST | /incident-candidates/{id}/confirm | 确认立项 | P2 | admin, sre, developer(T) |
| 候选事件 | POST | /incident-candidates/{id}/reject | 驳回（三原因枚举回流） | P2 | admin, sre, developer(T) |
| 事件 | GET | /incidents | 事件列表 | P2 | admin, sre, oncall_manager, developer(T) |
| 事件 | POST | /incidents | 人工立项 | P2 | admin, sre, developer(T) |
| 事件 | GET | /incidents/{id} | 事件详情（时间线/关联告警/升级状态） | P2 | admin, sre, oncall_manager, developer(T) |
| 事件 | POST | /incidents/{id}/acknowledge | 确认事件 | P2 | admin, sre, developer(T) |
| 事件 | POST | /incidents/{id}/mitigate | 止血完成 | P2 | admin, sre, developer(T) |
| 事件 | POST | /incidents/{id}/resolve | 根因恢复 | P2 | admin, sre, developer(T) |
| 事件 | POST | /incidents/{id}/close | 关闭事件 | P2 | admin, sre, developer(T) |
| 事件 | POST | /incidents/{id}/cancel | 误报关闭（原因必填） | P2 | admin, sre, developer(T) |
| 事件 | POST | /incidents/{id}/notes | 追加人工处理记录（FR-32，联调补录） | P2 | admin, sre, developer(T) |
| 事件 | POST | /incidents/{id}/status-page/sync | 同步状态页（BR-06） | P2 | admin, sre |
| 事件 | POST | /incidents/{id}/status-page/undo | 撤回状态页同步（BR-06） | P2 | admin, sre |
| 事件 | POST | /incidents/{id}/ai-investigation | 发起 Agent 调查（A2，概要） | P3 | admin, sre |
| 复盘 | GET | /incidents/{id}/postmortem | 获取复盘报告 | P2 | admin, sre, developer(T) |
| 复盘 | PUT | /incidents/{id}/postmortem | 编辑复盘与行动项 | P2 | admin, sre |
| 状态页 | GET | /status-page/entries | 状态页条目列表（viewer 仅 public） | P2 | 全部角色 |
| 状态页 | POST | /status-page/entries | 创建状态页条目 | P2 | admin, sre |
| 状态页 | GET | /status-page/entries/{id} | 状态页条目详情（含更新时间线） | P2 | 全部角色 |
| 状态页 | PUT | /status-page/entries/{id} | 更新条目/追加更新 | P2 | admin, sre |
| 状态页 | DELETE | /status-page/entries/{id} | 删除状态页条目（删除/撤回语义 `[ASSUMPTION]` P2 状态页详设） | P2 | admin, sre |
| 巡检规则 | GET | /inspection-rules | 巡检规则库列表 | P0 | admin, sre, developer |
| 巡检规则 | POST | /inspection-rules | 新增巡检规则 | P0 | admin, sre |
| 巡检规则 | GET | /inspection-rules/{id} | 巡检规则详情 | P0 | admin, sre, developer |
| 巡检规则 | PUT | /inspection-rules/{id} | 更新巡检规则 | P0 | admin, sre |
| 巡检规则 | DELETE | /inspection-rules/{id} | 删除巡检规则（软删，优先停用） | P0 | admin, sre |
| 巡检策略 | GET | /inspection-policies | 巡检策略列表 | P0 | admin, sre |
| 巡检策略 | POST | /inspection-policies | 创建巡检策略（cron + 规则集） | P0 | admin, sre |
| 巡检策略 | GET | /inspection-policies/{id} | 巡检策略详情 | P0 | admin, sre |
| 巡检策略 | PUT | /inspection-policies/{id} | 更新巡检策略 | P0 | admin, sre |
| 巡检策略 | DELETE | /inspection-policies/{id} | 删除巡检策略（软删） | P0 | admin, sre |
| 巡检策略 | POST | /inspection-policies/{id}/run | 手动触发巡检（L4） | P0 | admin, sre |
| 巡检执行 | GET | /inspection-runs | 巡检执行列表 | P0 | admin, sre, developer |
| 巡检执行 | GET | /inspection-runs/{id} | 巡检执行详情 | P0 | admin, sre, developer |
| 发现 | GET | /findings | 发现列表（按集群/规则过滤） | P0 | admin, sre, developer(T) |
| 发现 | POST | /findings/{id}/ack | 认领发现 `[CONFLICT-C2]` | P0 | admin, sre, developer(T) |
| 发现 | POST | /findings/{id}/ignore | 忽略发现（原因必填） | P0 | admin, sre |
| 发现 | POST | /findings/{id}/reopen | 重新打开发现 | P0 | admin, sre |
| 发现 | POST | /findings/{id}/explain | 一键 AI 解释（A1，BR-09） | P1 | admin, sre |
| AI 任务 | GET | /ai/tasks | 任务列表（可过滤 pending_approval）`[CONFLICT-C3]` | P1 | admin, sre(T) |
| AI 任务 | GET | /ai/tasks/{id} | 任务详情（预算/审批/结果） | P1 | admin, sre(T) |
| AI 任务 | POST | /ai/tasks/{id}/approve | 批准任务（BR-02/BR-05） | P1 | admin, sre(T) |
| AI 任务 | POST | /ai/tasks/{id}/cancel | 取消/拒绝任务 | P1 | admin, sre(T) |
| AI 任务 | GET | /ai/tasks/{id}/call-logs | 调用链审计（BR-10） | P1 | admin, sre(T) |
| 排班 | GET | /oncall-schedules | 排班表列表 | P2 | admin, oncall_manager |
| 排班 | POST | /oncall-schedules | 创建排班表 | P2 | admin, oncall_manager |
| 排班 | GET | /oncall-schedules/{id} | 排班表详情 | P2 | admin, oncall_manager |
| 排班 | PUT | /oncall-schedules/{id} | 更新排班（含临时顶班） | P2 | admin, oncall_manager |
| 排班 | DELETE | /oncall-schedules/{id} | 删除排班表（软删） | P2 | admin, oncall_manager |
| 升级策略 | GET | /escalation-policies | 升级策略列表 | P2 | admin, oncall_manager |
| 升级策略 | POST | /escalation-policies | 创建升级策略 | P2 | admin, oncall_manager |
| 升级策略 | GET | /escalation-policies/{id} | 升级策略详情 | P2 | admin, oncall_manager |
| 升级策略 | PUT | /escalation-policies/{id} | 更新升级策略 | P2 | admin, oncall_manager |
| 升级策略 | DELETE | /escalation-policies/{id} | 删除升级策略（软删） | P2 | admin, oncall_manager |
| 通知 | GET | /notification-records | 通知记录审计查询（BR-08） | P2 | admin, sre, oncall_manager |
| Workflow | GET | /workflows | 编排定义列表（概要级） | P3 | admin, sre |
| Workflow | POST | /workflows | 新建编排（概要级） | P3 | admin, sre |
| Workflow | POST | /workflows/{id}/versions | 提交新版本（diff 预览后） | P3 | admin, sre |
| Workflow | POST | /workflows/from-description | NL 生成编排（A3 → 提议） | P3 | admin, sre |
| Workflow | POST | /workflows/{id}/approve | 确认 AI 生成编排（BR-05） | P3 | admin, sre |
| Workflow | POST | /workflow-runs | 触发执行 | P3 | admin, sre |
| Workflow | GET | /workflow-runs/{id} | 执行实例详情（steps_log） | P3 | admin, sre |
| 实时 | GET | /realtime/stream | SSE 事件流（Last-Event-ID 恢复）`[CONFLICT-C4]` | P0 | 全部角色（按 scope 过滤） |
| 审计 | GET | /audit-logs | 审计日志查询（只读，BR-10） | P0 | admin |

统计：**70 条路径 / 103 个操作**；分期计数 P0=48、P1=7、P2=40、P3=8（P3 为概要级）。

> 联调补录（2026-10-25）：`GET /users/me`、`POST /alerts/{id}/suppress-suggestion`、`POST /incidents/{id}/notes` 三个前端已消费端点回写草案；`GET /alerts` 增加 `q` 搜索参数。补录不改变既有枚举值域与状态机。

## 4. 约定速览（细节以 yaml 为准）

| 项 | 约定 | 出处 |
|---|---|---|
| 鉴权 | 全局 `bearerAuth` **占位**（认证方式 SSO/LDAP/本地 `[TBD-INFRA]`，基础设施负责人 / P0 部署设计）；`POST /auth/token` 与 webhook 入口 `security: []` | 04-backend-design §4.2、01-data-model §9 |
| 错误 | 统一 RFC 7807 `application/problem+json`（type/title/status/detail/instance + 扩展 `code`/`trace_id`）；状态机非法迁移 409、越权访问一律 404、webhook 限流 429（仍落盘） | 04-backend-design §4.4 |
| 分页 | 查询参数 `offset`/`limit`（limit ≤ 200，offset ≤ 10000）；响应平铺 `{items, total, offset, limit}` | 04-backend-design §4.3 |
| 时间 | 一律 UTC ISO 8601（`date-time`，`Z` 后缀）；序列化细则（毫秒位等）`[ASSUMPTION]` 随定稿固化 | 01-data-model D-4、05-fe-be-boundary §2.4 |
| 字段命名 | JSON 字段 snake_case，前端不做 camelCase 转换 | 05-fe-be-boundary §2.4 |
| 枚举 | 值域唯一来源 `01-data-model.md` §3 枚举字典（加粗状态机枚举禁止增删改）；schema enum / 前端 zod / mock 三者同源 | 01-data-model §3 |
| webhook 202 | 落盘即应答（先落库/队列再处理，平台故障不丢告警）：202 + `{alert_id, merged}`；同指纹活跃告警合并计数不产生新行 | 04-backend-design §3.2.1、非功能 §8 |
| 检索 | `GET /alerts?q=` 对 `title` / `fingerprint` 做模糊匹配（工作台搜索与顶栏全局搜索入口；联调已验证） | 03-frontend-design §4.2、联调报告 |
| SSE | `text/event-stream`；事件类型 `alert.updated` / `incident.timeline.updated` / `ai_task.updated`（联调已验证）；载荷最小化 `{resource, resource_id, team, occurred_at}`；帧格式 `id` + `event` + `data`；`Last-Event-ID` 断连恢复；心跳为 SSE comment（默认 15s） | 04-backend-design §5、联调报告 |
| 软删 | 配置类资源 DELETE 为软删（deleted_at，D-7）；audit_logs / ai_call_logs / notification_records 只追加，无修改删除路径 | 01-data-model D-6/D-7 |

## 5. 冲突登记（[CONFLICT]，待评审裁决）

以下为契约草案与既有文档**路径/命名**层面的差异，草案按契约任务指令书写，**裁决前不引入第三方案**；裁决结果回写 `openapi.yaml` 与被冲突文档之一（以评审结论为准）：

| # | 草案 | 既有文档结论 |
|---|---|---|
| C1 | `POST /alerts/webhook/{provider_key}` | `04-backend-design.md` §4.1/§3.2.1：`POST /webhooks/{provider_name}`。裁决证据：redocly lint 报告草案路径与 `/alerts/{id}/ack` 等存在路由歧义（`/alerts/webhook/ack` 双匹配），既有方案无此问题 |
| C2 | `POST /alerts/{id}/ack`、`POST /findings/{id}/ack` | `04-backend-design.md` §4.1 示例：`POST /alerts/{id}/acknowledge`（事件侧草案已用 acknowledge，存在同词不同形） |
| C3 | `/ai/tasks`（含 call-logs 子路径） | `04-backend-design.md` §4.1：`/ai-tasks`（kebab-case 单段资源） |
| C4 | `GET /realtime/stream` | `04-backend-design.md` §5.1：`GET /stream` |

> 注：SSE 事件类型命名（`alert.updated` 等）不构成冲突——`05-fe-be-boundary.md` §1 实时推送行明确事件命名「随 04-api 定稿」，本草案即行使该命名权（相对 04-backend-design §5.2 的 `alert.status_changed` 示例，最终以本契约为准，如需细分事件类型在定稿前修订草案）。

## 6. 验证方法

```bash
# 1. YAML 语法校验（必须通过）
python3 -c "import yaml; yaml.safe_load(open('docs/04-api/openapi.yaml')); print('YAML OK')"

# 2. OpenAPI 规范 lint（可选，结果仅记录不阻塞）
npx --yes @redocly/cli lint docs/04-api/openapi.yaml --skip-rule=security-defined

# 3. 渲染冒烟（可选）：swagger editor 打开无语法错误；或本地渲染
npx --yes @redocly/cli build-docs docs/04-api/openapi.yaml -o /tmp/huntai-api-preview.html

# 4. 敏感信息扫描（必须通过）
python3 .zcode/scripts/secret_scan.py path docs/04-api/openapi.yaml
python3 .zcode/scripts/secret_scan.py path docs/04-api/README.md
```

## 7. 开放问题

| 标记 | 问题 | 确认人 / 阶段 |
|---|---|---|
| `[TBD-INFRA]` | 认证方式（决定 /auth/token 形态、bearerAuth 实现与 SSE 认证手段） | 基础设施负责人 / P0 部署设计 |
| `[TBD-INFRA]` | credentials 资源端点未在本草案覆盖（M0 示意清单含「credentials 仅引用元数据」，05-fe-be-boundary §4）；secret_ref 形态定后补端点或并入集群/Provider 资源 | 基础设施负责人 + 全栈 / P0 工程化 |
| `[TBD-FE]` | SSE 通道最终确认（ADR-0006）；当前按 SSE 实现并已联调验证，若后续改 WebSocket 仅替换前端实现类。前端 TS client 已由 spec 自动生成 | 前端 / P0 技术设计 |
| `[TBD-BIZ]` | 状态页可见性默认值、升级链各级超时与渠道组合、驳回原因英译、通知渠道组合；抑制建议的规则调优闭环（当前仅 audit 留痕） | 业务负责人 / P2 设计前 |
| `[TBD-UX]` | 告警降噪归因展示方式（影响告警详情归因字段结构） | UX / P0 前端设计前 |
| `[ASSUMPTION]` | 权限矩阵未单列的读写收敛（富化/关联规则 admin+sre、用户列表 admin、通知记录可见角色、集群列表 sre 可见性、developer 读规则库）；告警级 AI 解释与 ai_explanations(finding_id) 的存储映射；webhook provider_key 语义与 Provider 令牌方案；事件时间线/升级摘要的派生结构；错误码清单 | 见 yaml 内逐条标注的验证方式，随对应阶段详设评审收敛 |
