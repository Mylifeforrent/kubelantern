# 企业 SRE 运维平台开源对标分析报告

> **分析对象**：HolmesGPT · k8sgpt · OneUptime · Keep
> **日期**：2026-10-24
> **方法**：并行研究代理抓取 GitHub README 与官方文档一手页面（合计 30+ 页），结论均有出处；未经一手验证的信息已显式标注。
> **用途**：为自研「企业内部、基于 K8s 的 SRE 运维平台」（后端 Python + FastAPI，前端 React + TS）提供功能参考与 AI 应用设计依据。

---

## 0. 执行摘要

**一句话结论**：四个项目恰好覆盖企业 SRE 平台的四个支柱——

| 项目 | 支柱角色 |
|---|---|
| HolmesGPT | AI 排障 Agent（自主调查、工具调用、安全护栏） |
| k8sgpt | K8s 诊断引擎（SRE 经验规则化 + AI 解释） |
| OneUptime | 监控与事件管理底座（拨测、on-call、incident、遥测存储） |
| Keep | 告警接入与编排（provider 抽象、降噪、workflow 引擎、AI 生成编排） |

**三条核心判断**：

1. **对企业提效最大的不是「AI 问答」，而是确定性自动化**：规则化巡检（k8sgpt analyzer）、告警去重降噪（Keep fingerprint）、on-call 升级链（OneUptime）、workflow 编排（Keep）——这些不依赖大模型、效果可度量，应最先落地；AI 在其上做「解释与调查」放大价值。
2. **AI 的正确用法是「窄权限 + 确定性外壳」**：四个项目无一例外把 LLM 关在笼子里——k8sgpt「规则找问题、AI 只解释」且发 AI 前强制脱敏；HolmesGPT 默认只读 + 工具审批；k8sgpt auto-remediation 明确「LLM 永不持有写权限」；OneUptime 修复 PR 强制人工合并 + 调用预算上限。这套「安全护栏设计模式」比单个功能更值得抄。
3. **技术栈契合度决定参考方式**：Keep（FastAPI + React）与本平台同构，代码与设计模式可直接复用；k8sgpt（Go）移植其 analyzer 规则集与脱敏算法；OneUptime（TS）只学架构与数据模型；HolmesGPT（Python）学机制设计。

### 四项目总览对比

| 维度 | HolmesGPT | k8sgpt | OneUptime | Keep |
|---|---|---|---|---|
| 定位 | 开源 SRE Agent，AI 自主调查生产事故 | 扫描 K8s 集群、诊断并分诊问题的 AI 工具 | 开源一体化可观测 + 事件管理（Datadog 替代） | 开源 AIOps 告警管理（「监控工具的 GitHub Actions」） |
| CNCF | Sandbox（2025-10 接纳） | Sandbox（2023-12 接纳） | — | — |
| License | Apache-2.0 | Apache-2.0 | Apache-2.0 + `ee/` 企业版 | MIT + `ee/`（Open Core，SSO/RBAC 等收费） |
| 技术栈 | Python（CLI/server/operator 三形态） | Go | TypeScript monorepo | **Python FastAPI + React/Next.js** ⭐ |
| Stars（2026-10） | 数千量级（来源口径不一） | ~8.3k | ~7.7k | ~12.4k |
| 对本平台最大价值 | AI 工具调用机制与安全护栏 | analyzer 规则集 + 脱敏机制 | on-call / 事件 / 拨测 / 存储分层 | provider 抽象 + workflow 引擎 + AI 生成编排 |
| AI 应用范式 | Agent 循环自主调查 | 规则找问题、AI 解释 | AI 调查 + 修复 PR 全闭环 | 自然语言→YAML 编排 + AI 步骤 |

---

## 1. HolmesGPT —— AI 排障 Agent 的机制标杆

**定位**：开源 SRE Agent，用 agentic loop 对接实时可观测数据自动调查生产事故、定位根因。官方明确「agentic 调查而非静态 runbook」。CNCF Sandbox 项目，Apache-2.0，Python 实现，CLI / HTTP server / K8s operator 三种形态共享同一内核。

### 1.1 真正提效的功能（按落地价值排序）

| # | 功能 | 为什么提效 | 企业落地注意点 |
|---|---|---|---|
| 1 | **YAML 声明式 Toolset**：一个 `toolsets:` YAML 即把任意 shell 命令暴露为 LLM 工具（`{{ var }}` 由 LLM 推断、`${ENV}` 隐藏凭据、prerequisites 预检） | 企业内部专有系统（CMDB、发布系统、内部 API）**零代码**接入 AI 排障 | bash 命令在容器内执行，需配套镜像与权限治理 |
| 2 | **HTTP Connectors**：YAML 把任意 REST API 变成 LLM 工具，带端点白名单（仅允许批准的 host/path/method） | 安全等级要求高的内部 API 可以精确放行，而非全开 | 白名单维护成本 |
| 3 | **告警自动调查 + 回写闭环**：从 AlertManager / PagerDuty / OpsGenie / Jira 拉告警 → 调查 → `--update` 回写工单/Slack | 直接实现「告警 → AI 预诊断 → 结果回流」的值班减负场景 | PagerDuty/Jira 集成走 CLI 而非服务端 API，自动化编排需自行包装 |
| 4 | **K8s 默认只读 + 复用平台 RBAC**：内置工具只读、尊重 K8s RBAC / Grafana 角色 / 云 IAM；写操作（重启/扩缩容）经独立 Remediation MCP 显式 opt-in | 是企业安全评审最容易通过的设计，直接可抄为平台安全基线 | 写操作 opt-in 的流程需要配套审批制度 |
| 5 | **大输出治理**：服务端过滤聚合、JSON 树限深、per-tool 内存上限（默认 800MB）、OOM 时输出 `[OOM]` 提示引导 LLM 收窄查询重试，超大结果落盘可恢复 | 防止「一次查询撑爆上下文/内存」，是 AI 平台生产化的关键工程细节 | `llm_summarize` transformer 已被官方标记 legacy（有损）；macOS 上 ulimit 不生效 |
| 6 | **HealthCheck CRD 主动巡检**：一条自然语言 query 定义巡检项，K8s 原生管理（一次性/定时/部署验证/事件触发），可嵌入 CI/CD 做部署验证 | 「巡检项即代码」，开发自测、上线验证都能用 | 巡检频率直接放大 LLM 成本，需按巡检项分级选模型 |

### 1.2 AI 运用亮点

- **告警 → Agent 循环的完整链路**：告警 label/annotation + `generatorURL` 构造初始 prompt → LLM 自主选择 toolset 工具 → 执行 shell/HTTP → 输出回注上下文循环，直至产出根因 + 修复建议。服务端 API 暴露 `conversation_history`、`tool_calls`、`follow_up_actions`，并支持 `response_format`（strict JSON schema）供程序消费。
- **工具审批（`enable_tool_approval`）**：高危工具调用前可插入人工审批，或让 LLM 对被禁工具自纠错换路径。
- **企业制度注入**：`additional_system_prompt` 与 behavior controls 允许把内部运维规范写进 Agent 行为约束。
- **运行时依赖图**：从 trace span、K8s ownership、Prometheus label 推断上下游依赖，**无需人工维护拓扑**。
- **零幻觉可视化**：图表由原始查询数据直通客户端渲染，LLM 不产出数值，杜绝编图。
- **全链路审计**：OpenTelemetry 导出完整 prompt / 工具调用 / 答案链路，满足合规审计。
- **公开评测体系**：150+ 场景 benchmark、模型对比、历史结果公开——AI 功能可度量而非 demo。

### 1.3 工程实践亮点

- CLI / server / operator 三形态同一内核，扩展靠 custom toolsets YAML、HTTP/DB 连接器、远程/OAuth MCP、自定义镜像。
- 工具子进程内存隔离 + 落盘 spill，是 AI 平台少见的工程化深度。
- **注意**：admin reload 端点文档自述未鉴权（需网络层限制）；system prompt 原文在源码内，文档未公开。

### 1.4 不建议照搬

- Slack/Teams 双向集成依赖 Robusta 商业平台，开源版能力不完整。
- 作为「被集成引擎」其服务端 API 较薄，更适合借鉴机制后自建服务层。

---

## 2. k8sgpt —— 诊断引擎与「确定性外壳」范式

**定位**：扫描 K8s 集群、诊断并用简单英语分诊问题（"scanning your Kubernetes clusters, diagnosing and triaging issues in simple English"）。CNCF Sandbox（2023-12），Apache-2.0，Go 实现，CLI 与 operator 双形态。

### 2.1 真正提效的功能

| # | 功能 | 为什么提效 | 企业落地注意点 |
|---|---|---|---|
| 1 | **内置 analyzer（SRE 经验代码化）**：确定性规则扫描集群错误（pod/pvc/deployment/node/webhook/service/ingress/netpol 等默认 14 个，hpa/log/security/gateway/karpenter 等可选），输出结构化原始错误（如 ErrImagePull 完整报错） | 自研「体检引擎」可直接移植其规则集与输出 schema，覆盖面现成 | 规则需随 K8s 版本持续维护 |
| 2 | **Anonymization 脱敏**：`--anonymize` 在发往 AI 前把对象名/namespace 等替换为掩码，返回后再本地映射还原 | 企业合规刚需（数据不出域），机制可直接抄 | 掩码会丢失对排障有用的命名语义 |
| 3 | **多 AI backend 抽象**：一套 prompt 层对接 16+ 后端（openai/azure/bedrock/ollama/localai/litellm/customrest…），含 NoOpAI 测试档 | 避免厂商锁定；Ollama/LocalAI 支持内网数据不出域 | 各家输出质量需评测 |
| 4 | **Operator 常驻 + Result CR + sink**：CRD 定义 backend/interval/filters/sink，巡检结果落为 K8s 资源（Result CR）并推送 Slack/Mattermost/CloudEvents | 一次性 CLI 变持续巡检，对应平台「定时巡检 + 告警降噪」模块 | operator 的 Prometheus/Alertmanager 集成细节文档不全（待确认） |
| 5 | **Filters + 自定义 analyzer**：按范围裁剪扫描；任意语言经 schema/proto 扩展规则 | 接入企业内部业务规则与自研检查项 | 需要团队持续投入规则运营 |
| 6 | **Trivy 集成**：`k8sgpt integrate` 复用成熟安全扫描器输出漏洞类 finding | 安全能力不重造轮子 | — |
| 7 | **Auto-remediation（alpha，opt-in）**：**"LLM never receives write authority"**——LLM 只产出意图，operator 自行计算 JSON patch、先 dry-run、只允许窄路径修复 | 「AI 修复建议」的安全边界范本 | alpha 阶段，能力有限 |

### 2.2 AI 运用亮点

- **人机分工（本项目最大的设计洞察）**：analyzer（确定性代码）连接 K8s API 归因错误事件 → 产出结构化原始错误；AI 仅在 `--explain` 环节把原始错误**翻译**为可读诊断 + 修复建议。即**「规则找问题、AI 解释问题」**——幻觉面小、token 成本低、结果可复现。
- **只发送错误片段而非全量 dump**：上下文极小，成本与隐私双重收益。
- **脱敏链路完整**：脱敏 → 发 AI → 返回 → 本地映射还原；operator CRD 也有 `anonymized` 字段，常驻模式同样生效。
- **NoOpAI 后端**：不出 AI 解释、只出原始结果，便于 CI 管道测试。
- （待确认：完整 prompt 模板未从一手页面获取，落地前需读源码复核。）

### 2.3 工程实践亮点

- Go 单二进制 CLI 与 operator **共享同一 analyzer 核心**：同一能力既服务人工排查又服务常驻巡检。
- 定位是「可被平台集成的诊断引擎」而非终端产品：serve 模式（gRPC）、MCP server（12 个工具）、远程缓存（S3/Azure/GCS）——与自研平台的集成思路高度契合。

### 2.4 不建议照搬

- Go 实现，代码不可直接复用，移植规则集需重写。
- 它只做「发现 + 解释」，不做监控、事件、编排——是平台的**一个模块**，不是全部。

---

## 3. OneUptime —— 监控与事件管理底座 + AI 修复闭环

**定位**：开源一体化可观测性与事件管理平台，替代 Pingdom/PagerDuty/Datadog/Sentry/StatusPage 等 9 类工具，主打 "Agentic Observability"。Apache-2.0 + `ee/`（SCIM、审计日志等收费），社区版含完整监控、事件、可观测性与 SAML/OIDC SSO，支持完全离线自托管。Stars ~7.7k。

### 3.1 真正提效的功能

| # | 功能 | 为什么提效 | 企业落地注意点 |
|---|---|---|---|
| 1 | **多地域拨测 + 私有 Probe 架构**：Probe 纯出站 HTTPS（不开入站端口），可部署于内网/VPN/气隙环境；`Probe Agreement` 机制（N 个 probe 结果一致才判定故障）防误报；probe 断连 3 分钟即告警 | 内网拨测 + 防误报共识机制，是企业监控「误报治理」的直接范本 | 内网地址默认拒绝（`PROBE_ALLOW_PRIVATE_NETWORK_MONITORS=true` 才放开），安全默认值设计值得借鉴 |
| 2 | **监控类型覆盖**：API/Ping/Port/DNS/**SSL 证书/域名到期**/关键词/合成监控（最低 10s 间隔）、心跳、SNMP；基础设施代理覆盖 K8s/Docker/VM | 证书与域名到期类「低频但高危」检查一平台全覆盖，可直接抄清单 | — |
| 3 | **On-Call 与升级链**：轮换排班 + Out-of-Office、按严重度路由、超时未确认多级升级（如 0/5/15 分钟三级）、电话/SMS/Slack/Teams 一键 Ack/Escalate/Resolve、完整通知审计时间线、自动解决超时 | 值班减负的核心机制，路由/升级/审计三件套设计成熟 | 国内通知渠道（钉钉/企微）需自研对接 |
| 4 | **Incident 全生命周期 + 状态页联动**：Detect→Alert→Respond→Resolve，自定义状态与 P1-P4，incident 状态变更自动同步状态页；维护窗口自动抑制告警并通知订阅者；postmortem 含根因/影响面/行动项跟踪 | 「对内处置 + 对外沟通」一体，避免两个系统来回搬运 | — |
| 5 | **遥测一体化（ClickHouse）**：PG 管状态、ClickHouse 统一存日志/指标/trace/异常、Valkey 管队列；异常自动关联部署 | 避免自建时「用 PG 存日志」的经典错误；异常-部署关联是排查利器 | 有独立存储运维成本，小规模可先不上 |
| 6 | **IaC 与自动化**：Terraform/REST API 管理 monitor 与 on-call 配置；无代码 Workflow（5000+ 集成）；Runbook（JS 步骤，沙箱执行） | 监控配置进 Git，变更可审计 | — |

### 3.2 AI 运用亮点（该项目 AI 能力强，是差异化重点）

- **AI 调查与 RCA**：新事件/告警自动触发调查，读取 traces/logs/metrics/exceptions/deploys，发布**带引用**的根因分析；人工确认后可转为 fix task。
- **修复 PR 全闭环（Fix PR）**：Runner 克隆仓库 → 建 `oneuptime-fix-*` 分支 → 代码 agent 改动并构建/测试 → 开 PR，**合并必须人工完成**；合并后持续 14 天验证异常是否复发 / p99 是否改善。从「检测 → 根因 → 修复 → 生产验证」的全闭环在开源项目中少见。
- **工程控制成熟**：每次任务限 40 次 LLM 调用 / 10 万输出 token；Runner 不持有 API key（由 server 统一调用并计量）；自动修复默认关闭；自托管可配置任意 provider（含本地 Ollama），代码不出企业内网；上下文脱敏、上限 10 项。
- （未确认：未见「自然语言查询日志/指标」类 BI 式交互。）

### 3.3 架构与实践亮点

- **「同镜像多角色」的模块化单体**而非严格微服务：App 各角色共用一个镜像，Compose 单容器可跑全部，Helm 可拆独立 Deployment——大幅降低部署复杂度，**非常值得自研平台借鉴**。
- 存储职责分明：PG（状态）+ ClickHouse（遥测）+ Valkey（队列），均可外置托管。
- 自托管门槛低（单机 Compose 即可），企业版边界以 `ee/` 目录物理隔离。
- **借鉴价值有限处**：全栈 TypeScript monorepo，对 Python 团队代码复用性低——学架构与功能设计，不搬代码。

---

## 4. Keep —— 告警接入、降噪与 AI 生成编排

**定位**：开源 AIOps 告警管理平台，「GitHub Actions for your monitoring tools」，为告警、自动化、降噪提供单一全景视图。MIT + `ee/`（Open Core：SSO/SAML/LDAP、RBAC/ABAC 属企业版）。Stars ~12.4k。**技术栈与本平台高度同构：后端 Python（FastAPI）+ 前端 React/Next.js + PostgreSQL + Redis/Celery（ARQ）**，代码与设计模式可直接深挖。支持气隙部署。

### 4.1 真正提效的功能

| # | 功能 | 为什么提效 | 企业落地注意点 |
|---|---|---|---|
| 1 | **125+ provider 接入体系**：统一抽象「告警源/数据查询/动作输出」三类角色，一次接入全平台复用；双向（拉取告警 + 执行动作） | 告警接入层的直接蓝图；有 adding-a-new-provider 开发范式可抄 | 国内工具（阿里云监控、钉钉等）需自研 provider；凭据管理要配套 |
| 2 | **fingerprint 去重**：摄入管道内自动执行，每 provider 内置 `FINGERPRINT_FIELDS`，支持「部分合并 + 全同丢弃」两档 | 降噪第一道闸，机制清晰可直接借鉴 | fingerprint 字段设计需按业务定制 |
| 3 | **规则化 correlation → incident**：按告警属性（severity/source/labels）AND/OR 归并成事件，动态命名，**候选事件人工确认**的灰度机制 | 告警风暴 → 少量事件的自动化路径 | 规则爆炸后需运营治理；保留候选审批模式 |
| 4 | **YAML workflow 引擎（核心资产）**：声明式 triggers（手动/定时/告警触发带过滤）/ steps / actions / conditions / foreach / 内置函数 / context 变量；可在编排里查数据库、发 Slack、开工单、做富化 | 实现「告警→查上下文→通知/工单→自动处置」闭环；**编排即代码**，可进 Git 做 IaC/CI-CD 审计 | 引擎自研工作量最大，也可评估直接复用 |
| 5 | **告警富化管道**：mapping（CSV/拓扑按字段匹配）、extraction（从告警字段提取）、workflow 富化；摄入时点执行 | 把「谁值班、什么影响面」等静态知识在告警到达时自动补全，减少人工查证 | 拓扑/CSV 数据需维护 |
| 6 | **API-first**：UI 能做的 API 都能做 | 利于企业自建前端或集成自有系统 | — |

### 4.2 AI 运用亮点

Keep 的 AI 分三层，覆盖「生成编排 / 编排中调用 / 运维问答」全链路：

1. **AI Workflow Builder（自然语言 → 可执行编排）**：聊天式 UI，自然语言描述需求 → AI 生成/修改 workflow YAML，**人在回路（AI 只提议、用户明确同意后才应用）**。是「自然语言→可执行编排」模式的代表实现。
2. **Workflow 内 AI 步骤**：AI 作为 provider 嵌入 steps/actions，用例包括输入归一化、路由分流、severity 判定、摘要生成；支持 OpenAI/Anthropic/DeepSeek/Gemini/Ollama/vLLM——**数据流向由用户定义**，仅显式接入时数据才外发，对数据不出域企业友好。
3. **AI Incident Assistant**：事件页内嵌 Copilot，把 incident 全量上下文（告警列表、描述、受影响拓扑）一次性传给 LLM 做根因分析，并能**通过 provider methods 直接在第三方系统执行命令**（不只问答，可执行；开源版标注 experimental）。

**差异化**：AI 不是独立功能而是贯穿全链路；且 AI 输出均落在**可审计的 YAML workflow** 上（生成物可读、可改、可进 Git），而非黑盒决策。
（待确认：prompt 构造细节官方文档未披露，需读源码。）

### 4.3 工程实践亮点

- **Provider 抽象**：可扩展 Python 组件，入站（推/拉/手动三种模式）+ 出站；每 provider 带 `FINGERPRINT_FIELDS` 去重规则；有 template 范式降低新 provider 开发成本。
- **告警处理流水线固定顺序**：摄入 → enrichment → deduplication，各环节职责单一。
- **可配置即代码**：告警规则、workflow、provider 均可 provision（IaC/CI-CD 友好）。
- **注意**：前端是 Next.js 而非 Vite SPA；ee/ 目录代码不得参考搬运。

---

## 5. AI 应用模式横向对比（方法论层）

四个项目代表了四种可复用的 AI 应用范式：

| 范式 | 代表项目 | 做法 | 适用场景 | 优劣 |
|---|---|---|---|---|
| A. 规则找问题、AI 解释问题 | k8sgpt | 确定性 analyzer 先产出结构化错误，LLM 只做「翻译」 | 集群体检、已知错误模式诊断 | 幻觉最小、成本最低、结果可复现；上限取决于规则覆盖 |
| B. Agent 循环自主调查 | HolmesGPT、OneUptime | LLM + 工具调用循环，自主取数、验证假设、出根因 | 未知的复杂故障、跨系统排障 | 能力上限高；需重护栏（只读/审批/输出治理/预算） |
| C. 自然语言 → 可执行编排 | Keep | NL 生成 YAML workflow，人审核后应用，产物可进 Git | 自动化处置、巡检项生成 | 产物可审计可版本化；依赖 workflow 引擎底座 |
| D. AI 修复代码全闭环 | OneUptime | 查根因 → 代码 agent 改码 → PR → 人工合并 → 生产验证 14 天 | 有工程团队的故障修复 | 价值最高；投入与治理要求也最高 |

**共同的安全护栏设计模式**（比单个功能更值得抄）：

| 护栏 | 出处 |
|---|---|
| 发 AI 前强制脱敏、返回后本地还原 | k8sgpt anonymization |
| 默认只读，写操作显式 opt-in | HolmesGPT K8s toolset / Remediation MCP |
| LLM 永不持有写权限，由确定性层计算 patch + dry-run | k8sgpt auto-remediation |
| 高危工具调用前人工审批 | HolmesGPT tool approval |
| 调用预算上限（次数/token） | OneUptime（40 次/10 万 token 每任务） |
| Runner 不持有密钥，密钥由服务端统一管理计量 | OneUptime |
| 人在回路：AI 只提议，人确认后生效 | Keep Workflow Builder / OneUptime Fix PR |
| 全链路审计（prompt/工具调用/答案） | HolmesGPT OTel 导出 |
| 支持本地模型（Ollama/vLLM），数据不出域 | 全部四个项目 |

---

## 6. 对本平台（huntai-sre）的落地建议

结合本仓库技术栈（Python + FastAPI + uv；React + TS + Vite + Tailwind + shadcn/ui）与四个项目的成熟度，建议按「先确定性、后 AI」的顺序分五期演进。以下阶段划分为建议方案，优先级需结合团队资源确认 `[TBD-BIZ]`。

### 6.1 功能路线图

| 阶段 | 能力 | 借鉴来源 | 说明 |
|---|---|---|---|
| **P0 确定性底座** | 多集群接入（只读 kubeconfig + 平台 RBAC） | HolmesGPT 只读基线 | 一切的前提 |
| | 集群体检引擎（K8s 错误模式规则库） | k8sgpt analyzer 规则集（移植为 Python） | 确定性诊断，输出结构化 finding |
| | 告警接入层（provider 抽象：告警源/查询/动作三类角色） | Keep provider 范式 | 同栈代码可直接参考 |
| | 告警去重（fingerprint 机制 + 摄入管道） | Keep deduplication | 降噪第一道闸 |
| **P1 AI 解释层**（性价比最高的 AI 切入点） | AI 诊断解释 + 修复建议（范式 A） | k8sgpt | 规则找问题、AI 解释；只发错误片段 |
| | 发 AI 前脱敏 + 返回还原 | k8sgpt anonymization | 合规刚需 |
| | 多模型抽象（LiteLLM 一类方案，支持本地 Ollama/vLLM） | k8sgpt AI backends / Keep | 避免锁定、数据不出域 |
| | 诊断摘要推送 IM（钉钉/企微） | Keep provider 出站动作 | 渠道 `[TBD-BIZ]` |
| **P2 事件与响应** | On-call 排班 + 升级链 + 通知审计 | OneUptime | 值班减负核心 |
| | Incident 生命周期 + postmortem + 状态页联动 | OneUptime | 对内处置 + 对外沟通一体 |
| | 告警关联规则（候选事件人工确认制） | Keep correlation | 降噪第二道闸 |
| | 拨测 + 私有 Probe（出站-only + 多 probe 共识） | OneUptime Probe | 内网监控 + 防误报 |
| **P3 Agent 调查与编排** | YAML toolset / HTTP connector 机制 | HolmesGPT | 内部系统零代码接入 AI |
| | Agent 告警自动调查（范式 B）+ 工具审批 | HolmesGPT、OneUptime | 带引用的 RCA |
| | Workflow 引擎（YAML 声明式编排） | Keep | 处置闭环，可进 Git |
| | AI Workflow Builder（范式 C：NL→YAML 人审核） | Keep | 产物可审计 |
| | 定时巡检 / 部署验证（自然语言巡检项） | HolmesGPT HealthCheck CRD | 注意 LLM 成本分级 |
| **P4 远期** | AI 修复 PR 闭环（范式 D） | OneUptime Fix PR | 人工合并 + 合并后验证 |
| | 窄路径自动处置 | k8sgpt auto-remediation | LLM 无写权限，确定性层算 patch + dry-run |

### 6.2 架构借鉴要点

1. **模块化单体起步**（OneUptime「同镜像多角色」）：不要一开始就微服务；probe/runner 等边缘组件独立部署。
2. **存储分层**：PG 管业务状态；遥测（日志/指标/trace）规模上来后上 ClickHouse；Redis/Celery 类队列管异步任务。小规模可先 PG + Redis 起步 `[TBD-INFRA]`。
3. **CLI / 服务端 / 定时任务三形态共享同一内核**（HolmesGPT）：诊断能力既能被人手动调用，也能被巡检调度。
4. **API-first + 配置即代码**（Keep、OneUptime）：UI 全功能有 API；provider/workflow/巡检规则全部可进 Git。
5. **复用现有可观测栈**：若已有 Prometheus/Grafana/Loki，优先做 toolset/connector 集成而非自建存储 `[TBD-INFRA]`。
6. **气隙与本地模型**为第一优先约束设计（全部四项目的共同经验）。

### 6.3 参考方式三档

| 档位 | 内容 |
|---|---|
| 直接复用/移植 | Keep 的 provider 抽象与去重流水线设计（同栈）；k8sgpt analyzer 规则集与脱敏算法（移植为 Python）；HolmesGPT toolset YAML schema 设计 |
| 改造借鉴 | Keep workflow 引擎语义（它是 Celery/ARQ 实现）；OneUptime on-call/incident 数据模型 |
| 只学思想 | OneUptime TS 代码与微服务拆分；k8sgpt Go 代码；各项目 ee/ 目录（License 限制，禁止参考搬运） |

### 6.4 风险与合规注意

- **License 边界**：Keep `ee/`（SSO/RBAC/ABAC）与 OneUptime `ee/`（SCIM/审计日志）为商业许可，代码不可复制；Apache-2.0 / MIT 部分可合规借鉴（保留版权声明）。
- **LLM 成本治理**：巡检频率、模型分级（巡检用小模型、事故调查用强模型）、调用预算上限——三者都要在平台层内置，不要留给用户自觉。
- **K8s 版本兼容**：analyzer 规则集需随集群版本维护，纳入平台自身的 CI。
- **AI 安全默认值**：只读默认、写操作 opt-in、脱敏默认开启、自动修复默认关闭。

### 6.5 待确认事项

- `[TBD-BIZ]` 平台目标用户规模与监控对象规模（决定是否需要 ClickHouse 级遥测存储）——由业务负责人在立项阶段确认。
- `[TBD-BIZ]` 数据是否允许出域、可用哪些模型（决定 AI backend 选型与脱敏强度）——由安全/合规负责人确认。
- `[TBD-INFRA]` 是否已有 Prometheus/Grafana/Loki/ELK 等可复用栈——由基础设施负责人确认。
- `[TBD-BIZ]` on-call 通知渠道（钉钉/企微/Slack）与排班制度——由业务负责人确认。

---

## 7. 参考资料

**HolmesGPT**
- GitHub：https://github.com/HolmesGPT/holmesgpt
- 文档站：https://holmesgpt.dev/latest/ ｜ Why HolmesGPT：https://holmesgpt.dev/latest/why-holmesgpt/
- 内置 Toolsets：https://holmesgpt.dev/latest/data-sources/builtin-toolsets/ ｜ 自定义 Toolsets：https://holmesgpt.dev/latest/data-sources/custom-toolsets/
- 工具执行安全：https://holmesgpt.dev/latest/data-sources/tool-execution-safety/
- HTTP API：https://holmesgpt.dev/latest/reference/http-api/ ｜ Operator 健康检查：https://holmesgpt.dev/latest/operator/health-checks/
- CNCF 项目页：https://www.cncf.io/projects/holmesgpt

**k8sgpt**
- GitHub：https://github.com/k8sgpt-ai/k8sgpt ｜ Operator：https://github.com/k8sgpt-ai/k8sgpt-operator
- 自动修复：https://github.com/k8sgpt-ai/k8sgpt-operator/blob/main/AUTO_REMEDIATION.md
- CNCF 项目页：https://www.cncf.io/projects/k8sgpt
- 官方文档：https://docs.k8sgpt.ai （analyzers / ai-backends / privacy / filters）

**OneUptime**
- GitHub：https://github.com/OneUptime/OneUptime ｜ 官网：https://oneuptime.com
- AI Agent：https://oneuptime.com/docs/ai/ai-agent
- Custom Probe：https://oneuptime.com/docs/en/probe/custom-probe ｜ 自托管架构：https://oneuptime.com/docs/en/self-hosted/architecture
- On-Call：https://oneuptime.com/product/on-call ｜ Incident：https://oneuptime.com/product/incident-management ｜ 状态页：https://oneuptime.com/product/status-page

**Keep**
- GitHub：https://github.com/keephq/keep ｜ 文档：https://docs.keephq.dev
- Workflow：https://docs.keephq.dev/workflows/overview ｜ 去重：https://docs.keephq.dev/overview/deduplication
- 关联规则：https://docs.keephq.dev/overview/correlation-rules ｜ 富化：https://docs.keephq.dev/overview/enrichment/mapping
- AI Workflow Assistant：https://docs.keephq.dev/overview/ai-workflow-assistant ｜ AI in Workflows：https://docs.keephq.dev/overview/ai-in-workflows ｜ AI Incident Assistant：https://docs.keephq.dev/overview/ai-incident-assistant
