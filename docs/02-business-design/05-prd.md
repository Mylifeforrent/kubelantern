# 产品需求文档（PRD）

| 元信息 | |
|---|---|
| 状态 | accepted |
| 日期 | 2026-10-24 |
| 依据 | `docs/README.md`（治理规则与台账）、`01-research/01-benchmark-report.md`（四支柱、三条核心判断、P0-P4 路线图、安全护栏模式）、`02-business-design/01-domain-model.md`（§2 范围、§3 角色、§4 子域、§6 状态机、§7 BR-01~13、§8 非功能）、`02-business-design/02-interaction-flows.md`（L1-L4/A1-A3、§4.1 八页面、§4.2 三操作流、§5 分期）、`02-business-design/03-clickable-prototype.html`（可点击原型 v0.1）、`02-business-design/04-hifi-design-spec.md`（视觉与布局单一事实源）、`03-tech-design/01-data-model.md`、`03-tech-design/02-architecture.md`、`03-tech-design/03-frontend-design.md`、`03-tech-design/04-backend-design.md`、`03-tech-design/05-fe-be-boundary.md`（技术五篇）、`04-api/README.md` + `04-api/openapi.yaml`（契约草案与端点总览） |
| 读者 | 产品 · 研发 · SRE · 评审 |

> 本文是全部前期文档的**汇总性顶层文档**：读完本文即知产品全貌，细节一律通过路径引用下钻。单一事实源纪律（`docs/README.md` §4 第 2 条）：业务规则只引用 BR-xx 编号（唯一事实源 `01-domain-model.md` §7）；枚举只引用 `01-data-model.md` §3；API 细节以 `04-api/` 契约为准；色值与布局细节以 `04-hifi-design-spec.md` 为准——本文不复制正文。事实缺失标 `[ASSUMPTION]` / `[TBD-*]`，禁止编造。

---

## 1. 产品概述

**一句话定位**：面向企业内部的、基于 Kubernetes 的 SRE 运维平台——以确定性自动化为底座（多集群接入、规则化巡检、告警接入与降噪、事件与值班响应），在其上以「窄权限 + 确定性外壳 + 人在回路」方式叠加 AI 解释、AI 调查与 AI 生成编排。

**解决的四个核心痛点**（对标报告 §0，四项目各覆盖一支柱）：

1. 告警分散、噪声大 → 统一接入 + 去重降噪 + 关联成事件（Keep provider/fingerprint/correlation 范式）；
2. 集群问题依赖人工经验 → 规则化巡检 + AI 解释（k8sgpt analyzer + 范式 A）；
3. 值班响应无流程保障 → on-call 排班 + 升级链 + 通知审计（OneUptime）；
4. AI 落地无安全边界 → 窄权限 + 确定性外壳的 AI 能力体系（四项目共同护栏模式，对标报告 §5）。

**目标**：P0-P2 交付 MVP 核心（确定性告警管道、巡检、AI 解释、事件与值班闭环），P3 二期（Agent 调查、Workflow 编排），P4 远期（AI 修复 PR、窄路径自动处置）——能力分解见领域文档 §2 分期表。

**非目标**（领域文档 §2 Out of scope）：日志/指标/trace 的采集与存储（复用企业已有 Prometheus/Grafana/Loki `[TBD-INFRA]`）；工单系统自建（对接企业已有工单 `[TBD-BIZ]`）。

## 2. 用户与角色

角色定义与完整权限矩阵（资源 × 动作 × Y/N/T）唯一事实源为 `01-domain-model.md` §3，本文不复制矩阵正文：

| 角色 | 标识 | 职责一句话 | 主战场页面 |
|---|---|---|---|
| 平台管理员 | `admin` | 平台配置、集群与凭证、用户与角色、AI 预算策略、写操作审批开关 | 管理后台、AI 任务中心 |
| SRE 工程师 | `sre` | 告警/事件处置、巡检认领、AI 工具使用与审批（限本团队） | 告警工作台、候选队列、事件详情、巡检看板、AI 任务中心 |
| 值班经理 | `oncall_manager` | 排班表、升级策略、通知渠道维护；事件只读 | 排班与升级 |
| 研发工程师 | `developer` | 本团队资源只读 + finding 认领，无 AI 审批权 | 巡检看板（T）、告警（T） |
| 访客 | `viewer` | 状态页与公开看板只读 | 状态页（public 条目） |

> 写操作（对集群的一切变更类动作）在权限之外还需通过审批流（BR-02），权限矩阵只表达「谁可以发起」（领域 §3 注）。角色按五类扁平建模 `[ASSUMPTION]`（验证方式：首批使用团队访谈，领域 §9）。前端只做权限的展示控制，判定一律后端权威（`03-frontend-design.md` §3.2、`05-fe-be-boundary.md` §1）。

## 3. 产品原则

三条建设原则贯穿全部功能（对标报告 §0 核心判断、领域 §1），第三条以 BR-xx 落地为唯一事实源（`01-domain-model.md` §7，此处仅一句话概括）：

1. **先确定性、后 AI**：L1-L4 主干不依赖模型可用性，AI（A1-A3）挂接在确定性产出之上，可整体熔断为 NoAI 模式（HLD §5.1）。
2. **窄权限 + 确定性外壳 + 人在回路**：默认只读、脱敏前置、预算上限、审批挂起、AI 只提议（对标报告 §5 护栏模式表）。
3. **BR-01~13 逐条落地**：

| BR | 一句话 | BR | 一句话 |
|---|---|---|---|
| BR-01 | 发往外部模型的内容必须先脱敏（掩码可逆映射仅存本地） | BR-08 | 升级链每级超时自动升级，每步投递与响应留痕 |
| BR-02 | 对 K8s 默认只读，写操作须独立审批 + 管理员显式开启 | BR-09 | 巡检发现按严重度分流：info 只入看板，warn+ 转告警并可触发 AI |
| BR-03 | AI 任务必须有预算上限（默认 40 次 / 100k token），超限优雅降级 | BR-10 | 全部写操作与 AI 调用留全量审计，不可删改 |
| BR-04 | 候选事件必须人工确认才立项；auto 模式有准入门槛 | BR-11 | 自动修复默认关闭，LLM 不持有写权限 |
| BR-05 | AI 生成的 Workflow/修复建议仅为提议，确认前不得执行 | BR-12 | 模型路由支持本地模型；出域由管理员配置，默认仅本地 |
| BR-06 | P1/P2 事件状态自动同步状态页，可人工撤回 | BR-13 | 通知渠道降级链可配置；全失败不停链 |
| BR-07 | 维护窗口内告警自动抑制并完整记录 | | |

## 4. 范围与分期

链路编号 L1-L4/A1-A3 定义于 `02-interaction-flows.md` §1-§3；分期与链路映射见其 §5；验收口径 M0-M2 定义于 `05-fe-be-boundary.md` §4（M = Playwright E2E 对应流通过 + 契约同步检查通过）。

| 分期 | 交付能力 | 对应链路 | 对应页面（交互 §4.1） | 验收口径 |
|---|---|---|---|---|
| **P0 确定性底座** | 多集群只读接入、集群体检引擎（规则库+调度+执行）、告警 webhook 接入与先落盘、去重/富化、告警工作台、用户角色与审计、管理后台 | L1（接入+去重+富化）、L4（无 AI） | 登录、告警工作台、巡检看板、管理后台 | **M0**（`05-fe-be-boundary.md` §4）：告警处置流 P0 形态 E2E + 契约阶段一切换 + 权限位全组合单测 |
| **P1 AI 解释层** | AI 诊断解释 + 修复建议（范式 A）、脱敏（BR-01）、多模型抽象与本地优先（BR-12）、预算（BR-03）、NoAI 熔断 | A1 全量、L4 接入 A1 | AI 任务中心（新增）、巡检看板（AI 解释）、告警工作台（AI 解释 tab） | **M1**：AI 审批流 E2E + 告警处置流补 AI 真实/NoAI 双分支 + BR-03 预算链路测试 |
| **P2 事件与响应** | 告警关联（候选确认制 BR-04）、维护窗口（BR-07）、事件全生命周期 + 状态页联动（BR-06）+ 复盘、on-call 排班 + 升级链 + 通知审计（BR-08/13） | L1（关联）、L2、L3（不含 Agent） | 候选事件确认队列、事件列表/详情、排班与升级；告警工作台（关联归因） | **M2**：候选事件确认流 E2E + 告警处置流 P2 完整形态 + 三流 E2E 全绿 + BR-04 链路测试 |
| **P3 Agent 调查与编排** | A2 Agent 自动调查（带引用 RCA + 工具审批）、YAML Workflow 引擎、A3 自然语言生成编排（BR-05） | A2、A3、L3 接入 Agent | Workflow 编排（新增） | 详设另立（HLD §6.3、后端 §3.9）；页面已入契约 P3 概要级端点 |
| **P4 远期** | AI 修复 PR 闭环（人工合并 + 合并后验证）、窄路径自动处置 | 范式 D | — | 仅 BR-11 约束下规划，实体暂不细化（领域 §2） |

> 拨测（对标报告 P2 项）在领域与交互文档中未建实体与链路，暂不纳入本 PRD 范围；如需补入须先修订领域文档（`01-domain-model.md` §2）`[ASSUMPTION]`（验证方式：P2 设计前与业务负责人确认）。

## 5. 功能需求

组织方式：**用户旅程 → 页面 → 功能点**。页面口径 = 交互文档 §4.1 八页面 + 事件详情子视图（`04-hifi-design-spec.md` §3 共 9 个页面视图 + 告警详情抽屉等全局浮层）。优先级 P0-P3 与 §4 分期一致。「端点」引自 `04-api/README.md` §3 契约草案（67 路径/100 操作；个别路径命名存在已登记的 C1-C4 待裁决冲突，见 §10，以契约为准）。

### 5.1 旅程 A：告警接入与处置（P0 主旅程）

> 场景：admin 配置集群与告警源 → 监控源上报 → 管道自动去重富化 → sre 在工作台实时看到并处置。

| FR | 功能点 | 描述 | 优先级 | 关联（BR / 链路 / 端点 / 视图） |
|---|---|---|---|---|
| FR-01 | 集群接入管理 | 接入/更新/移除目标集群（只读凭证引用制、探活状态、连接测试） | P0 | BR-02；集群接入域；`/clusters*`；hifi §3.10 |
| FR-02 | Provider 告警源接入 | 告警源 CRUD：type/category(source/query/action)/pull_mode/fingerprint_fields 配置 | P0 | L1；告警管理域；`/providers*`；hifi §3.10 |
| FR-03 | 告警 webhook 接入 | 机器入口接收上报，归一化→先落盘→入队→202 应答 `{alert_id, merged}`；平台故障不丢告警 | P0 | L1；非功能 §8；`POST /alerts/webhook/{provider_key}` `[CONFLICT-C1]` |
| FR-04 | 去重降噪管道 | fingerprint 两级去重（全同丢弃 + 部分合并计数）、管道四步（接入→去重→富化→关联）计数卡实时可视化 | P0 | L1；D-1；SSE `alert.*`；hifi §3.1 管道卡 |
| FR-05 | 富化规则管理 | matchers + mappings(extraction/mapping) 规则 CRUD，告警到达时自动补全 team/影响面/oncall 组 | P0 | L1；`/enrichment-rules*`；hifi §3.2 富化 tab |
| FR-06 | 告警工作台列表 | 合并计数（×N 徽标）、severity/状态筛选（入 URL）、降噪归因摘要、指纹截断展示 | P0 | L1；`GET /alerts`；hifi §3.1 |
| FR-07 | 告警详情抽屉 | 500px 右抽屉 5 tab：详情 / 原始 Payload / 富化字段 / AI 解释 / 关联事件；降噪归因信息框 | P0/P1 | `GET /alerts/{id}`；hifi §3.2（AI tab 三态 + NoAI 变体） |
| FR-08 | 告警认领 Ack | sre 认领告警，升级链停止，留痕 | P0 | BR-08；告警处置流步骤 4；`POST /alerts/{id}/ack` `[CONFLICT-C2]` |
| FR-09 | 告警关闭 | 人工关闭（resolve），活跃指纹释放 | P0 | L1；`POST /alerts/{id}/close` |
| FR-10 | 一键转事件 | 告警人工立项为事件并跳转详情 | P2 | L3；`POST /alerts/{id}/convert-to-incident` |
| FR-11 | 误报抑制建议 | 三原因单选 + 补充说明，提交进降噪规则反馈池 | P0 | L1；hifi §3.1 抑制建议 modal；告警处置流步骤 5 |
| FR-12 | 实时更新 | 列表行级精确 patch、候选徽标、NoAI 全局 Banner、断连降级轮询 | P0 | SSE（`[TBD-FE]` ADR-0006）；`GET /realtime/stream` `[CONFLICT-C4]`；前端 §4.3 合并矩阵 |

### 5.2 旅程 B：巡检与诊断（P0/P1）

> 场景：sre 配置巡检策略 → 定时/手动执行 → 确定性 finding 产出并分流 → warn+ 转告警 → 可选 AI 解释。

| FR | 功能点 | 描述 | 优先级 | 关联 |
|---|---|---|---|---|
| FR-13 | 巡检规则库管理 | 内置规则（k8sgpt analyzer 移植）+ 自定义规则，k8s_version_fit 版本适配 | P0 | L4；`/inspection-rules*`；hifi §3.10 规则库卡 |
| FR-14 | 巡检策略与调度 | 集群 × 规则集 × cron × ai_explain_level 配置 | P0 | BR-09；`/inspection-policies*`；hifi §3.6 策略卡 |
| FR-15 | 手动触发巡检 | 策略级手动 run（trigger=manual） | P0 | L4；`POST /inspection-policies/{id}/run` |
| FR-16 | Finding 产出与分流 | 只读拉取→确定性判定→结构化 finding→严重度分流（warn+ 转告警并回链；info 仅看板） | P0 | BR-09；L4；`GET /findings`、`GET /inspection-runs*` |
| FR-17 | 巡检看板 | 集群切换、健康分与统计卡、近 7 次 run 趋势堆叠柱、findings 表（AI 解释行内展开/生成中态） | P0 | L4；hifi §3.6 |
| FR-18 | Finding 处置 | 认领 / 忽略（原因必填）/ 重开（复现） | P0 | Finding 状态机（领域 §6）；`POST /findings/{id}/ack|ignore|reopen`（ack `[CONFLICT-C2]`） |
| FR-19 | 一键 AI 解释 | finding 行内触发 A1：脱敏→路由→预算→结构化诊断+修复建议；info 级禁用并提示 | P1 | BR-01/03/09；A1；`POST /findings/{id}/explain`、`GET /alerts/{id}/explanations`；hifi §3.6 aibox |

### 5.3 旅程 C：AI 能力治理（P1，P3 扩展）

> 场景：AI 任务在预算与审计内运行 → 高危动作挂起审批 → sre/admin 审批 → 结果回填；模型不可用整体 NoAI。

| FR | 功能点 | 描述 | 优先级 | 关联 |
|---|---|---|---|---|
| FR-20 | AI 任务中心 | 任务列表（类型/模型/状态 8 态）、预算进度双维度（calls/tokens，>90% 变红）、月度统计卡（含本地模型占比） | P1 | BR-03/10；`GET /ai/tasks*` `[CONFLICT-C3]`；hifi §3.7 |
| FR-21 | AI 审批流 | pending_approval 行高亮 + toast「前往审批」→ 审批 Modal（将要执行的工具与参数、预算已消耗、30min 超时说明）→ 批准继续 / 拒绝终止（上下文留存） | P1 | BR-02/05；三操作流之一；`POST /ai/tasks/{id}/approve|cancel`；hifi §3.7 审批 modal |
| FR-22 | 调用链审计 | AICallLog 逐次调用（模型/工具/摘要/时延/结果）只读查看 | P1 | BR-10；`GET /ai/tasks/{id}/call-logs`；hifi §3.7 调用链 modal |
| FR-23 | NoAI 降级 | 模型端点熔断：A1 透出原始错误+人工入口、A2/A3 拒新任务；全局状态显著标识 | P1 | HLD §5.1；ADR-0005；`system` SSE 主题；hifi aibox NoAI 变体 + Banner |
| FR-24 | Agent 调查（P3） | 事件详情发起 A2：上下文构造→只读工具循环→高危挂起→带引用 RCA 回写时间线 | P3 | A2；BR-01/02/03；`POST /incidents/{id}/ai-investigation` |
| FR-25 | NL 生成 Workflow（P3） | 自然语言描述→生成 YAML 草稿→diff 双栏预览→确认入库（approved_by 必填）或「需要修改」回 AI 再生成 | P3 | A3；BR-05；`/workflows*`；hifi §3.8 diff modal |

### 5.4 旅程 D：事件与值班闭环（P2）

> 场景：关联规则产出候选 → sre 确认立项 → 状态页同步 → 值班升级链投递与 Ack → 止血恢复 → P1/P2 生成复盘 → 规则回流。

| FR | 功能点 | 描述 | 优先级 | 关联 |
|---|---|---|---|---|
| FR-26 | 候选事件队列 | 候选卡：命中规则编号+描述、时间窗、相似度进度条、成员告警列表；实时新增徽标/toast | P2 | BR-04；L1 关联段；`GET /incident-candidates`；hifi §3.3 |
| FR-27 | 候选确认立项 | 确认 → 创建事件 + incident_alerts 关联 + 告警置 correlated → 跳事件详情 | P2 | BR-04；候选确认流步骤 1；`POST /incident-candidates/{id}/confirm` |
| FR-28 | 候选驳回回流 | 三原因（规则过宽/时间窗过长/富化字段错误）单选卡组提交，原因结构化留存供规则调优 | P2 | BR-04；候选确认流步骤 2；`POST /incident-candidates/{id}/reject`；hifi 驳回 modal |
| FR-29 | 事件列表 | ID/标题/严重度/状态/值班人/状态页同步/时间 | P2 | L3；`GET /incidents`；hifi §3.4 |
| FR-30 | 事件详情与时间线 | 状态机步进条、四色节点时间线（auto/man/esc/ai）、右栏升级状态/状态页/关联告警卡 | P2 | L3；`GET /incidents/{id}`；hifi §3.5 |
| FR-31 | 事件状态机推进 | 主按钮随状态切换（确认/止血/恢复/关闭），误报 cancel 原因必填；非法迁移 409 | P2 | Incident 状态机（领域 §6）；`POST /incidents/{id}/acknowledge|mitigate|resolve|close|cancel` |
| FR-32 | 人工处理记录 | 时间线底部输入行追加人工节点 | P2 | L3；时间线 append |
| FR-33 | 状态页同步与撤回 | P1/P2 事件自动同步 public/internal 条目与更新，可人工撤回 | P2 | BR-06；`POST /incidents/{id}/status-page/sync|undo`、`/status-page/entries*` |
| FR-34 | 复盘与行动项 | P1/P2 关闭时生成模板（时间线自动汇总），root_cause 编辑、action_items 分派跟踪 | P2 | L3；`GET|PUT /incidents/{id}/postmortem` |
| FR-35 | 关联规则管理 | conditions(AND/OR)+时间窗+mode(auto/candidate)；auto 准入（≥30 天零误报）校验 | P2 | BR-04；`/correlation-rules*` |
| FR-36 | 维护窗口管理 | scope 匹配器 + 起止时间，窗口内抑制、结束未恢复重入管道 | P2 | BR-07；`/maintenance-windows*` |
| FR-37 | 排班管理 | 周视图（主/备班）、轮换规则、临时顶班 overrides 编辑 | P2 | L2；`/oncall-schedules*`；hifi §3.9 |
| FR-38 | 升级策略管理 | 多级 levels（目标/渠道/超时）+ 渠道降级链配置 | P2 | BR-08/13；`/escalation-policies*` |
| FR-39 | 升级链投递与 Ack | 逐级投递、超时自动升级、失败降级不停链、每步 notification_records 留痕；IM 一键 Ack | P2 | BR-08/13；L2；`GET /notification-records` |
| FR-40 | 通知记录审计查询 | 按 alert/incident/状态检索投递与响应留痕 | P2 | BR-08；同上 |

### 5.5 旅程 E：平台管理与会话（P0）

| FR | 功能点 | 描述 | 优先级 | 关联 |
|---|---|---|---|---|
| FR-41 | 用户与角色管理 | 用户 CRUD、角色授予（含 developer team_scope）、停用 | P0 | 领域 §3；`/users*`、`/roles` |
| FR-42 | 凭证引用管理 | 仅 secret_ref 引用与轮换信息，**永不回显凭证值** | P0 | 安全红线/D-2；hifi §3.10 硬规则；credentials 端点 `[TBD-INFRA]`（04-api §7） |
| FR-43 | AI 预算与模型路由配置 | 默认预算、本地优先、出域开关 | P1 | BR-03/12；hifi §3.10 AI 预算卡 |
| FR-44 | 审计日志查询 | 全量写操作审计只读检索（who/when/what/cost） | P0 | BR-10；`GET /audit-logs` |
| FR-45 | 登录与会话 | 登录、会话角色获取（形态随 `[TBD-INFRA]` 认证方式） | P0 | `POST /auth/token`（占位）；前端 §3.2 |
| FR-46 | 全局搜索 | 顶栏跨 alerts/incidents/findings 搜索 | P0 | 前端 widgets/global-search；hifi §2.3 |
| FR-47 | 权限展示控制 | 路由守卫 + `can()` 权限位控制按钮/入口（判定后端权威） | P0 | 领域 §3；前端 §3.2；`05-fe-be-boundary.md` §1 |
| FR-48 | 通知铃与徽标 | 待处理计数角标、侧栏各域计数徽标 | P0 | hifi §2.2/§2.3 |

### 5.6 三条关键操作流的功能分解（E2E 验收对象，`03-frontend-design.md` §7.2）

| 操作流（交互 §4.2） | 功能分解（按序） | 验收里程碑 |
|---|---|---|
| **告警处置流**（sre 主路径） | 收到通知 → 点入详情（FR-07）→ 查看 AI 解释（FR-19，P0 以 NoAI/未上线降级态断言）→ 认领 Ack（FR-08，升级链停止）→ 转事件（FR-10，P2 真实化）或直接关闭（FR-09）→ 误报标记抑制建议（FR-11） | M0（P0 形态）→ M1（补 AI 真实分支）→ M2（P2 完整形态） |
| **候选事件确认流**（BR-04 人机协作） | 候选卡展示（FR-26：命中规则+成员告警+相似度）→ 确认立项（FR-27，断言事件创建与成员关联）/ 驳回（FR-28，断言三原因提交回流） | M2 |
| **AI 审批流**（BR-02/BR-05） | AI 任务挂起（pending_approval，FR-20/23）→ 任务中心 + IM 通知审批人 → Modal 展示工具与参数、预算已消耗（FR-21）→ 批准（任务继续）/ 拒绝（终止，上下文留存） | M1 |

## 6. 非功能需求

唯一事实源：领域文档 §8（数据边界/凭据安全/可用性/性能/成本）+ HLD §4（可用性/性能/安全的架构机制），数值沿既有标注，本文不复制不编造：

| 维度 | 要求 | 出处 |
|---|---|---|
| 数据边界 | 默认数据不出域；外部模型使用需显式配置 | 领域 §8（BR-12） |
| 凭据安全 | 集群凭证、Provider 凭据不入库不入日志，引用密钥管理（secret_ref）；前端零密钥 | 领域 §8；D-2；前端 §8.3 |
| 可用性 | 平台自身故障不得影响告警接收（接入层先落盘暂存）；PG 单点风险以备份+落盘缓解 | 领域 §8；HLD §4.1 |
| 性能 | 告警接入管道 P95 < 3s `[ASSUMPTION]`（待容量规划验证）；巡检不阻塞告警管道（队列优先级拆分）；前端性能预算见前端 §6（`[ASSUMPTION]` P0 末校准） | 领域 §8；HLD §4.2；前端 §6 |
| 成本 | LLM 成本按任务类型分级（巡检解释小模型、事件调查强模型），月度成本看板 | 领域 §8；BR-03/09 |
| 审计 | 全量写操作与 AI 调用留痕不可删改（库级 REVOKE 兜底） | BR-10；D-6；后端 §6.2 |
| 可访问性 | 焦点环、aria 标注、`prefers-reduced-motion` 全关、状态不作纯色信息 | hifi §2.9 |

## 7. 交互与视觉

- **视觉与布局单一事实源**：`04-hifi-design-spec.md`（token 总表 §1、全局布局 §2、9 视图逐页排版 §3、组件规范 §4、偏差治理 §5）；提取基准为可点击原型 `03-clickable-prototype.html`（v0.1，1039 行，Keep 风格亮色版）。本文不复制任何色值。
- **关键约束引用**：AI 语义紫色专色专用（§1.1.4）；卡片零阴影靠边框分层（§1.5 硬规则）；每屏主操作唯一主按钮、AI 能力一律 AI 按钮（§4.2 层级用法）；演示装置（角色切换器、模拟告警接入按钮）生产不保留（§4.9）；原型改动必须先改 hifi 文档再改代码（§5.2）。
- **响应式**：断点 820/1024（Tailwind md/lg 映射，前端 §2.3）；窄屏仅保证基本可用 `[ASSUMPTION]`。
- **操作流与信息架构**：交互文档 §4（八页面 + 三操作流）；页面路由表与守卫见前端 §3。

## 8. 技术方案概要

**架构**（HLD `02-architecture.md` §1/§6）：模块化单体 + worker——`api`（FastAPI 单体：API 网关 + Webhook 接入 + 全部领域模块 + SSE + SPA 静态资源）与 `worker`（arq 异步执行面：告警管道/巡检/Agent/Workflow/通知/回放 + 全部 cron）两个部署单元，同一 Docker 镜像不同启动命令；PostgreSQL（全部业务状态，32 张表）+ Redis（判重缓存/队列 broker/推送 Stream）；AI 网关为唯一模型出域出口（BR-01/03/10/12 收口）；微服务化触发条件已写明（HLD §6.2）。

| 层 | 选型 | 出处 |
|---|---|---|
| 后端 | Python ≥3.12 + FastAPI + uv + SQLAlchemy async + Alembic + arq | 后端 §1.1 |
| 前端 | React + TypeScript + Vite SPA + Tailwind + shadcn/ui（源码内置）+ react-router + TanStack Query/Table/Virtual + zustand + RHF/zod + recharts + Monaco(P3) | 前端 §1 |
| 数据 | PostgreSQL 单库 + Redis（版本 `[TBD-INFRA]`） | 数据模型 §1 |
| 实时 | SSE 倾向（`[TBD-FE]` ADR-0006），Last-Event-ID 断连恢复 | HLD §3.3、后端 §5 |
| 部署 | Docker Compose 起步 → 远期 K8s（Helm，同镜像多角色） | HLD §3.4 |
| 错误/分页/契约 | RFC 7807；offset/limit + `{items,total,offset,limit}`；OpenAPI 两阶段 | 后端 §4、边界 §2 |

**契约两阶段**（`05-fe-be-boundary.md` §2）：当前以 `04-api/openapi.yaml` 手写草案为唯一临时事实源（前端 mock 与类型生成基于它）；后端可稳定导出 spec 且覆盖前端已消费资源时（预计 M0 中后段）一次性切换为 FastAPI 导出物 + CI 强制同步，草案退役归档。

**里程碑**（`05-fe-be-boundary.md` §4）：M0（P0：告警工作台/巡检/管理后台 + 告警处置流 P0 形态 + 契约切换）、M1（P1：AI 任务中心 + AI 审批流 + 处置流 AI 分支）、M2（P2：候选队列/事件/排班 + 候选确认流 + 三流全绿）；验收统一为 Playwright E2E + 契约同步检查双通过。

## 9. 成功指标

**禁止编造 KPI 数字**——以下为指标框架；基线与目标值全部 `[TBD-BIZ]`（业务负责人 / 上线前结合历史数据与容量输入确认，与领域 §8 性能项 `[ASSUMPTION]` 的容量规划同轮校准）：

| 指标 | 定义口径 | 来源与现状 |
|---|---|---|
| 告警降噪率 | 工作台「去重抑制 + 关联归并 + 维护窗口抑制」合计 / 接入总量；管道四步计数卡即为数据来源 | FR-04 统计卡已有展示位；基线/目标 `[TBD-BIZ]` |
| MTTR（事件平均恢复时长） | incidents 表 acknowledged_at→resolved_at 均值（按 severity 分组） | 事件域数据已有；基线/目标 `[TBD-BIZ]` |
| AI 审批及时率 | pending_approval→决定时长 ≤ 审批超时（默认 30min `[ASSUMPTION]`）的比例 | ai_tasks 字段已有；基线/目标 `[TBD-BIZ]` |
| 告警管道 P95 | webhook 上报到入库；既有目标 < 3s（领域 §8 `[ASSUMPTION]` 待容量验证，分段预算 HLD §4.2） | 既有标注，非本文新设 |
| LLM 月成本 | 月度调用/token 成本 + 预算占比；模型分级路由后的人均摊 | 领域 §8 成本项、FR-20 统计卡已有；基线/目标 `[TBD-BIZ]` |

## 10. 风险与依赖

汇总 HLD §8.1 风险表、后端 §8 开放问题、契约 C1-C4，每条给缓解方向；完整开放问题清单见 §11。

| # | 风险/依赖 | 影响 | 缓解方向 | 出处 |
|---|---|---|---|---|
| R1 | PostgreSQL 单点（起步单实例） | 平台不可用或数据丢失 | 定期备份+恢复演练；高可用 `[TBD-INFRA]`；接入层落盘保证告警不丢 | HLD §8.1 |
| R2 | Redis 缓存与队列双用途，故障双影响 | 判重性能与任务投递同降 | 判重降级 PG 兜底（D-1）、队列降级落盘回放（§5.3）；实例规划 `[TBD-INFRA]` | HLD §8.1 |
| R3 | P95 < 3s 与容量未验证（告警峰值 `[TBD-BIZ]`） | 告警风暴下管道积压 | 预算拆解+P0 末压测校准；限流+落盘+回放兜底 | HLD §8.1/§4.2 |
| R4 | LLM 成本失控 | 月度成本超预算 | BR-03 预算上限 + BR-09 严重度分级路由 + 月度成本看板 | HLD §8.1 |
| R5 | 巡检规则随 K8s 版本腐化 | 误报/漏检 | k8s_version_fit 字段 + 规则集纳入平台 CI | HLD §8.1 |
| R6 | 单人运维知识集中 | 关键人风险 | 文档化 docs/ + runbook 沉淀 + 同镜像多角色降低部署复杂度 | HLD §8.1 |
| R7 | 认证方式未定（`[TBD-INFRA]`） | 阻塞 M0 登录/会话/SSE 认证形态 | 尽快由基础设施负责人裁决（P0 部署设计）；契约已留 `/auth/token` 占位 | 后端 §8、04-api §7 |
| R8 | **契约路径命名 C1-C4 待裁决** | webhook 路径歧义（C1：`/alerts/webhook/{provider_key}` vs `/webhooks/{provider_name}`）、ack/acknowledge 同词不同形（C2）、`/ai/tasks` vs `/ai-tasks`（C3）、`/realtime/stream` vs `/stream`（C4） | 已在 04-api §5 登记，裁决前不引入第三方案；裁决后回写 openapi.yaml 与被冲突文档之一，后端代码落地前必须完成 | 04-api §5 |
| R9 | 阶段一手写草案与后端 §4.5「不采用手写 spec 先行」的张力 | 契约流程返工（若评审不认可过渡草案） | 以「终态不变 + 草案一次性退役」衔接；评审裁定（`05-fe-be-boundary.md` §7 Q1） | 边界 §2.1/§7 |
| R10 | 外部依赖：密钥管理后端、可观测栈对接、工单对接均 `[TBD-INFRA]`/`[TBD-BIZ]` | P0 工程化与部署设计阻塞项 | P0 设计前集中确认（§11 INFRA 组） | 数据模型 §9 等 |
| R11 | arq 生态规模小于 Celery | 冷门场景缺现成方案 | 任务原语已收敛；ADR-0002 留重评触发条件 | HLD §3.2 |
| R12 | Webhook 暴露面（机器入口） | 未授权上报/恶意灌入 | Provider 令牌/签名 `[ASSUMPTION]` + 入口限流（超限仍落盘） | HLD §8.1、后端 §3.2 |

## 11. 开放问题汇总表（核心增量）

汇总范围：`01-research/01-benchmark-report.md`、`01-domain-model.md`、`02-interaction-flows.md`、`04-hifi-design-spec.md`（四篇业务/调研文档的开放问题节 + 正文关键标注）与 `03-tech-design/` 五篇、`04-api/README.md`（各 §7/§8/§9 开放问题节 + 正文关键标注）。**同主题多文档重复登记的合并为一行并全部列出处**；正文散落的同类 `[ASSUMPTION]` 按主题归并。编号 OP-*（B=BIZ、U=UX、F=FE、E=BE、I=INFRA、A=ASSUMPTION、C=CONFLICT）。

### 11.1 `[TBD-BIZ]`（业务负责人确认）

| # | 问题 | 阶段 | 出处 |
|---|---|---|---|
| OP-B01 | 通知渠道组合（钉钉/企微/短信/电话）与升级链各级默认超时（含 L2 默认 5/15min、BR-13 降级链配置） | P2 设计前 | 领域 §9、交互 §7、数据模型 §9、HLD §8.2、后端 §8、04-api §7 |
| OP-B02 | 数据出域政策与可用模型清单（BR-12 出域默认值、AI_EGRESS_ENABLED 放开值） | P1 设计前 | 领域 §9、benchmark §6.5、后端 §8 |
| OP-B03 | 团队/服务归属数据源（CMDB 对接 or 平台自维护；users.team 建模走向） | P0 设计前 | 领域 §9、数据模型 §9 |
| OP-B04 | 状态页受众（对外/对内）、默认可见性、对外发布流程是否需审批 | P2 设计前 | 领域 §9、交互 §7、数据模型 §9、04-api §7 |
| OP-B05 | raw_payload 与各流水表保留天数、audit_logs/ai_call_logs 归档年限与介质、ai_mask_mappings 清理天数 | 对应阶段上线前 | 数据模型 §6.1/§9 |
| OP-B06 | 告警峰值与容量输入（P0 压测前提）；poll 模式 Provider 首批清单 | P0 上线前 / P0 设计前 | HLD §8.2、后端 §8 |
| OP-B07 | 同指纹 severity 变化策略（取最高/最新）与恢复事件语义映射（Provider 归一化细则） | P0 管道详设 | 后端 §8 |
| OP-B08 | auto 关联模式准入细则（BR-04「≥30 天零误报」判定口径） | P2 设计前 | 后端 §8 |
| OP-B09 | 候选驳回原因英译（reject_reason 值域） | P2 设计前 | 04-api §7 |
| OP-B10 | 平台目标用户规模与监控对象规模（决定是否需要 ClickHouse 级遥测存储、D-9 分区时机） | 立项/P0 建库评审 | benchmark §6.5、数据模型 §9 |
| OP-B11 | on-call 排班制度输入（轮换周期约定，影响 FR-37 细化） | P2 设计前 | benchmark §6.5 |

### 11.2 `[TBD-UX]`（UX 确认）

| # | 问题 | 阶段 | 出处 |
|---|---|---|---|
| OP-U01 | 告警工作台信息密度与降噪归因展示方式（合并原因可视化；影响详情归因字段结构） | P0 前端设计前 | 交互 §7、前端 §9、04-api §7 |
| OP-U02 | developer 角色团队隔离的数据边界展示方式 | P2 前端设计前 | 领域 §9、前端 §9 |
| OP-U03 | 加载态规范（skeleton/spinner，原型全站未覆盖） | P0 前端开发前 | hifi §6 |
| OP-U04 | 表格分页 / 无限滚动控件形态（原型无分页 UI） | P0 前端开发前 | hifi §6 |
| OP-U05 | tooltip 形态（`data-tooltip` 已埋属性无样式） | P0 前端开发前 | hifi §6 |
| OP-U06 | 错误态视觉（接口失败、全局错误页） | P0 前端开发前 | hifi §6 |
| OP-U07 | 暗色模式是否恢复（token 全按亮色提取） | P0 前端开发前 | hifi §6 |
| OP-U08 | 大屏（≥1440）与窄屏（≤768/375）适配（原型宣称四断点仅实现两条） | P0 末视觉走查 | hifi §6 |
| OP-U09 | 多语言（当前仅简体中文） | 国际化需求出现时 | hifi §6 |
| OP-U10 | Workflow 编辑器（P3）、排班编辑（P2）、管理后台写表单的布局稿（原型仅列表/只读形态） | 各分期设计前 | hifi §6 |

### 11.3 `[TBD-FE]` / `[TBD-BE]`（前后端确认）

| # | 问题 | 阶段 | 出处 |
|---|---|---|---|
| OP-F01 | 实时通道最终确认：SSE vs WebSocket（倾向 SSE，结论落 ADR-0006；影响 FR-12/FR-23 与 `/realtime/stream` 端点） | 前端 / P0 技术设计 | 交互 §7、HLD §3.3/§8.2、前端 §9、后端 §8、边界 §7、04-api §7 |
| OP-F02 | 前端 TS client 是否由 openapi.json 自动生成（04-backend §4.5 第 4 条遗留 `[TBD-FE]`） | 前端 / P0 联调前 | 后端 §8、04-api §7 |
| OP-E01 | developer 团队行级过滤的索引支撑（`enrichments->>'team'` 表达式索引）——确认后回流 01-data-model 增补 | 后端负责人 / P0 权限模块详设 | 后端 §8 |

### 11.4 `[TBD-INFRA]`（基础设施负责人确认）

| # | 问题 | 阶段 | 出处 |
|---|---|---|---|
| OP-I01 | 用户认证方式（SSO/LDAP/本地）与用户会话机制——影响登录页、SSE 认证手段、users 表字段、`/auth/token` 形态（R7） | P0 部署设计 | 数据模型 §9、HLD §8.2、前端 §9、后端 §8、04-api §7、边界 §7 |
| OP-I02 | 全部依赖与运行时版本锁定清单（uv.lock 首锁、npm/Node/engines、CI 平台与验证命令；ADR-0008） | P0 工程化 | HLD §8.2、后端 §8、前端 §9 |
| OP-I03 | 部署目标环境（Compose 单机 or 已有 K8s）、PG 备份与高可用、Redis 部署形态与实例规划（缓存/队列是否分实例） | P0 部署设计 | HLD §3.4/§8.2、数据模型 §9 |
| OP-I04 | 模型出域网络策略（worker/api 进程外呼端点限制）、模型抽象层是否引入 LiteLLM（ADR-0004） | P1 部署设计 | HLD §8.2、后端 §8 |
| OP-I05 | secret_ref 密钥后端选型、掩码加密密钥管理（信封加密 KMS）、迁移执行时机编排 | P0-P1 部署设计 | 数据模型 §9、后端 §8 |
| OP-I06 | 已有可观测栈（Prometheus/Grafana/Loki）与工单系统对接方式（决定是否补充集成表） | P0 设计前 | benchmark §6.5、领域 §9、数据模型 §9 |
| OP-I07 | credentials 资源端点未入契约草案（secret_ref 形态定后补端点或并入集群/Provider 资源；影响 FR-42） | P0 工程化 | 04-api §7 |

### 11.5 `[ASSUMPTION]`（按主题归并，验证方式见各出处）

| # | 主题 | 验证方式/阶段 | 出处 |
|---|---|---|---|
| OP-A01 | 角色按五类扁平建模 | 首批使用团队访谈 | 领域 §3/§9 |
| OP-A02 | 告警管道 P95 < 3s 及 HLD §4.2 各段预算为工程设定 | P0 末压测按真实告警样本校准回填 | 领域 §8、HLD §4.2 |
| OP-A03 | 限流默认速率、积压切换阈值、回放 stale 阈值、NoAI 熔断参数（N 次/半开周期）、审批超时 30min、A1 失败重试 1 次 | P0/P1 压测与上线前以真实任务校准（ADR-0005） | HLD §5、后端 §6.3、交互 §7 |
| OP-A04 | 数据模型非状态机枚举值域群（cluster_status、alert/finding severity、incident_source、candidate 状态、similarity、notification_status、run 状态/触发、ai_explain_level、result_code 等）与技术演绎（主键策略、text 默认长度、软删/分区/版本化「一版本一行」、D-9 分区时机、D-11 多对多偏离领域 ER） | 各对应阶段详设评审；确认后回流领域/数据模型文档修订 | 数据模型 §2/§3/§5/§9 |
| OP-A05 | 告警 upsert 与「去重三段」的物理映射、规则集缓存与失效策略、管道任务是否拆分段、cron 多副本 advisory lock 防重、机器触发审计写入边界、审计与推送最终一致性取舍、arq 延迟任务丢失率（升级链兜底扫描必要性）、SSE 保留窗口/心跳/连接上限与多副本广播、asyncio 测试插件与集成测试 DB 方案（testcontainers vs fixture DB） | P0 工程化/详设评审/压测收敛 | 后端 §3/§5/§7/§8 |
| OP-A06 | 后端候选依赖清单引入前逐项审计（structlog、croniter、import-linter、testcontainers、fakeredis、pytest 插件） | P0 工程化评审 | 后端 §1.1 |
| OP-A07 | 前端工程设定：性能预算数值、SSE 事件命名与幂等键、轮询间隔、API 资源名示意、`web/` 目录名、排班周视图自实现、sre 排班只读开放、E2E 基座形态、边界 lint 工具选型 | P0 工程化/联调评审与 04-api 定稿 | 前端 §4/§9 |
| OP-A08 | 契约流程工程设定：草案 yaml 格式、Prism mock 选型与 fixture 挂载、`api:gen` 幂等 CI 校验、响应键集合断言、seed 形态、spec info.version 递增规则、字段废弃标注期时长、JSON 不做 camelCase 转换、时间序列化细则（Z/+00:00、毫秒位）、错误文案 code 映射清单、阶段一切换时点与 PR 清单 | P0 工程化/联调评审、04-api 定稿、M0/M1 实跑校准 | 边界 §2/§3/§5/§7 |
| OP-A09 | 契约草案逐条标注：权限矩阵未单列的读写收敛、告警级 AI 解释与 ai_explanations(finding_id) 存储映射、webhook provider_key 语义与 Provider 令牌方案、事件时间线/升级摘要派生结构、错误码清单、SSE 事件命名（`alert.updated` 等，行使边界 §1 授予的命名权） | 随 yaml 内逐条验证方式与对应阶段详设评审收敛 | 04-api §4/§7 |
| OP-A10 | 视觉假设：对比度数值（≥4.5:1 等）照抄原型注释未独立验证；Tailwind 变量命名与文字档归并、辅助间距收敛（4px 基数） | 前端 / P0 实装以工具逐对复核与视觉走查 | hifi §1.4/§1.8/§6 |
| OP-A11 | 桌面优先（375px 级窄屏仅基本可用）、角色切换器生产不保留（admin 视角模拟是否保留待确认） | P0 末设备抽样 / 会话详设 | 前端 §2.3/§3.2 |
| OP-A12 | 拨测能力未建实体暂不入范围 | P2 设计前与业务确认（§4 注） | 本文 §4 |

### 11.6 `[CONFLICT]`（已登记待裁决，非本文新增）

| # | 冲突 | 状态 | 出处 |
|---|---|---|---|
| OP-C01 | C1：webhook 路径 `/alerts/webhook/{provider_key}`（草案）vs `/webhooks/{provider_name}`（后端 §4.1）；lint 报告草案存在路由歧义 | 待评审裁决；后端代码落地前必须完成，裁决后回写 openapi.yaml 与被冲突文档之一 | 04-api §5 |
| OP-C02 | C2：`ack` vs `acknowledge` 同词不同形（`/alerts/{id}/ack`、`/findings/{id}/ack` vs 后端示例 `acknowledge`） | 同上 | 04-api §5 |
| OP-C03 | C3：`/ai/tasks`（草案）vs `/ai-tasks`（后端 §4.1 kebab-case 单段） | 同上 | 04-api §5 |
| OP-C04 | C4：`GET /realtime/stream`（草案）vs `GET /stream`（后端 §5.1） | 同上 | 04-api §5 |

## 12. 附录：文档地图

本 PRD 引用的全部文档（相对 `docs/` 路径；状态见 `README.md` §2 台账）：

| 文档 | 一句定位 |
|---|---|
| `README.md` | 文档治理入口：目录体系、状态台账、单一事实源规则 |
| `01-research/01-benchmark-report.md` | 四开源项目（HolmesGPT/k8sgpt/OneUptime/Keep）对标、四条 AI 范式与安全护栏模式、P0-P4 路线图建议 |
| `02-business-design/01-domain-model.md` | 业务建模唯一事实源：范围分期、五角色权限矩阵、子域地图、实体字典、五类状态机、BR-01~13、非功能约束 |
| `02-business-design/02-interaction-flows.md` | 链路与交互唯一事实源：L1-L4/A1-A3 时序、§4.1 八页面、§4.2 三关键操作流、§6 异常降级 |
| `02-business-design/03-clickable-prototype.html` | 可点击原型 v0.1（视觉提取基准，生产不保留演示装置） |
| `02-business-design/04-hifi-design-spec.md` | 视觉与布局单一事实源：token 总表、全局布局、9 视图排版、组件规范、偏差治理 |
| `02-business-design/05-prd.md` | 本文：产品全貌汇总与开放问题总清单 |
| `03-tech-design/01-data-model.md` | 存储唯一事实源：32 张表、枚举字典 §3、D-1~D-11 决策、保留与脱敏、分期建表 |
| `03-tech-design/02-architecture.md` | HLD：六层架构、组件清单、技术选型（arq/SSE 倾向）、质量属性、部署拓扑、ADR 索引 |
| `03-tech-design/03-frontend-design.md` | 前端 LLD：技术栈、模块边界、路由权限、数据流与 SSE 合并、页面要点、测试与工程化 |
| `03-tech-design/04-backend-design.md` | 后端 LLD：uv/FastAPI 工程结构、领域模块、API 层原则（RFC 7807/分页/OpenAPI 导出同步）、SSE、横切与测试 |
| `03-tech-design/05-fe-be-boundary.md` | 前后端边界：职责总表、契约两阶段流程、mock 与联调、M0-M2 里程碑、反模式清单 |
| `04-api/README.md` | 契约治理说明：两阶段流程导读、67 路径/100 操作端点总览、约定速览、C1-C4 冲突登记 |
| `04-api/openapi.yaml` | OpenAPI 3.1 契约草案——阶段一唯一临时事实源（端点字段级定义以此为准） |
