# 前端设计与技术栈

| 元信息 | |
|---|---|
| 状态 | accepted |
| 日期 | 2026-10-24 |
| 依据 | `02-business-design/02-interaction-flows.md`（§4 人机交互设计：8 个关键页面与 §4.2 关键操作流）、`02-business-design/03-clickable-prototype.html`（视觉与交互基准，含 design token 雏形与响应式断点）、`02-business-design/01-domain-model.md`（§3 角色权限矩阵；BR-xx 只引编号）、`03-tech-design/02-architecture.md`（HLD：组件 #1 `web-spa`、§3.1 前端栈冻结、§3.3 实时通道、ADR-0006/0008/0011） |
| 读者 | 前端、全栈研发 |

> 本文是 HLD 组件 #1 `web-spa` 的详细设计，不与 `02-architecture.md` 冲突：SPA 静态资源由 api 部署单元提供 `[ASSUMPTION]`、实时通道 SSE vs WebSocket `[TBD-FE]` 沿用 HLD §3.3 结论不做定案、依赖版本锁定遵循 ADR-0008。业务规则只引用 BR-xx 编号（唯一事实源 `01-domain-model.md` §7）。**视觉基准**：`03-clickable-prototype.html`（Keep 风格亮色版）；本文不罗列颜色值，色板、语义 token 细节由后续高保真设计规范文档定稿，本文只约定 token 的迁移机制与响应式断点。**API 资源名**：本文出现的资源名均为示意，唯一事实源为 `04-api/` OpenAPI spec（规划中），spec 定稿后以生成的 TS 类型为准 `[ASSUMPTION]`（验证方式：04-api 评审时逐条对齐）。

---

## 1. 技术栈与版本策略

### 1.1 冻结项与锁定原则

以下为仓库根 `AGENTS.md` 冻结结论（非本文决策），本文只展开：

| 层 | 技术 | 说明 |
|---|---|---|
| UI 框架 | React + TypeScript | SPA，无 SSR/Next.js（HLD §3.1：仅参考 Keep 组件形态不搬架构） |
| 构建 | Vite | 路由级代码分割（§6） |
| 样式 | Tailwind CSS | 语义 token 经 CSS variables 映射（§2.3） |
| 组件 | shadcn/ui（**源码内置**） | 经 CLI 将组件源码复制进 `src/shared/ui/`，不是 npm 运行时依赖；可按原型定制 |
| 包管理 | npm | 禁止 pnpm / yarn；`package-lock.json` 为单一事实源 |

**锁定原则：以 npm 精确版本固化（`save-exact=true`），具体版本号 `[TBD-INFRA]`**（基础设施负责人 / P0 工程化，登记于 ADR-0008）；本文一律不写具体版本号，P0 首次构建时锁定当期稳定版。升级必须走 PR + lock 文件 diff + 项目验证命令（对齐 HLD §3.1 锁定原则）。

**依赖引入纪律**：禁止自行引入未审计的第三方依赖（项目安全红线）；本文推荐之外的任何新依赖必须先评估并在 PR 中说明理由。

### 1.2 补选库对比与推荐

选型约束（同 HLD §3.2 立场）：单人项目、能独立运维、依赖面最小化。每个决策给候选对比 + 推荐 + 理由；版本遵循 §1.1 锁定原则。

#### 1.2.1 路由

| 维度 | **react-router（推荐）** | TanStack Router |
|---|---|---|
| 生态与文档 | 最大多数，问题排查材料多 | 增长中，示例相对少 |
| 类型安全 | 路径参数类型安全；search params 需手写 schema | 全链路类型安全（含 search params）是核心卖点 |
| 本项目需求匹配 | 8 个页面 + 1 层详情嵌套，需求简单 | search params 重度类型诉求本项目不存在（筛选参数少，§4.4） |
| 运维成本 | API 稳定多年，单人熟悉度优先 | API 演进较快，跟进成本高 |

**推荐 react-router**：路由需求收敛（§3.1 路由表），无复杂嵌套与 search-param 类型链条；生态最大意味着单人排障成本最低。TanStack Router 的类型优势在更大规模路由树才兑现。

#### 1.2.2 服务端状态

| 维度 | **TanStack Query（推荐）** | SWR | RTK Query |
|---|---|---|---|
| 缓存操作粒度 | `setQueryData` 精确 patch（SSE 增量合并的关键能力，§4.3） | 只提供 mutate/validate 粗粒度 | 需 Redux store |
| 轮询 | `refetchInterval` 支持动态函数（AI 审批轮询 §5.5） | 支持但控制弱 | 支持 |
| DevTools | 官方完善 | 弱 | 依赖 Redux DevTools |
| 依赖面 | 独立无绑定 | 独立 | 引入整套 Redux |

**推荐 TanStack Query**：§4.3 的「SSE 推送 → 缓存精确合并」是本项目服务端状态的核心形态，Query 的细粒度缓存操作与动态轮询是三者中唯一完备的；且与 TanStack Table/Virtual 同生态。

#### 1.2.3 客户端状态

| 维度 | **zustand（推荐）** | Jotai | Redux Toolkit |
|---|---|---|---|
| 概念成本 | 单 store + selector，最低 | 原子组合模型 | action/reducer/slice 样板多 |
| 体积 | 极小 | 小 | 大 |
| 本项目全局态数量 | 仅 3 类：当前会话用户、AI 熔断全局状态（HLD §5.1）、实时连接状态（§4.3） | 同左 | 同左 |

**推荐 zustand**：本项目客户端全局态极少（列表筛选走 URL，§4.4；表单走 RHF），zustand 以最低概念成本覆盖；Jotai 的细粒度依赖追踪在大规模原子图才有优势。

#### 1.2.4 表单与校验

| 维度 | **react-hook-form + zod（推荐）** | Formik | TanStack Form |
|---|---|---|---|
| 渲染性能 | 非受控，重渲染少 | 受控重渲染多 | 非受控 |
| 维护状态 | 活跃 | 维护放缓 | 较新、API 未稳定 |
| schema 复用 | zod schema 同时用于提交前校验与（未来）SSE payload 兜底解析 | 需配 yup，两套 | 自带校验，生态弱 |

**推荐 react-hook-form + zod**：表单面窄（抑制建议、驳回原因、审批、NL 生成等 modal 表单），但 zod 作为唯一校验库可复用于运行时数据防御（§4.3）；组合为社区事实标准。

#### 1.2.5 图表

| 维度 | **recharts（推荐）** | Apache ECharts | Chart.js（react-chartjs-2） |
|---|---|---|---|
| 范式 | React 声明式组件 | 命令式实例，需自封装 | 命令式，封装层类型一般 |
| 体积 | tree-shakable，可控 | 全量引入大（按需引入配置繁琐） | 中 |
| 与 shadcn/ui 关系 | shadcn/ui 官方 Charts 即基于 recharts，源码内置策略一致 | 无 | 无 |
| 能力上限 | 中（万级以下数据点） | 高（大数据量、复杂交互） | 中 |

**推荐 recharts**：本项目图表面窄（巡检趋势堆叠柱、预算进度、告警统计，见原型），数据量小；与 shadcn/ui 源码内置组件天然一致。**重评触发条件**：出现万级数据点或复杂交互图表时重新评估 ECharts（登记于 §9）。

#### 1.2.6 表格与虚拟滚动

- **TanStack Table**：shadcn/ui Data Table 官方底层即 TanStack Table，无第二候选必要；告警/AI 任务/巡检 findings 列表统一用它。
- **长列表虚拟滚动**：

| 维度 | **TanStack Virtual（推荐）** | react-virtuoso |
|---|---|---|
| 范式 | headless，配合任意表格实现 | 开箱即用组件 |
| 表格行虚拟化 | 与 TanStack Table 官方配合示例成熟 | 动态高度列表强、表格场景一般 |
| 生态 | 与 Query/Table 同家族 | 独立 |

**推荐 TanStack Virtual**：与表格方案同生态、headless 可精确对齐 shadcn/ui 表格样式（原型表格形态）。

#### 1.2.7 实时客户端（SSE / WebSocket，`[TBD-FE]` 沿用 HLD §3.3）

通道协议本身不定案（ADR-0006）；本文只定**客户端封装抽象**：`RealtimeClient` 接口（`connect / disconnect / on(event, handler)` + 连接状态订阅），协议实现可替换。默认实现选型：

| 维度 | 原生 EventSource | **@microsoft/fetch-event-source（推荐）** | 自封装 fetch 流 |
|---|---|---|---|
| 自定义 header | 不支持（认证只能靠 cookie） | 支持（Bearer / cookie 均可） | 支持 |
| POST 订阅（按页面过滤事件） | 不支持（只能 GET + query） | 支持 | 支持 |
| 自动重连 | 内建 | 提供 onclose 控制重试（可加退避） | 需完全自写（重连/解析/退避全自造） |
| 依赖 | 零 | 小 | 零但等于重造上两者 |

**推荐 @microsoft/fetch-event-source**：认证方式 `[TBD-INFRA]`（HLD §8.2，SSO/LDAP/本地未定），header 能力保证认证选型落地时不返工；POST 订阅为「告警工作台只订告警域事件」的按需过滤留出空间。若 ADR-0006 结论为 WebSocket，则替换实现类（如 sockettej/websocket 库或原生 WebSocket 封装），上层 `RealtimeClient` 接口与事件分发层不变。

#### 1.2.8 代码编辑器（P3，YAML + diff 场景）

| 维度 | **Monaco（@monaco-editor/react，推荐）** | CodeMirror 6 |
|---|---|---|
| Diff 视图 | 内置 DiffEditor，双栏 diff 开箱即用（A3 链路核心交互，交互文档 §3 A3） | 需 @codemirror/merge，可用但配置多 |
| YAML 支持 | 配 monaco-yaml（schema 校验） | 官方语言包成熟 |
| 体积 | 大（约 MB 级） | 模块化、小 |
| 加载策略 | 动态 import 独立 chunk，仅 P3 Workflow 编辑器使用 | 同样可动态加载 |

**推荐 Monaco**：A3 的「diff 预览 → 人工确认 BR-05」是 P3 核心交互，Monaco DiffEditor 成熟度最高；因 P3 才引入且强制动态加载（§6），体积不影响 P0-P2 首屏。**重评触发条件**：构建集成或加载问题显著、或体积敏感场景增多时切换 CodeMirror 6（登记于 §9）。

#### 1.2.9 OpenAPI 类型生成

| 维度 | **openapi-typescript + openapi-fetch（推荐）** | @hey-api/openapi-ts | orval |
|---|---|---|---|
| 生成物 | 纯类型 + 薄运行时（KB 级） | 完整 client | 全量 Query hooks + mock |
| 生成代码维护成本 | 最小（只有 `.d.ts`） | 中 | 大（生成物多、迭代快、定制性弱） |
| 与模块边界（§2.2）关系 | Query hooks 在 feature 层手写薄封装，边界清晰 | hooks 形状固定 | 全量 hooks 会把 API 形状漏进所有 feature，与边界纪律冲突 |

**推荐 openapi-typescript + openapi-fetch**：单人维护生成代码，噪音最小是第一优先级；Query hooks 由各 feature 自持（§2.2 边界规则）。

#### 1.2.10 配套小件（随 shadcn/ui 生态带入，不做对比）

- toast：sonner（shadcn/ui 官方推荐，对应原型 toast 形态）；
- 日期：date-fns（shadcn/ui Calendar/react-day-picker 的既定依赖）；
- 工具：clsx / tailwind-merge 等 shadcn 组件源码自带依赖，随 CLI add 进入。

## 2. 工程结构与模块边界

### 2.1 目录树

前端工程根目录名 `web/` `[ASSUMPTION]`（验证方式：P0 工程化时随 monorepo 布局定稿，与 HLD §6 部署单元一起登记）。

```text
web/
├── openapi.json                # 后端导出的 spec 快照（api:gen 输入，CI 校验新鲜度）
├── package.json / package-lock.json   # npm 唯一事实源（ADR-0008）
├── vite.config.ts              # dev proxy → api 进程（§8.3）
├── tailwind.config.ts / tsconfig.json / .env.*
└── src/
    ├── main.tsx                # 入口
    ├── app/                    # 应用装配层
    │   ├── router.tsx          # 路由表 + React.lazy + 守卫挂载（§3）
    │   ├── providers.tsx       # QueryClient / zustand / toast / Realtime 装配
    │   ├── routes/             # 路由级页面薄壳（只组合 feature 出口）
    │   └── guards/             # RequireAuth / RequireRole（§3.2）
    ├── features/               # 业务子域模块（对齐交互文档 §4.1 八页面与领域 §4 子域）
    │   ├── alerts/             # 告警工作台；内含 candidates/（候选事件确认队列，归告警管理域关联段）
    │   ├── incidents/          # 事件列表 / 事件详情 / 时间线 / 状态页同步 / 复盘入口
    │   ├── inspections/        # 巡检看板（findings / runs / 策略）
    │   ├── ai-tasks/           # AI 任务中心（审批 / 调用链 / 预算）
    │   ├── workflows/          # Workflow 编辑器（P3，动态加载）
    │   ├── oncall/             # 排班管理（周视图 / 升级策略）
    │   ├── admin/              # 管理后台（集群 / Provider / 规则库 / 用户 / AI 配置）
    │   ├── session/            # 登录与当前会话（形态随 [TBD-INFRA] 认证方式）
    │   └── <feature>/          # 每个 feature 统一内部结构：
    │       ├── api/            # 本域 Query hooks + mutation（只经 shared/api 客户端）
    │       ├── components/     # 域内组件
    │       ├── <feature>.types.ts
    │       └── index.ts        # 唯一公开出口
    ├── widgets/                # 跨域组合组件（只 import 各 feature 的 index.ts）
    │   ├── app-shell/          # 侧栏 + 顶栏 + 内容区（原型 .side/.topbar 布局骨架）
    │   ├── global-search/      # 顶栏全局搜索（跨 alerts/incidents/findings）
    │   └── ai-status-banner/   # NoAI 熔断全局标识（HLD §5.1 下行状态）
    └── shared/
        ├── api/                # openapi-fetch client、错误规约、RealtimeClient 封装
        ├── ui/                 # shadcn/ui 源码内置组件 + 原型 token 化基础件（Chip/StatusBadge/Timeline 等）
        ├── lib/                # queryClient 配置、queryKeys 注册表、时间/格式化、zod 公共 schema
        ├── hooks/              # 通用 hooks
        └── types/              # 角色/权限位等公共类型
```

### 2.2 模块边界规则（与 HLD ADR-0011 对应）

HLD §6.2 对后端 Python 包规定了「模块间只经内部 service 接口、禁止跨模块直查他域表、import 静态检查拦截（ADR-0011）」。前端采用同构纪律：

1. **依赖方向单向**：`app → widgets → features → shared`；反向 import 禁止。
2. **feature 间禁止横向 import**：`features/alerts` 不得 import `features/incidents` 的任何文件。跨域组合必须下沉 `shared/`（基础件）或上浮 `widgets/`（组合层）；跨域数据必须经各自 `api/` 发起，禁止跨 feature 调用对方的 Query hooks。
3. **feature 对外只暴露 `index.ts`**：内部文件被外部 import 视为边界违规。
4. **API 访问收口**：所有请求经 `shared/api` 客户端实例（含认证与错误规约），feature 的 `api/` 只定义本域 hooks 与 key 引用。
5. **强制手段**：eslint-plugin-boundaries（或 dependency-cruiser 进 CI）实现 import 静态检查，工具选型与后端 ADR-0011 同轮工程化评审 `[ASSUMPTION]`（验证方式：P0 工程化评审，规则并入 ADR-0011 或伴随 ADR 固化）。

### 2.3 视觉 token 与断点迁移（原型 → Tailwind）

- 原型 `#hp` 内的 CSS 变量集（表面/文字/品牌/状态色、间距 `--s1..--s6`、半径 `--r-s/m/l`、字体栈）是 design token 雏形；实现时将其映射为 Tailwind 主题的语义 CSS variables（shadcn/ui 约定的 `--background/--foreground/...` + 项目扩展 token），**色值不在本文重复**，以原型为视觉基准，最终以后续高保真设计规范文档定稿 `[TBD-UX]`（UX / P0 前端开发前）。
- 响应式断点以原型实际 media query 为准：`1024px`（统计卡/管道卡降两列、双栏网格降单列）、`820px`（侧栏收窄为图标态）；Tailwind `screens` 覆盖为 `md: 820px`、`lg: 1024px`，其余沿用默认。375px 级窄屏仅保证基本可用（内部 SRE 工具桌面优先 `[ASSUMPTION]`，验证方式：P0 末以真实使用设备抽样确认）。
- 原型中的 aria 标注（`role/aria-label/aria-current` 等）与 `prefers-reduced-motion` 行为在实现中必须保留。

## 3. 路由与权限设计

### 3.1 路由表

对齐交互文档 §4.1 八页面与领域文档 §3 权限矩阵；分期对齐交互文档 §5。

| 路由 | 页面（交互 §4.1） | 布局 | 可访问角色（领域 §3） | 分期 |
|---|---|---|---|---|
| `/login` | 登录（形态随认证 `[TBD-INFRA]`） | Blank | 公开 | P0 |
| `/` | 重定向 → `/alerts` | — | 已登录 | — |
| `/alerts` | 告警工作台 | AppShell | admin、sre、oncall_manager（只读）、developer（T 限本团队） | P0 |
| `/candidates` | 候选事件确认队列 | AppShell | admin、sre（确认/驳回仅此两者） | P2 |
| `/incidents` | 事件列表 | AppShell | admin、sre、oncall_manager（只读）、developer（T） | P2 |
| `/incidents/:incidentId` | 事件详情页 | AppShell | 同上（处置动作 admin/sre/developer(T)） | P2 |
| `/inspections` | 巡检看板 | AppShell | admin、sre、developer（T，认领） | P0 |
| `/ai/tasks` | AI 任务中心 | AppShell | admin、sre（审批限本团队 T） | P1 |
| `/workflows`、`/workflows/:workflowId` | Workflow 编辑器 | AppShell | admin、sre | P3 |
| `/oncall` | 排班管理 | AppShell | admin、oncall_manager（编辑）；sre 只读 `[ASSUMPTION]`（依据原型演示，生产是否开放待与业务确认 / P2 设计前） | P2 |
| `/admin` | 管理后台 | AppShell | admin | P0 |
| `/403`、`/404` | 错误页 | Blank | — | — |

路由级组件一律 `React.lazy` 动态加载（§6）；`workflows` 整域 P3 才合入构建。

### 3.2 守卫实现与权限边界

- **守卫链**：`RequireAuth`（会话存在）→ `RequireRole(roles)`（命中路由表角色）→ 不命中跳 `/403`。角色来自会话接口（`features/session`），随认证方式 `[TBD-INFRA]`（HLD §8.2）落地。
- **细粒度操作权限**：领域 §3 矩阵中的 T（限本团队）与动作级差异（如 oncall_manager 对告警只读、developer 无 AI 审批权）由 `shared/types` 定义权限位 + `can()` 工具函数控制按钮/入口渲染，映射表以领域 §3 为唯一事实源。
- **前端权限只做展示控制，后端权威**：菜单隐藏、按钮禁用、路由重定向均为 UX 优化；一切数据过滤（developer 团队边界）与写操作鉴权由 API 网关执行（HLD §1.3「两个人口，两套准入」与 §2 #2）。绕过前端直调 API 必须被后端拒绝，前端不承担安全职责。
- 角色切换器（原型顶栏 `#hp-role`）仅为演示交互的装置，生产实现不提供运行时切换角色 `[ASSUMPTION]`（验证方式：P0 会话详设时确认是否保留 admin 视角模拟功能）。

## 4. 数据流与服务端状态

### 4.1 API 客户端与类型生成流程

```text
后端 FastAPI（HLD §3.1，API-first）导出 openapi.json
  → 快照到 web/openapi.json（导出脚本随 04-api 治理定稿 [ASSUMPTION]）
  → npm run api:gen（openapi-typescript）→ src/shared/api/schema.d.ts（纯类型）
  → shared/api/client.ts：createClient<paths>（openapi-fetch）统一装配 baseURL / 认证 / 错误规约
  → 各 feature api/ 基于类型化 client 编写 Query hooks
```

- CI 校验 `openapi.json` 与后端当前 spec 的漂移，防类型与契约脱钩。
- 错误规约（错误 envelope、401 跳登录、4xx/5xx toast 分级）在 `shared/api` 统一实现；具体错误模型以 04-api spec 为准。
- 开发期经 Vite dev server 代理到 api 进程（同源，免 CORS 与 cookie 域问题）；生产构建产物由 api 部署单元直接提供（HLD §1.3 `[ASSUMPTION]`）。

### 4.2 TanStack Query 约定

- **key 注册表**：所有 queryKey 集中注册于 `shared/lib/query-keys.ts`（只有 key 工厂，不含请求逻辑），供 SSE 全局分发层（§4.3）与 feature hooks 共同引用。形如：

```ts
export const qk = {
  alerts: { list: (f: AlertFilters) => ['alerts', 'list', f] as const,
            detail: (id: string) => ['alerts', 'detail', id] as const },
  incidents: { list: (f) => ..., detail: (id) => ..., timeline: (id) => ... },
  candidates: { list: () => ... },
  findings: { list: (cluster: string) => ... },
  aiTasks: { list: () => ... },
  oncall: { schedule: (team) => ..., escalationPolicies: () => ... },
  // ...
} as const;
```

- **staleTime**：默认 30s（列表）/ 60s（管理后台配置类）；列表翻页/筛选切换使用 `placeholderData: keepPreviousData` 消除闪动。
- **mutation**：成功后按需 `invalidate` 对应 key；统一 `onError` toast；写操作提示中说明已留痕（BR-10 由后端落库，前端只做提示语）。
- **URL 即状态**：列表筛选（severity/status/搜索词）写入路由 search params（可分享、刷新可恢复），Query key 的 filters 部分直接取自 URL（§4.4）。

### 4.3 实时通道与 Query 缓存合并

通道协议（SSE vs WebSocket）`[TBD-FE]` 沿用 HLD §3.3（倾向 SSE，结论落地 ADR-0006），本文不擅自定案；以下设计**通道无关**，只依赖 `RealtimeClient` 抽象（§1.2.7）。

**合并策略矩阵**（事件名为示意，契约随 04-api 定稿 `[ASSUMPTION]`）：

| 实时事件 | 缓存处理 | 页面表现 |
|---|---|---|
| alert 新增 / 计数合并 / 状态变化 | `setQueryData(qk.alerts.list)` 精确 patch（避免整表 refetch） | 告警工作台行级更新、合并计数 ×N 变化、管道统计卡节流刷新 |
| candidate.created | `invalidateQueries(qk.candidates.list())` | 候选队列新增卡片 + 侧栏徽标 + toast（对应 L1「推送待确认提醒」） |
| incident.timeline.appended | `setQueryData(qk.incidents.timeline(id))` 追加（按事件 id 幂等去重 `[ASSUMPTION]`，随事件契约定） | 事件详情时间线实时追加（§5.2） |
| incident.status_changed | patch detail + 列表行 | 状态机步进条前移 |
| ai-task.status_changed | patch `qk.aiTasks.list()` 行 | pending_approval 高亮 + 徽标 + toast（对应 AI 审批流） |
| system.ai_circuit_state（NoAI 熔断，HLD §5.1） | 写 zustand 全局态 | 顶栏 `AiStatusBanner` 显著标识 |

- **合并函数必须是纯函数**（输入旧缓存 + 事件 → 新缓存），集中放 `shared/api/realtime/merge/`，是单测重点（§7.1）。
- **高频节流**：告警风暴时同 key 的多次 patch 以 rAF 合并 flush（§6）。
- **断连降级**：`RealtimeClient` 连接状态进 zustand；断连时对活跃列表 query 开启兜底轮询 `refetchInterval: 10s` `[ASSUMPTION]`（验证方式：P0 末弱网演练校准），恢复后停轮询。
- **pending_approval 轮询或推送**：AI 任务中心优先消费 `ai-task.status_changed` 推送；同时列表 query 的 `refetchInterval` 为动态函数——存在 pending_approval 任务时 5s、否则 30s `[ASSUMPTION]`（验证方式：P1 上线前按审批时效体验校准），页面不可见（`visibilitychange`）时暂停。推送与轮询并存，保证 `[TBD-FE]` 任一结局下审批时效有保障。

### 4.4 状态分层边界

| 状态类别 | 归属 | 例 |
|---|---|---|
| 服务端数据与副本 | TanStack Query（唯一来源，禁止复制进组件 state） | 告警列表、事件详情 |
| 可分享/可恢复的视图状态 | URL search params | 列表筛选、抽屉选中 id、tab |
| 全局客户端状态 | zustand（仅 3 类，§1.2.3） | 会话用户、NoAI 熔断态、实时连接态 |
| 局部 UI 状态 | 组件 useState / RHF | modal 开合、表单草稿 |

## 5. 关键页面实现要点

> 逐页对齐交互文档 §4.1；「API 资源」列为示意名（§4.1 声明），接口细节在 `04-api/`。

### 5.1 告警工作台（P0，重点页）

- **组件拆分**：`PipelineStatsCard`（①接入②去重③富化④关联四步计数卡，原型 `.pipe`）、`AlertsStatCards`（待处理/降噪率/P1P2 活跃/维护窗口抑制）、`AlertsFilterBar`（severity 分段器 + 状态下拉 + 搜索，全部入 URL）、`AlertsTable`（TanStack Table + Virtual，行内 fingerprint 截断展示、合并计数 ×N 徽标、降噪归因摘要）、`AlertDetailDrawer`（500px 右抽屉，5 个 tab：详情 / 原始 Payload / 富化字段 / AI 解释 / 关联事件）、`DedupAttributionPanel`（降噪归因：全同丢弃 / 部分合并 / 关联决策链路，展示方式 `[TBD-UX]` 沿用交互 §7）、`SuppressSuggestionModal`（抑制建议：三原因单选 + 补充说明，对应告警处置流）。
- **状态与数据**：列表/统计走 Query（key 含 URL filters）；抽屉选中 id 与当前 tab 入 URL；`NoAI` 降级时 AI 解释 tab 显示原始错误与人工排障入口（交互文档 §6，HLD §5.1）。
- **实时性**：SSE alert 事件精确 patch（§4.3 矩阵首行）；管道四步统计卡对高频计数做 rAF 节流；合并计数变化只在行内更新，不整表刷新。
- **关键操作**（告警处置流）：认领 Ack（升级链停止，BR-08）→ 转事件（创建后跳事件详情）或关闭 → 误报走抑制建议入降噪反馈池；全部为 mutation + invalidate。
- **API 资源（示意）**：`alerts`、`providers`（fingerprint_fields 来源展示）、`enrichment-rules`（富化字段命中归因）。

### 5.2 事件详情页（P2，重点页）

- **组件拆分**：`IncidentHeader`（severity/status/团队 + 状态机步进条 open→acknowledged→mitigated→resolved→closed，领域 §6 状态机）与「推进下一状态」主按钮（按当前状态切换文案：确认/止血/恢复/关闭）；`IncidentTimeline`（四类节点 auto/man/esc/ai 分色，原型 `.tl`；人工记录输入框提交追加）；`EscalationStatusCard`（升级链各级投递与 Ack 留痕展示，BR-08）；`StatusPageSyncCard`（同步状态 + 人工撤回，BR-06）；`RelatedAlertsCard`（点击回跳告警抽屉）；`AgentInvestigationButton`（P3，发起 A2）；`PostmortemPanel`（P1/P2 事件关闭时生成模板入口，时间线自动汇总，L3 链路）。
- **状态与数据**：`qk.incidents.detail/timeline` 两个 query 分离，时间线独立缓存利于增量追加。
- **实时性**：`incident.timeline.appended` SSE 追加（幂等去重）；状态变化 patch 步进条；页面滚动位置保持（追加在尾部，用户正在阅读不打断）。
- **API 资源（示意）**：`incidents/{id}`、`incidents/{id}/timeline`、`notification-records`、`status-page-entries`、`postmortems`、`ai-tasks`（P3 调查入口）。

### 5.3 候选事件确认队列（P2）

- **组件拆分**：`CandidateCard`（命中规则编号与描述、时间窗、相似度进度条、成员告警列表）、确认立项按钮（创建事件并跳详情）、`RejectModal`（三驳回原因：规则过宽 / 时间窗过长 / 富化字段错误——对应候选事件确认流，原因回流规则调优）。
- **状态与数据**：队列列表 Query；确认/驳回 mutation 成功后本地移除 + invalidate。
- **实时性**：`candidate.created` 推送 + 侧栏徽标 + toast（含跳转动作）；空队列态展示「所有候选已确认或驳回」。
- **API 资源（示意）**：`incident-candidates`、`correlation-rules`（规则详情引用）、`incidents`（确认立项写）。

### 5.4 巡检看板（P0）

- **组件拆分**：`ClusterSegmented`（集群切换，入 URL）、健康分与 findings 统计卡、`FindingsTrendChart`（recharts 堆叠柱状：近 7 次 run 的 warn+ / info）、`PolicyCard`（规则集、调度、`ai_explain_level`，BR-09）、`FindingsTable`（AI 解释行内展开：aibox 或「正在生成」或 NoAI 降级态；info 级禁用 AI 按钮并提示 BR-09）、行操作（认领 / 忽略 / 一键 AI 解释）。
- **状态与数据**：按集群分 key；AI 解释触发生成中态（乐观），完成后 patch 展开行。
- **实时性**：巡检为低频定时任务，run 完成 SSE 事件到达后 invalidate 即可，无秒级要求。
- **API 资源（示意）**：`findings`、`inspection-runs`、`inspection-policies`、`clusters`、`ai-explanations`。

### 5.5 AI 任务中心（P1，重点页）

- **组件拆分**：`BudgetStatCards`（本月调用 / token 消耗与月度预算占比 / 待审批数 / 本地模型占比，BR-12）、`AiTasksTable`（类型 explain/investigate/workflow_gen、模型、预算进度条（calls/tokens 双维度，BR-03）、状态机徽章——pending_approval 行高亮）、`ApprovalModal`（展示将要执行的工具与参数、预算已消耗、审批超时 30min 自动取消说明——对应 AI 审批流 BR-02/BR-05；批准/拒绝主次按钮）、`CallLogModal`（AICallLog 调用链表格，BR-10，不可删改提示）、`YamlDiffLink`（workflow_gen 任务跳转 Workflow diff 预览）。
- **状态与数据**：任务列表 + 预算统计两个 query；审批 mutation 后 patch 行状态。
- **实时性**：`ai-task.status_changed` 推送 + 动态轮询兜底（§4.3）；新 pending_approval 到达 toast 带「前往审批」动作（对应交互文档 §4.2）。
- **API 资源（示意）**：`ai-tasks`、`ai-call-logs`、AI 预算统计资源。

### 5.6 Workflow 编辑器（P3，重点页）

- **组件拆分**：`WorkflowListTable`（版本、来源 manual/ai_generated + approved_by、触发类型、执行统计）、`YamlEditor`（Monaco 动态加载 + monaco-yaml schema 校验）、`VersionHistory`、`DiffPreview`（Monaco DiffEditor 双栏 diff；操作按钮：确认入库（BR-05）/「需要修改」回 AI 再生成——A3 回环）、`NlGenerateModal`（自然语言描述 → 生成草稿 → 自动进 diff 预览）、`WorkflowRunList`（状态机含 waiting_approval，领域 §6）。
- **状态与数据**：编辑器内容为本地草稿态（RHF/zod 或组件 state），保存才提交；diff 基于「当前版本 vs 草稿」双版本拉取。
- **实时性**：执行记录低频轮询或 run 状态推送；无秒级要求。
- **加载策略**：整页路由级 lazy + Monaco 二级动态 import（首次进入编辑器才加载，独立 chunk，§6）。
- **API 资源（示意）**：`workflows`、`workflows/{id}/versions`、`workflow-runs`、A3 生成任务复用 `ai-tasks`。

### 5.7 排班管理（P2）

- **组件拆分**：`WeekCalendar`（7 日主/备班网格，**自实现轻量周视图**——原型即 7 列 grid，不引入重型日历库 `[ASSUMPTION]`（验证方式：P2 排班详设若需月视图/拖拽再评估）、`RotationRulesPanel`（轮换规则编辑）、`OverrideEditor`（临时顶班记录）、`EscalationPolicyTable`（级别/目标渠道/超时，默认值 `[TBD-BIZ]` 沿用交互 §7，业务负责人 / P2 设计前）。
- **状态与数据**：表单走 RHF；保存 mutation + invalidate。
- **实时性**：无实时要求（排班变更低频）。
- **API 资源（示意）**：`oncall-schedules`、`escalation-policies`。

### 5.8 管理后台（P0）

- **组件拆分**：卡片网格——`ClustersCard`（集群状态、K8s 版本；**凭证只显示 secret_ref 引用与轮换信息，永不回显凭证值**，安全红线 + HLD §4.3）、`ProvidersCard`（type/category/pull_mode/fingerprint_fields）、`InspectionRulesCard`（规则库统计、k8s_version_fit 适配、来源回流）、`UsersRolesCard`（用户与角色管理，领域 §3）、`AiBudgetCard`（默认预算 BR-03、模型路由本地优先 BR-12、出域开关 `[TBD-BIZ]`）。
- **状态与数据**：各卡独立 query，懒渲染（进入视口再请求）；配置表单 RHF + zod。
- **实时性**：集群连接状态变化（探活，HLD §5.4）推送更新 `ClustersCard` 状态徽标。
- **API 资源（示意）**：`clusters`、`credentials`（仅引用元数据）、`providers`、`inspection-rules`、`users`、`roles`、AI 配置资源。

## 6. 性能预算与优化

预算数值均为工程设定 `[ASSUMPTION]`（验证方式：P0 末以真实部署环境与 Lighthouse CI / 构建产物分析校准后回填，对齐 HLD §4.2 做法）：

| 指标 | 预算 | 测量方式 |
|---|---|---|
| 首屏路由 JS（gzip，`/alerts` chunk + 公共 chunk） | ≤ 300KB | `vite-bundle-visualizer` + Lighthouse |
| LCP（内网环境） | ≤ 2.5s | Lighthouse CI |
| 单个路由 chunk（gzip） | ≤ 500KB（Monaco chunk 例外，P3 动态加载） | 构建产物分析 |
| 告警列表渲染 | ≤ 100 行普通渲染；超过启用 TanStack Virtual（窗口约 20 行） | 代码约定 + 大数据集手测 |
| 图表 / 统计卡重绘 | SSE 更新 rAF 合并 flush（≥ 1 帧间隔）；resize debounce 200ms | 性能手测 |

优化手段：

- **路由级代码分割**：全部路由 `React.lazy`；`workflows` 域 P3 合入。
- **二级动态加载**：Monaco 编辑器/DiffEditor、图表组件（recharts）首次使用时加载，独立 chunk。
- **列表行 `memo`**：行组件 props 稳定（行数据 + 权限位），配合精确 patch 只重渲染变化行。
- **SSE 合并纯函数 + rAF 批处理**（§4.3），告警风暴时避免渲染抖动。
- **字体**：Inter self-host 子集化（woff2 + `font-display: swap`）；中文字体走系统栈（原型同款策略），不引入中文 webfont 大文件。
- **尊重 `prefers-reduced-motion`**（原型已实现，动画全部关闭）。

## 7. 测试策略

### 7.1 单元与组件测试（Vitest + Testing Library）

- **纯函数单测（重点）**：SSE 合并函数（§4.3，含幂等/乱序/风暴批处理）、`can()` 权限位映射（领域 §3 矩阵全组合）、降噪归因文本组装、预算进度计算、query key 工厂稳定性。
- **组件测试**：`RequireRole` 守卫渲染与重定向；告警表格行按角色渲染/隐藏操作按钮；候选驳回表单校验与提交；AI 审批 Modal 的工具/预算/超时信息完整性（对应 AI 审批流）；NoAI Banner 出现条件；基础 a11y 断言（role / aria-label，对齐原型标注）。
- **Renderer**：jsdom 为主，无视觉回归（视觉以高保真规范文档验收为准，§2.3）。

### 7.2 E2E 测试（Playwright，范围锁定）

**只覆盖交互文档 §4.2 的三条关键操作流**，不做全页面巡检：

1. **告警处置流**：告警列表点入详情 → 查看 AI 解释（含 NoAI 降级分支）→ 认领 Ack → 转事件（断言跳转与立项）/ 直接关闭 → 误报标记抑制建议（断言原因提交）。
2. **候选事件确认流**：候选卡片 → 确认立项（断言事件创建与成员告警关联）/ 驳回三原因（断言原因提交）。
3. **AI 审批流**：AI 任务中心 pending_approval → 审批 Modal 展示工具与预算 → 批准（任务继续）/ 拒绝（任务终止）。

运行形态：Compose 起 api 进程 + seed fixture 数据 + `vite preview` 构建产物 `[ASSUMPTION]`（验证方式：P0 工程化时定 E2E 基座；dev server 模式为备选）。

### 7.3 覆盖原则

以 §7.1 清单与 §7.2 三条流的覆盖为准，**不设行覆盖率门禁**（单人项目维护成本优先 `[ASSUMPTION]`，验证方式：P0 末随测试基建落地复核）；E2E 失败即阻塞合入。

## 8. 工程化约定

### 8.1 代码质量

- **TypeScript 严格模式**：`strict: true` + `noUncheckedIndexedAccess` + `noImplicitOverride`；`moduleResolution: bundler`。
- **ESLint**（flat config）：typescript-eslint（strict-type-checked）+ react-hooks + **eslint-plugin-boundaries**（§2.2 模块边界静态检查，对应 ADR-0011）。
- **Prettier** 负责格式化，与 ESLint 职责分离；CI 执行 `lint + typecheck + test` 全绿才可合入（沿用仓库规则：禁止 `--no-verify`）。
- Node 版本经 `engines` 字段固化，具体版本 `[TBD-INFRA]`（ADR-0008 同轮锁定）。

### 8.2 npm scripts 约定

| 脚本 | 作用 |
|---|---|
| `npm run dev` | Vite dev server（proxy → api 进程） |
| `npm run build` | `tsc -b && vite build`（产物交 api 静态服务，HLD §1.3） |
| `npm run preview` | 本地预览构建产物 |
| `npm run lint` / `lint:fix` | ESLint（含模块边界规则） |
| `npm run typecheck` | tsc 全量类型检查 |
| `npm run test` / `test:watch` | Vitest 单测与组件测试 |
| `npm run test:e2e` | Playwright 三条流 |
| `npm run api:gen` | openapi.json → schema.d.ts 类型生成（§4.1） |
| `npm run format` / `format:check` | Prettier |

### 8.3 环境变量与安全

- 环境变量仅允许 `VITE_` 前缀进入前端；当前仅规划 `VITE_API_BASE_URL`（默认同源 `/api/v1` `[ASSUMPTION]`，随 04-api 定稿）。开发代理目标端口经 Vite config 读取本地配置 `[ASSUMPTION]`（验证方式：P0 工程化与部署端口一起定）。
- **禁止任何密钥进入 `VITE_*` 或前端代码**：构建产物对用户完全可读；模型密钥、集群凭证、Provider token 只存在后端，前端一切模型相关操作经 API → AI 网关（HLD §1.3「唯一出域出口」）。
- `.env*` 全部 gitignore（提交 `.env.example` 占位）；仓库 secret_scan + pre-commit 拦截（项目安全红线）。

## 9. 开放问题

| 标记 | 问题 | 确认人 / 阶段 |
|---|---|---|
| `[TBD-FE]` | 实时通道 SSE vs WebSocket（沿用 HLD §3.3 / 交互 §7；本文倾向 SSE 但封装通道无关，结论落 ADR-0006） | 前端 / P0 技术设计 |
| `[TBD-INFRA]` | 前端依赖与 Node 版本锁定清单（package-lock.json + engines，ADR-0008） | 基础设施负责人 / P0 工程化 |
| `[TBD-INFRA]` | 认证方式（SSO/LDAP/本地）——决定登录页形态、SSE 认证手段（cookie vs header，§1.2.7）与角色获取接口 | 基础设施负责人 / P0 部署设计（HLD §8.2 已登记） |
| `[TBD-UX]` | 告警工作台信息密度与降噪归因展示方式（沿用交互 §7） | UX / P0 前端开发前 |
| `[TBD-UX]` | developer 角色团队隔离的数据边界展示（沿用领域 §9） | UX / P2 前端设计前 |
| `[TBD-BIZ]` | 升级链各级默认超时与渠道（排班页展示依赖，沿用交互 §7） | 业务负责人 / P2 设计前 |
| `[ASSUMPTION]` | 性能预算数值（§6）、SSE 事件命名与幂等键（§4.3）、轮询间隔（§4.3）、API 资源名示意（§4.1）、`web/` 目录名（§2.1）、排班周视图自实现（§5.7）、sre 排班只读开放（§3.1）、E2E 基座形态（§7.2）、边界 lint 工具（§2.2） | 验证方式均见各节标注，随 P0 工程化与 04-api 定稿收敛 |
| — | recharts 重评（大数据图表出现时换 ECharts）、Monaco 重评（构建/体积问题时换 CodeMirror 6） | 前端 / 触发条件出现时（P3 前） |
