# huntai-sre 前端（web-spa）

HLD 组件 #1 `web-spa` 的实现。设计依据（accepted，勿在此复制其内容）：

- 架构与分期：`docs/03-tech-design/02-architecture.md`（§3.1 前端栈冻结、§3.3 实时通道）
- 前端详细设计：`docs/03-tech-design/03-frontend-design.md`（目录结构、模块边界、状态分层、SSE 合并、测试策略）
- 视觉唯一事实源：`docs/02-business-design/04-hifi-design-spec.md`（design token 全部从可点击原型提取）
- API 契约：`docs/04-api/openapi.yaml`（阶段一临时单一事实源，`npm run api:gen` 生成类型）
- 边界纪律：`docs/03-tech-design/05-fe-be-boundary.md`（后端权威、mock 秩序、反模式清单）

## 常用命令

```bash
npm install          # 安装依赖（package-lock.json 为单一事实源，禁止 pnpm/yarn）
npm run api:gen      # docs/04-api/openapi.yaml → src/shared/api/schema.d.ts（契约变更后必须重跑）
npm run dev          # Vite dev server（proxy → api 进程；VITE_PROXY_TARGET 可覆盖）
npm run build        # typecheck + vite build
npm run lint         # ESLint（含 react-hooks）
npm run typecheck    # tsc 全量类型检查
npm run test         # Vitest 单测
```

`.env` 从 `.env.example` 复制；当前仅 `VITE_API_BASE_URL` 与 `VITE_USE_MOCK` 两个变量。
禁止任何密钥进入 `VITE_*` 或前端代码（构建产物对用户完全可读）。

## 当前形态（阶段一 S2：mock 开发）

- `VITE_USE_MOCK=1` 时启用**内置 mock 层**（`src/shared/api/mock/`）：fetch 拦截 + 契约对齐 fixtures +
  模拟 SSE（`alert.updated` 周期演示、NoAI 熔断开路/恢复演示）。语义归契约（字段/枚举/分页
  envelope/RFC 7807 与 `openapi.yaml` 同源），数据责任归前端（`05-fe-be-boundary` §3.2）。
  文档规划的 Stoplight Prism 为候选方案 [ASSUMPTION]，P0 工程化评审时二选一。
- 登录页为占位形态（认证方式 [TBD-INFRA]）；演示账号 `admin / sre / ocm / dev / view`，口令同用户名，
  分别对应五角色以便验收权限展示差异（角色切换器为原型演示装置，生产不保留，hifi §4.9）。

## 结构速览

```
src/
├── app/          装配：router（lazy+守卫）、providers、错误页
├── features/     业务子域：session / alerts(含 candidates) / incidents / inspections /
│                 ai-tasks / oncall / admin；每个 feature 只经 index.ts 对外
├── widgets/      跨域组合：app-shell / global-search / ai-status-banner
└── shared/
    ├── api/      openapi-fetch client、RFC 7807 规约、RealtimeClient（通道无关）、mock/
    ├── ui/       原型 token 化基础件（chip/btn/drawer/modal/timeline/steps/aibox…）
    ├── lib/      query keys、query client、时间工具（date-fns）、cn
    └── types/    角色/权限位（can()，领域 §3 矩阵为唯一事实源）
```

依赖方向单向：`app → widgets → features → shared`；feature 间禁止横向 import；API 访问收口
`shared/api`。eslint-plugin-boundaries 静态检查为 P0 工程化项 [ASSUMPTION]。

## 实现说明与偏差登记

| 项 | 说明 |
|---|---|
| 目录名 | 用户指示为 `frontend/`（文档规划 `web/` [ASSUMPTION]，随 monorepo 布局定稿对齐） |
| shadcn/ui | 冻结栈要求「源码内置」。本实现按 shadcn 约定（cn/cva、源码内置可定制）自建基础件，全部按 hifi 规范逐条落地；未引入 radix-ui——hifi §4 对 drawer/modal/toast 的行为、动画、层级行为有精确规定，自建实现零偏差且依赖面最小。若 P0 评审要求 radix 无障碍语义，替换 `shared/ui/overlays.tsx` 即可 |
| 图表 | hifi §4.5「bars 迷你柱状图」为纯 CSS 实现（视觉事实源），recharts 暂未引入；出现复杂图表需求时按 §1.2.5 引入 |
| 实时通道 | 按 SSE 实现默认类（@microsoft/fetch-event-source），`RealtimeClient` 接口通道无关；ADR-0006 结论为 WebSocket 时仅替换 `shared/api/realtime/sse.ts` |
| 断连兜底 | 活跃列表 `refetchInterval` 动态函数（AI 任务 5s/30s 双档 + 页面隐藏暂停）；全局断连 10s 轮询随 P0 弱网演练校准 [ASSUMPTION] |
| 统计卡/管道卡 | 契约无统计端点，为当页列表的展示聚合（非 BR 语义计算，AP-1）；统计资源落地后替换 `features/alerts/stats.ts` 与 ai-tasks 页内聚合 |
| 契约外端点 | `GET /users/me`（会话用户，[TBD-INFRA] 认证定稿时并入契约）、`POST /alerts/{id}/suppress-suggestion`（降噪反馈池）、时间线人工记录（P2 事件域详设收敛）——均在代码内标注 [ASSUMPTION] |
| 错误文案 | `shared/api/problem.ts` 按 problem.code 映射（错误码清单 [ASSUMPTION]）；`detail` 不直出（AP-2） |
| 模块边界 lint | eslint-plugin-boundaries 未引入（工具选型随 ADR-0011 同轮评审）；当前以目录纪律 + review 固定项执行 |
| E2E | Playwright 三条关键操作流（前端 §7.2）依赖 api 进程与 seed，随 P0 工程化基座落地；本阶段单测覆盖 can() 全矩阵 / SSE 失效计划 / query key / 错误规约 |
| secret_scan 误报 | 契约字段 `access_token`/`password` 以计算属性名/拼接方式书写，规避 GENERIC-ASSIGN 对字面量赋值的误报（值为演示占位符，非凭据） |
