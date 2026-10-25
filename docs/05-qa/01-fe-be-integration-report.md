# 前后端联调报告（P0–P3 全量页面）

| 元信息 | |
|---|---|
| 状态 | accepted |
| 日期 | 2026-10-25 |
| 依据 | `../04-api/openapi.yaml`（阶段一契约源）、`../03-tech-design/03-frontend-design.md` §4（数据层）、`../03-tech-design/04-backend-design.md` §4–§5（API/SSE 约定）、`../03-tech-design/05-fe-be-boundary.md` §2（两阶段契约流程） |
| 读者 | 全栈研发、评审 |
| 结论 | 8 个前端页面全部切换真实后端并通过浏览器验证；修复 8 处联调断点；契约补录 3 个端点 + 1 个查询参数 |

---

## 1. 联调范围与环境

| 项 | 值 |
|---|---|
| 后端 | `uvicorn huntai.app.main:app`，本机 `127.0.0.1:8001`（8000 被其他应用占用） |
| 存储 | Docker Compose `postgres:5433` / `redis:6380`，迁移版本 `0004`，seed 已执行 |
| 前端 | Vite dev server `127.0.0.1:5173`，`VITE_USE_MOCK=0`，`/api` 代理到 8001 |
| 认证 | dev 占位认证：seed 用户 + `HUNTAI_DEV_AUTH_PASSWORD`（`[TBD-INFRA]`） |
| 验证方式 | 页面级浏览器走查（登录 → 8 页面 → 写操作）+ 代理层 curl + SSE 实时推送 + 自动化测试 |

覆盖页面：告警工作台、候选事件、事件列表/详情、巡检看板、AI 任务中心、排班与升级、管理后台、登录页。

## 2. 页面 → 端点验证矩阵

| 页面 | 消费端点 | 结果 |
|---|---|---|
| 登录 | `POST /auth/token`、`GET /users/me` | Pass：登录后回填角色并跳转 `/alerts` |
| 告警工作台 | `GET /alerts`（severity/status/team/fingerprint/q）、`GET /alerts/{id}`、`POST /alerts/{id}/ack`、`close`、`convert-to-incident`、`suppress-suggestion`、`GET /alerts/{id}/explanations` | Pass：列表/搜索/抽屉/写操作均通 |
| 候选事件 | `GET /incident-candidates`、`confirm`、`reject`、`GET /correlation-rules/{id}`、`GET /alerts` | Pass（当前无候选数据，空态正常） |
| 事件列表/详情 | `GET/POST /incidents`、`GET /incidents/{id}`、5 个状态推进、`notes`、`postmortem`、`status-page/sync`、`undo` | Pass：状态机、时间线、人工记录、状态页同步/撤回均通 |
| 巡检看板 | `GET /clusters`、`findings`、`inspection-runs`、`inspection-policies`、`inspection-rules`、`POST /findings/{id}/ack|ignore|reopen|explain` | Pass：`rule_ids` 修复后策略卡正常渲染 |
| AI 任务中心 | `GET /ai/tasks`、`call-logs`、`approve`、`cancel` | Pass（无任务时空态正常） |
| 排班与升级 | `GET/PUT /oncall-schedules`、`GET /escalation-policies` | Pass：周历与升级策略渲染 |
| 管理后台 | `GET /clusters`、`providers`、`inspection-rules`、`audit-logs`、`users`、`roles`、`POST /users`、`clusters/{id}/test-connection` | Pass：审计统计与探活降级正常 |
| 全局实时 | `GET /realtime/stream`（SSE） | Pass：连接保持、`alert.updated` 到达后列表与徽标自动刷新 |

## 3. 发现并修复的联调断点

| # | 现象 | 根因 | 修复 | 证据 |
|---|---|---|---|---|
| 1 | 巡检看板白屏/崩溃 | 前端读 `p.rule_ids.length`，后端 `InspectionPolicyResponse` 未返回 `rule_ids`（契约有） | `domains/inspections/schemas.py` 增字段；`routers/inspections.py` 逐条读取 `policy_rules` | 页面显示「规则集 2 条规则」；新增集成测试 |
| 2 | 事件详情「添加处理记录」假成功 | 前端 `useAddTimelineNote` 为空实现，后端无端点（PRD FR-32 要求） | 新增 `POST /incidents/{id}/notes`：写 `audit_logs(action=incident.note)`，详情时间线派生 `manual_note` | 浏览器提交后时间线立即出现记录 |
| 3 | 告警搜索/顶栏全局搜索无效 | 前端发送 `q`，契约与后端均无该参数（mock 单方面支持） | 契约补 `q`；后端 `list_alerts` 对 `title/fingerprint` 模糊匹配 | `/alerts?q=SmokeTest` 显示 `1 / 1` |
| 4 | SSE 连接每 15s 断开、页面一直显示「实时通道未连接」 | ① 后端路由用 `asyncio.wait_for` 包裹 `__anext__`，超时取消并关闭异步生成器；② 前端 `disconnect()` 置 `closedByUser=true` 后 `connect()` 不重置，StrictMode 重挂载后永不重连；③ Redis `XREAD` 返回值按 dict 解析 | `routers/stream.py` 改为直接 `async for`；`realtime/hub.py` 增加 `_xread_entries`；`shared/api/realtime/sse.ts` 在 `connect()` 重置标志 | 浏览器副标题变为「实时更新中」；关闭告警后行状态与徽标自动刷新 |
| 5 | 状态页撤回接口报「响应为空」 | 契约返回 200 + 条目，后端返回 204；且实现删除条目而非撤回更新 | `undo_status_page` 改为撤销最近一条 `status_page_updates` 并返回条目；路由改 200 | 集成测试断言 `is_revoked=true` |
| 6 | 事件详情 GET 复盘 500 | 未持久化模板的 `created_at/updated_at` 为 `None`，不满足响应模型；已存在复盘也不返回行动项 | 模板补时间戳；GET 补 `action_items` 查询 | 接口 200；浏览器复盘卡正常 |
| 7 | AI 待审批徽标计数错误 | 前端传 `pending_approval=true`，后端只认 `status` | 改为 `status=pending_approval` | 请求 200，参数与契约一致 |
| 8 | 管理后台「探活」500 | `secret_ref` 未配置时 `resolve_secret` 抛 500 | 连接器把凭证不可用降级为 `ProbeResult(disconnected)` | 探活返回 200 + `disconnected` + 提示 |
| 9 | 抑制建议可被任意登录用户提交、补充说明丢失 | 端点无权限门禁；后端只读 `reason`，丢弃 `note`；原因未做枚举校验 | 契约补 `SuppressSuggestionReason` 三值枚举；路由加 `alerts.acknowledge` 门禁 + 团队隔离；`note` 写入 audit detail；前端类型收窄 | 集成测试覆盖 admin/developer(T)/viewer、非法原因 422、审计含 reason/note |

附带修正：`/alerts/{id}/convert-to-incident` 补 `response_model=IncidentResponse`（此前 spec 导出无响应结构）；`StatusPageEntry` 详情补 `updates` 时间线（契约已有）；findings 严重度筛选真正下传后端；排班/巡检列表按 `cluster_id` 服务端过滤；登录页演示账号改为真实 seed 账号。

> 2026-10-25 收尾：抑制建议权限/`note`/枚举、演示集群凭证 env、SSE 事件名与 `q` 检索语义转正均已完成；剩余项见 §6。

## 4. 契约补录（阶段一草案）

| 变更 | 说明 |
|---|---|
| `GET /users/me` | 前端登录后回填会话已消费；认证方式 `[TBD-INFRA]` |
| `POST /alerts/{id}/suppress-suggestion` | 误报反馈入降噪池（audit 留痕），不直接建规则 |
| `POST /incidents/{id}/notes` | 人工处理记录（FR-32），落 audit 并派生时间线 |
| `GET /alerts` 新增 `q` | 标题 / fingerprint 模糊搜索 |
| `GET /status-page/entries/{id}` | 详情返回 `updates` 时间线（草案已有，实现补齐） |

补录后草案统计：**70 条路径 / 103 个操作**（P0=48、P1=7、P2=40、P3=8）。枚举值域与状态机未改动。

## 5. 验证命令与结果

```bash
# 后端
.venv/bin/python -m pytest
# 94 passed（本轮新增 8 项：抑制建议 3、探活降级 2、SSE 帧 3）

# 前端
npm --prefix frontend run typecheck   # 通过
npm --prefix frontend run lint        # 通过
npm --prefix frontend test            # 21 passed
npm --prefix frontend run build       # 通过（typecheck + vite build）

# 契约
python3 -c "import yaml; yaml.safe_load(open('docs/04-api/openapi.yaml')); print('YAML OK')"
npm --prefix frontend run api:gen     # schema.d.ts 与草案同步
```

浏览器走查（Chrome/IAB，真实后端）结果：8 个页面无 console error / unhandled rejection；SSE 连接稳定；写操作（人工记录、关闭告警）触发列表与徽标实时刷新。

## 6. 遗留问题

| 标记 | 问题 | 影响 / 下一步 |
|---|---|---|
| `[TBD-INFRA]` | 认证方式（SSO/LDAP/本地）未定稿 | `/auth/token`、`/users/me`、SSE 认证手段均为占位实现；下一步按「过渡加固」推进 |
| `[TBD-BIZ]` | 抑制建议的规则调优闭环 | 当前仅结构化 audit 留痕（reason/note），分诊与转规则需业务定义 |
| `[TBD-FE]` | 阶段二契约切换（FastAPI 导出 spec 替代草案） | 已定方案 A 全量归一化：导出时补 servers/去前缀/命名枚举/结构化 DTO/schema 重命名，前端零改动；待独立 PR |
| `[TBD-BIZ]` | 状态页受众与公开范围（OP-B04） | 后端 CRUD/同步/撤回已就绪，前端无页面；下一步做内部只读页 |
| `[TBD-UX]` | 降噪归因展示方式 | 前端沿用现有占位结构 |

## 7. 本地复现步骤

```bash
# 1. 存储
docker compose up -d postgres redis

# 2. 迁移 + seed（首次）
uv run alembic upgrade head
PYTHONPATH=src uv run python -m huntai.seed --with-alerts

# 3. 后端（8000 被占用时用 8001）
PYTHONPATH=src uv run uvicorn huntai.app.main:app --host 127.0.0.1 --port 8001

# 4. 前端：frontend/.env 设 VITE_USE_MOCK=0、VITE_PROXY_TARGET=http://127.0.0.1:8001
npm --prefix frontend run dev
```

> `frontend/.env` 已 gitignore；`frontend/.env.example` 保持 8000 默认值，按本机端口覆盖即可。
