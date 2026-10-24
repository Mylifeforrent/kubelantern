# 前后端开发边界

| 元信息 | |
|---|---|
| 状态 | accepted |
| 日期 | 2026-10-24 |
| 依据 | `docs/README.md`（治理规则 §4：单一事实源、状态生命周期）、`02-business-design/01-domain-model.md`（§3 角色权限矩阵、§5.2 标识与命名、BR-xx 只引编号）、`02-business-design/02-interaction-flows.md`（§4.1 八个页面、§4.2 三条关键操作流、§5 分期映射）、`03-tech-design/01-data-model.md`（§3 枚举字典、D-4）、`03-tech-design/02-architecture.md`（HLD：§1.3 两个人口、§2 #2 API 网关、§3.3 实时通道、§6.1 部署单元）、`03-tech-design/03-frontend-design.md`（§3.2 权限展示控制、§4.1 类型生成流程、§4.4 状态分层、§7.2 E2E 范围、§8.3 环境变量）、`03-tech-design/04-backend-design.md`（§4.3 分页约定、§4.4 RFC 7807、§4.5 OpenAPI 同步流程、§5 SSE、§6.3 配置） |
| 读者 | 全栈研发 · 评审 |

> 本文是单人全栈开发模式下的**边界纪律文档**：每层职责、契约流程、mock 与联调秩序、里程碑验收。既有的四份技术文档（01-04）已分别定稿前后端各自的技术方案，本文不重复其内容、不自创新原则，只在「两份设计之间」划界并定义协作流程；凡上游未规定者标 `[ASSUMPTION]`（附验证方式）或 `[TBD-*]`（附确认人/阶段）。业务规则只引用 BR-xx 编号（唯一事实源 `02-business-design/01-domain-model.md` §7）。

---

## 0. 总裁决原则

**一切争议裁决：后端权威，前端为 UX 体验层。**

出处（不自创）：

- HLD `02-architecture.md` §1.3「两个人口，两套准入」与 §2 #2：认证、鉴权（领域 §3 权限矩阵）、限流、审计埋点收口在 API 网关；
- 前端设计 `03-frontend-design.md` §3.2：「前端权限只做展示控制，后端权威……绕过前端直调 API 必须被后端拒绝，前端不承担安全职责」；
- 后端设计 `04-backend-design.md` §4.4（错误结构）、§4.3（分页排序过滤）、§4.5（spec 事实源）均为后端侧定义、前端消费。

推论（贯穿 §1-§6）：任何「前端算出来的业务结论」都只是展示优化，后端必然存在同语义的权威计算与校验；任何「后端吐给前端的 UI 语义」（文案、布局意图）都是越界。

## 1. 职责边界总表

按十个维度声明。**争议裁决列**均为 §0 总原则在该维度的具体化，不再逐条展开。

| 维度 | 前端职责（UX 体验层） | 后端职责（权威） | 争议裁决（均为后端权威）与出处 |
|---|---|---|---|
| 数据校验 | RHF + zod 提前校验（必填/长度/格式），减少无效往返（`03-frontend-design.md` §1.2.4）；zod schema 语义与契约一致 `[ASSUMPTION]`（验证方式：P0 工程化时评估由 spec 生成或人工对照清单） | DTO 值域校验为唯一权威（长度/枚举/条件必填，`04-backend-design.md` §1.4）；非法请求 400/422（§4.4） | 前端校验是体验优化；结果永远以后端响应为准。前端不得因「前端已校验」而省略错误分支处理 |
| 业务规则 | 只做规则**结果**的展示与入口预防性禁用（如 info 级 finding 禁用 AI 按钮，BR-09，`03-frontend-design.md` §5.4）；提示语「已留痕」（§4.2） | BR-01 ~ BR-13 全部规则的执行、计算与兜底校验（规则正文唯一事实源 `01-domain-model.md` §7；各 BR 落地点见 `04-backend-design.md` §3） | 规则计算一律后端。前端「禁用/隐藏」不构成安全边界，后端必须能拒绝绕过前端的请求 |
| 权限 | 展示控制：路由守卫 `RequireAuth/RequireRole`、`can()` 权限位控制按钮/入口渲染，映射表以领域 §3 为唯一事实源（`03-frontend-design.md` §3.2） | 认证鉴权、T（限本团队）行级过滤、写操作审批（BR-02）、越权访问一律 404（`04-backend-design.md` §4.2/§4.4） | 权限判定归属后端（任务指明领域 §3）；前端隐藏/禁用仅为 UX。前端不复制权限矩阵逻辑，只消费 `roles.permissions` 结构 |
| 状态机 | 按当前状态渲染可用动作与步进条（如事件 open→acknowledged→…→closed，`03-frontend-design.md` §5.2）；不自行推断「哪些迁移应该合法」 | 合法迁移表与必填上下文校验在 service 层集中实现，非法迁移 409（`04-backend-design.md` §1.4、§3.6、§4.4）；状态值域与领域 §6 状态机严格一致（`01-data-model.md` §3） | 迁移合法性归属后端。前端按钮只按「后端声明的当前状态 + 权限位」渲染，不预判 |
| 错误处理 | `shared/api` 统一错误规约：解析 problem envelope、401 跳登录、4xx/5xx toast 分级（`03-frontend-design.md` §4.1）；面向用户的提示文案在前端按 `code` 映射 `[ASSUMPTION]`（验证方式：04-api 契约定稿时随错误码清单一并固化） | 错误结构唯一权威：RFC 7807 `application/problem+json`，含 `code`/`trace_id` 扩展成员与状态码映射（`04-backend-design.md` §4.4） | 错误结构后端定；文案与展示形式前端定（后端 `detail` 是面向开发者的诊断信息，不是 UI 文案，见 §6 反模式 AP-2） |
| 实时推送 | `RealtimeClient` 封装（通道无关）、缓存合并纯函数与幂等去重、断连降级轮询（`03-frontend-design.md` §1.2.7、§4.3） | 事件产生与发布收敛在 `realtime/hub.py`；载荷最小化（只通知变更，详情走 API）；Last-Event-ID 断连恢复；推送层团队 scope 过滤（`04-backend-design.md` §5） | 推送语义（topics、事件命名、载荷、恢复协议）归后端契约；合并与渲染策略归前端实现。事件名 `[ASSUMPTION]`（沿 `03-frontend-design.md` §4.3，随 04-api 定稿） |
| 时间与时区 | 本地化展示（领域 §5.2）；日期处理统一经 `shared/lib` 时间工具（date-fns，`03-frontend-design.md` §1.2.10）；禁止手工解析/拼接时间字符串 | 一律 `timestamptz`、UTC 存储（`01-data-model.md` D-4）；序列化 UTC ISO 8601（SSE `occurred_at` 示例带 `Z` 后缀，`04-backend-design.md` §5.2）；序列化细则（`Z` vs `+00:00`、毫秒位）`[ASSUMPTION]`（验证方式：04-api 契约定稿时统一并写入草案 examples） | 后端权威 UTC。前端把 UTC 字符串当本地时间解析视为缺陷（§6 AP-9） |
| 分页过滤排序 | 筛选/排序/翻页写入 URL search params（可分享可恢复，`03-frontend-design.md` §4.2/§4.4）；`keepPreviousData` 消闪 | offset/limit（limit 上限 200）、响应 `{items, total, offset, limit}`、`sort` 白名单、过滤字段白名单、非法字段 400（`04-backend-design.md` §4.3） | 分页语义归后端。前端不得对分页数据做客户端全量重排（破坏 total/offset 语义）；排序必须经 `sort` 参数 |
| 审计 | 零审计职责；仅在写操作提示中说明已留痕（`03-frontend-design.md` §4.2） | 全量写操作与 AI 调用审计：service 层与业务变更同事务写入、只追加不可删改（BR-10、`04-backend-design.md` §6.2、`01-data-model.md` D-6） | 审计完全归属后端。前端不产生、不补充、不修正审计数据 |
| 配置 | 仅 `VITE_` 前缀环境变量（当前仅 `VITE_API_BASE_URL`，`03-frontend-design.md` §8.3）；**禁止任何密钥进入 `VITE_*` 或前端代码**（构建产物可读） | `HUNTAI_` 前缀读仓库根 `.env`，pydantic-settings 启动 fail-fast（`04-backend-design.md` §6.3）；密钥类生产一律 `secret_ref` | 前端零密钥（`03-frontend-design.md` §8.3 红线）；一切模型调用经 API → AI 网关（HLD §1.3 唯一出域出口），前端直连模型端点即违规（§6 AP-3） |

## 2. 契约流程（契约先行工作流）

> 本章是全文关键章节。治理基线：`docs/README.md` §4 第 2 条「API 以 `04-api/` 的 OpenAPI spec 为单一事实源」。终态流程已由 `04-backend-design.md` §4.5 定稿（**spec 由代码生成，导出物入 `04-api/`，CI 强制同步，不采用手写 spec 先行**）；本章只补齐「当前尚无后端代码」这一时间点的过渡规则，终态不变。

### 2.1 两阶段模型

```text
阶段一（当前：仓库无后端代码）
  事实源 = docs/04-api/openapi.yaml 手写契约草案（唯一的临时契约源）
  前端：api:gen 从草案生成 schema.d.ts → mock 开发 → 页面开发
  后端：按草案实现路由与 DTO，实现偏差回头修订草案（走 PR）

阶段二（切换时点起，永久）
  事实源 = FastAPI 导出的 docs/04-api/openapi.json（04-backend-design §4.5）
  一切契约变更 = 改代码 → 导出 → CI git diff --exit-code 校验
  新资源 = 后端先落路由与 DTO → 导出 → 前端 api:gen → 前端开发
```

- **阶段一的存在理由**：后端工程化（uv 项目、Alembic 建库、CI）完成前，前端需要契约启动 mock 与页面开发（§3 阶段划分）；草案是单人项目内的临时脚手架，不是 design-first 常态。
- **与 `04-backend-design.md` §4.5 的衔接说明**：§4.5 的结论「不采用手写 spec 先行」其理由（FastAPI 类型注解即契约、同仓同节奏无外部协作时序诉求）针对**常态**；本文的阶段一不改变 §4.5 终态——切换后手改 `docs/04-api/openapi.json` 会被 CI diff 直接拒绝，事实源唯一性始终成立。此衔接是否被评审接受，登记 §7 开放问题 Q1。

### 2.2 阶段一：手写契约草案的治理

| 项 | 规则 |
|---|---|
| 位置与格式 | `docs/04-api/openapi.yaml`（yaml 便于 PR diff `[ASSUMPTION]`，验证方式：首个草案 PR 评审确认；目录按 `docs/README.md` §1 随首文件创建并更新台账） |
| 草案必须对齐的三件事 | ① 错误结构：RFC 7807 problem（`04-backend-design.md` §4.4）；② 分页 envelope 与参数（§4.3）；③ 枚举值域：逐条引用 `01-data-model.md` §3 枚举字典，禁止自创值 |
| 变更流程 | 草案变更走独立 PR（不与页面代码混提），评审以 spec diff 为审查面（同 §4.5 第 3 条精神）；合入后前端必须重跑 `api:gen` |
| 草案的死亡 | 切换时点（§2.3）一次性退役，移至 `docs/04-api/archive/` 留档；退役后禁止复活 |

### 2.3 切换时点与迁移规则（防双源漂移的核心）

**切换时点**：后端 `create_app()`（`04-backend-design.md` §1.3）可稳定导出 spec，且导出物**覆盖前端已消费的全部草案资源**——预计在 M0 中后段（§4 里程碑表），具体以事件「M0 全资源在后端可运行」为准 `[ASSUMPTION]`（验证方式：P0 联调评审确认首个切换 PR 清单）。

**迁移规则（必须一次性执行，禁止草案与导出物长期并存）**：

1. 后端导出 `docs/04-api/openapi.json`（`uv run python -m huntai.app.openapi`，§4.5 第 1 条）合入，同一 PR 内：草案退役归档、前端 `openapi.json` 快照与 `schema.d.ts` 重新生成、全部类型 diff 适配完毕；
2. 切换 PR 合入后，CI 启用 §4.5 第 2 条校验（导出物 diff 不同步即失败）；该 PR 是草案与导出物并存的**唯一且最后一个** PR；
3. 切换后新增资源（P1/P2）一律走「后端先行 → 导出 → 前端跟进」，**不再回头写草案**——P1/P2 资源不存在「前端等不到契约」的问题（单人同仓同节奏，§4.5 理由 3）；
4. 切换前若前端消费了后端短期内不实现的资源：该资源要么从草案与页面中同时摘除，要么后端在切换 PR 前补齐实现；不允许「导出物 + 残留草案」拼接成事实源。

### 2.4 通用字段约定（两阶段一致）

| 项 | 约定 | 出处 |
|---|---|---|
| JSON 字段命名 | 一律 snake_case，与库表命名一致；前端不得在 API 层做 camelCase 转换（openapi-typescript 生成类型保持 spec 原名，避免双命名体系）`[ASSUMPTION]`（验证方式：P0 前端工程化评审固化） | `01-data-model.md` §2.1；`03-frontend-design.md` §1.2.9 |
| URL 资源命名 | 复数 kebab-case，前缀 `/api/v1` | `04-backend-design.md` §4.1 |
| 时间格式 | UTC ISO 8601（timestamptz 语义）；序列化细则 `[ASSUMPTION]`（§1 时间维度行） | `01-data-model.md` D-4；`04-backend-design.md` §5.2 |
| 枚举值 | 唯一事实源为 `01-data-model.md` §3 枚举字典（加粗项值域禁止增删改）；spec 的 schema enum、前端 zod、mock 数据三者必须同源（经 `api:gen` 生成或对照清单核对） | `01-data-model.md` §3 |
| 响应模型 | ORM 模型禁止直接充当 response model，敏感字段（`secret_ref`、掩码原值、`raw_payload` 凭据类内容）禁止出现在任何响应 DTO | `04-backend-design.md` §1.4 |

## 3. Mock 与联调

### 3.1 阶段划分

| # | 阶段 | 内容 | 退出条件 |
|---|---|---|---|
| S1 | 契约评审 | 草案（阶段一）或 spec 导出物（阶段二）PR 评审通过：错误结构、分页 envelope、枚举值域逐条对照（§2.2/§2.4） | 契约 PR 合入 |
| S2 | 前端 mock 开发 | 基于 OpenAPI 启动 mock server（候选 Stoplight Prism，由 spec 直接起 mock `[ASSUMPTION]`，验证方式：P0 工程化评审确认 Prism 对草案版本与 examples 的支持，不通过则换 openapi 生态等价物并登记 ADR）；`VITE_API_BASE_URL` 指向 mock 端口；`api:gen` 生成类型后开发页面 | 页面在 mock 数据上走通交互流（§4.2 三条流对应路径） |
| S3 | 后端实现 | 按契约实现路由/DTO/service（阶段一以草案为准，偏差回修草案 PR）；后端测试按 `04-backend-design.md` §7 执行 | 后端集成测试通过 + spec 导出同步（阶段二起 CI 保证） |
| S4 | 联调切换 | 前端仅改环境变量：`VITE_API_BASE_URL` 从 mock 端口切回默认同源 `/api/v1`（dev 经 Vite proxy → api 进程，`03-frontend-design.md` §4.1/§8.3），**代码零改动**；`.env.local` 不入库 | 里程碑验收（§4）双条件通过 |
| S5 | E2E | Playwright 三条关键操作流（`03-frontend-design.md` §7.2），Compose 起 api + seed fixture + `vite preview` | E2E 全绿，阻塞合入 |

### 3.2 责任划分

- **mock 数据责任归前端**：场景数据（中文语境、边界值、空态、异常态——如 pending_approval 高亮、NoAI 降级态）由前端在 `web/` 内维护 fixture/examples `[ASSUMPTION]`（验证方式：P0 工程化时定 fixture 目录与 Prism 挂载方式）。
- **mock 语义归契约**：枚举值域、字段名、时间格式、错误结构、分页 envelope 一律来自 spec——mock server 由 spec 驱动起服务，手写漂移视为违规（§6 AP-5）。
- **E2E seed 责任归后端**：seed 数据须满足业务规则正确性（如告警状态须经管道推进、候选事件须由关联规则产生），故 seed 脚本随后端仓库维护、前端 E2E 只消费 `[ASSUMPTION]`（验证方式：P0 工程化评审定 seed 形态：直写 DB 或调 API/webhook 造数）。

## 4. 联调里程碑（P0-P2）

每个里程碑 = 页面（交互文档 §4.1）+ 对应 API 资源（示意名，唯一事实源随 §2 契约流程）+ 关键操作流（交互文档 §4.2）验收。**统一验收口径：① Playwright E2E 对应流通过（`03-frontend-design.md` §7.2）；② 契约同步检查通过（阶段一：草案 PR 已评审合入且前端类型由当期草案生成；阶段二：CI spec diff 通过）。二者缺一不可。**

| 里程碑 | 页面（交互 §4.1 / 前端 §3.1） | API 资源（示意） | 关键操作流验收（交互 §4.2） | 附加验收 |
|---|---|---|---|---|
| **M0（P0 奠基）** | 登录、告警工作台、巡检看板、管理后台 | `session`/认证（形态随 `[TBD-INFRA]` 认证方式）、`users`、`roles`、`clusters`、`credentials`（仅引用元数据）、`providers`、`enrichment-rules`、`alerts`（列表/详情/认领/关闭/抑制建议）、`inspection-rules`、`inspection-policies`、`inspection-runs`、`findings`（认领/忽略）、`stream`（SSE，`[TBD-FE]` 确认后） | **告警处置流（P0 形态）**：详情 → 认领 Ack → 转事件入口（P0 占位，事件 P2 落地）/ 直接关闭 → 误报抑制建议提交；「查看 AI 解释」步骤以 **NoAI/未上线降级态断言**（P0 无 AI 能力，确定性在前，HLD §1.3；交互 §5 L1 P0 行） | 完成契约阶段一切换（§2.3）；`can()` 权限位对领域 §3 矩阵全组合单测通过（前端 §7.1） |
| **M1（P1 AI 接入）** | AI 任务中心（新增）、巡检看板（A1 集成：行内 AI 解释）、告警工作台（AI 解释 tab 生效） | `ai-tasks`（含审批）、`ai-call-logs`、`ai-explanations`、AI 预算统计资源 | **AI 审批流**：pending_approval → 审批 Modal（工具与参数、预算已消耗、30min 超时说明）→ 批准继续/拒绝终止；**告警处置流补全**：「查看 AI 解释」真实分支 + NoAI 降级分支双断言（前端 §7.2） | `ai-task.status_changed` 推送 + 动态轮询兜底双通道验证（前端 §4.3）；后端 BR-03 预算耗尽链路测试（后端 §7.3）通过 |
| **M2（P2 事件与值班）** | 候选事件确认队列、事件列表/详情、排班管理；告警工作台（降噪归因/关联） | `incident-candidates`、`correlation-rules`、`maintenance-windows`、`incidents`（含 `timeline`）、`notification-records`、`status-page-entries`、`postmortems`、`oncall-schedules`、`escalation-policies` | **候选事件确认流**：候选卡片（规则+成员+相似度）→ 确认立项（断言事件创建与成员关联）/ 驳回三原因（断言原因提交回流）；**告警处置流 P2 完整形态**：转事件真实落地（断言跳转与立项） | 三条流 E2E 全绿（前端 §7.2 全量）；`candidate.created` 推送 + 徽标/toast 验证；后端 BR-04 候选流链路测试（后端 §7.3）通过 |

- P3（Workflow 编辑器、A2/A3）不入本表，随 P3 详设另立（HLD §6.3、后端 §3.9）。
- 里程碑内部的推荐节奏：S2（前端 mock）与 S3（后端实现）可并行启动，但 S4 联调开始前 S1/S3 必须完成；M1/M2 的新资源在阶段二下「后端先落路由导出 spec，前端再开发」（§2.3 迁移规则第 3 条）。

## 5. 变更流程

单人全栈下，「谁提 PR、谁审」退化为**流程纪律 + CI 机械审查**：评审人即维护者本人，按 checklist 自审（`AGENTS.md` 工作方式），杜绝「顺手改契约不提 PR」。

### 5.1 契约变更（阶段二常态；阶段一同理作用于草案）

| 步 | 规则 |
|---|---|
| 提 PR | 任何契约修改必须独立 PR：阶段二 = 路由/DTO 代码 PR 内含重新导出的 `openapi.json` 与前端 `schema.d.ts` 重生成（禁止与无关重构混提）；阶段一 = 草案独立 PR |
| 审查面 | PR 以 spec diff 为契约变更审查面（§4.5 第 3 条）：逐字段核对命名/类型/枚举（对齐 `01-data-model.md` §3）/错误结构/分页 envelope |
| breaking change | 删字段、改语义、改状态码、改枚举值域 = 破坏性变更：必须在 PR 描述标注 `BREAKING`；前端适配必须**同一 PR** 完成（CI spec diff + 前端 typecheck 保证不存在「spec 已改前端未跟上」的中间态合入 main）；枚举值域变更还须先修订领域文档状态机并同步 `01-data-model.md` §3（其加粗枚举禁止直接增删改） |
| spec 版本化 | URL 路径版本 `/api/v1`（§4.1）为对外版本；spec `info.version` 随每次契约变更递增 `[ASSUMPTION]`（验证方式：P0 工程化时定递增规则——建议 semver：加字段 patch、加资源 minor、breaking major）。`/api/v2` 仅在「不兼容变更且无平滑过渡手段」时立项，双版本并存期与退役规则届时以 ADR 固化 `[ASSUMPTION]`（触发时评审） |

### 5.2 字段废弃流程

1. 废弃起：spec 中该字段标 `deprecated: true`（OpenAPI 原生标记），前端代码清引用；
2. 标注期：至少存活**一个完整里程碑**（§4 表），且 E2E 与前端代码中零引用 `[ASSUMPTION]`（验证方式：M0/M1 实跑后校准时长，若跨里程碑周期过长再定固定天数）；
3. 物理删除：满足标注期后随普通契约 PR 删除（属 breaking change，按 §5.1 标注）；
4. 审计与流水字段（`01-data-model.md` D-6 只追加表）的「废弃」仅指 API 响应不再暴露，落库数据不动。

## 6. 边界反模式清单

每条：禁止事项 → 违规后果 → 检查手段。**检查手段中的 lint/CI 均为既有文档已规划的设施**（前端 §2.2/§8.1 boundaries lint、前端 §4.1 spec 新鲜度 CI、后端 §4.5 spec diff CI、后端 §2.2 import 边界检查），本章只做映射，不新增工具承诺。

| # | 禁止事项 | 违规后果 | 检查手段 |
|---|---|---|---|
| AP-1 | 前端拼装业务规则（自行计算降噪率/预算耗尽判定/严重度分流/相似度等 BR-xx 语义） | 规则双实现必然漂移；规则变更只改后端时前端展示错误结论 | Code review（PR checklist 固定项：页面内不得出现 BR 语义计算）；E2E 断言消费后端返回值而非前端计算值 |
| AP-2 | 后端返回 UI 文案（中文按钮/提示/toast 文案进响应体；把 problem `detail` 当用户文案直接 toast） | 文案迭代被迫走后端发布；`detail` 面向开发者，直出会暴露内部信息（后端 §4.4：500 的 detail 不泄内部信息） | 契约评审：response schema 不得出现文案类字段；前端 `shared/api` 错误规约按 `code` 映射文案（前端 §4.1），review 固定项 |
| AP-3 | 前端直连 DB/Redis/K8s API/模型端点（绕过 api 部署单元） | 绕过权限（领域 §3）、审计（BR-10）、脱敏（BR-01）、预算（BR-03）；密钥进前端即泄露（构建产物可读） | 架构上前端仅 api 可达（HLD §1.3 单部署单元 + 部署网络 `[TBD-INFRA]`）；前端 `VITE_*` 白名单（前端 §8.3）；secret_scan + pre-commit 拦密钥 |
| AP-4 | 绕过 OpenAPI 手写接口层（手写 fetch/axios 调用、手写 TS 类型、feature 内私建 client） | 类型与契约脱钩，契约变更不再被 typecheck 捕获；模块边界失守 | 前端 §2.2 规则 4：API 访问收口 `shared/api`；eslint-plugin-boundaries 静态检查；`schema.d.ts` 为生成物禁止手改（CI 校验 `api:gen` 幂等 `[ASSUMPTION]`，验证方式：P0 工程化定校验脚本） |
| AP-5 | mock 与契约漂移不检（mock 手写字段/枚举与 spec 不一致仍继续开发；草案/spec 变更后不重生成） | 联调期集中返工，S4 切换成本剧增 | mock server 由 spec 驱动启动（§3.1 S2）；契约 PR 合入后强制重跑 `api:gen`；CI 校验 `web/openapi.json` 快照新鲜度（前端 §4.1） |
| AP-6 | 服务端状态复制进组件 state、绕过 Query 缓存双写（含 SSE 事件另存本地副本） | 状态多副本不一致，实时更新丢失 | 前端 §4.4 状态分层为已定纪律；review 固定项；SSE 合并函数单测（前端 §7.1）约束唯一入口 |
| AP-7 | 后端绕过 DTO 直吐 ORM 模型、或响应混入敏感字段（`secret_ref`、掩码原值、明文 prompt） | 字段泄漏事故；契约表面稳定实则字段漂移 | 后端 §1.4 三层 DTO 为已定纪律；spec diff 使 response schema 突变在 PR 显形；后端集成测试断言响应键集合 `[ASSUMPTION]`（验证方式：P0 工程化定断言清单） |
| AP-8 | 双源契约并存（阶段一切换后仍手改 `docs/04-api/openapi.json`；草案与导出物拼接使用） | 事实源失守（违反 `docs/README.md` §4 第 2 条），类型与实现各说各话 | 阶段二：CI `git diff --exit-code` 直接失败（后端 §4.5 第 2 条）；切换 PR 一次性迁移（§2.3 规则 1-2） |
| AP-9 | 前端时间处理违规（手工解析/拼接时间字符串、把 UTC 当本地时间、mock 数据用无时区时间串） | 时区错位性缺陷；跨时区部署即炸 | 约定：时间一律经 `shared/lib` 工具（date-fns）；mock fixture 时间串必须带时区后缀（§2.4）；review 固定项 |
| AP-10 | 前端做客户端全量重排/过滤分页数据、或自行缓存越权数据越权展示（developer 展示他团队数据） | 分页语义破坏（total/offset 失真）；团队隔离形同虚设（领域 §3 T 列） | 排序必须经 `sort` 参数（后端 §4.3）；T 隔离以后端行级过滤为准（后端 §4.2），E2E 以 developer 角色断言列表仅含本团队数据 `[ASSUMPTION]`（验证方式：P0 权限模块详设时补该断言用例） |

## 7. 开放问题

| 标记 | 问题 | 确认人 / 阶段 |
|---|---|---|
| Q1 `[ASSUMPTION]` | 阶段一手写过渡草案与 `04-backend-design.md` §4.5「不采用手写 spec 先行」的字面张力：本文以「终态不变 + 草案一次性退役」衔接，是否被评审接受；不接受则取消阶段一、前端等待后端代码先行 | 评审 / 本文档评审时 |
| `[ASSUMPTION]` | 契约草案文件格式（yaml）与存放路径、Prism mock 工具选型（含 examples 支持度）、前端 fixture 挂载方式 | 全栈 / P0 工程化评审 |
| `[ASSUMPTION]` | `api:gen` 幂等 CI 校验脚本、后端响应键集合断言清单、seed 形态（直写 DB or API/webhook 造数） | 全栈 / P0 工程化评审 |
| `[ASSUMPTION]` | spec `info.version` 递增规则（semver 建议）、字段废弃标注期时长（一个里程碑起步）、JSON 字段不做 camelCase 转换、时间序列化细则（`Z` vs `+00:00`、毫秒位）、错误文案 code 映射清单 | 评审 + 全栈 / 04-api 契约定稿与 M0 实跑校准 |
| `[ASSUMPTION]` | 契约阶段一切换时点（预计 M0 中后段）与切换 PR 资源清单 | 全栈 / P0 联调评审 |
| `[TBD-FE]` | 实时通道 SSE vs WebSocket 最终确认（本文 §1 实时推送行与里程碑 `stream` 资源依赖此结论；ADR-0006）；前端 TS client 是否由 spec 自动生成（后端 §4.5 第 4 条） | 前端 / P0 技术设计与联调前 |
| `[TBD-INFRA]` | 认证方式（决定 M0 `session` 资源形态、SSE 认证手段、登录页形态）；前端仅 api 可达的网络约束方式 | 基础设施负责人 / P0 部署设计（沿 HLD §8.2） |
