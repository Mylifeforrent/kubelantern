# 高保真设计规范（Hi-Fi Design Spec）

| 元信息 | |
|---|---|
| 状态 | accepted |
| 日期 | 2026-10-24 |
| 依据 | `02-business-design/03-clickable-prototype.html`（可点击原型 v0.1，1039 行，视觉唯一提取基准）、`02-interaction-flows.md` §4（页面与操作流）、`03-tech-design/03-frontend-design.md`（§2.3 token 迁移机制与断点结论、§6 性能预算——本文引用不复制） |
| 读者 | 前端、UX |

> 本文把原型中隐含的设计系统**显式化、规范化**：所有 token 值均从原型源码逐行提取（`:root` 变量、散落样式、JS 内联样式、media query、keyframes），**禁止发明原型中不存在的值**；凡属本文的规范化建议（归并、收敛、命名）均单独标注「实现建议」。原型宣称但未实现的能力（如 tooltip、更多断点）如实标注并归入 §6。本文是前端实现的视觉单一事实源；与 `03-frontend-design.md` 的分工：那边定**机制**（token 如何迁入 Tailwind、断点取值），这边定**值与布局**。

---

## 1. Design Token 总表

### 1.1 色彩

#### 1.1.1 表面与边框（`:root` 5 项）

| Token | 值 | 原型注释/用途 |
|---|---|---|
| `--bg` | `#f4f6f7` | white-30 画布（近白，衬托纯白卡片）；`html,body` 背景同值 |
| `--surface` | `#fefeff` | white-10 卡片 / 侧栏 / 顶栏 / 抽屉 / 弹窗 / toast 底 |
| `--surface-2` | `#f4f6f7` | hover 填充（nav、默认按钮底、seg 激活态环境） |
| `--surface-3` | `#e8edf0` | white-40 常规边框 / 交替底 / 激活态底（tag 默认底、开关轨、步进条轨道） |
| `--raise` | `#d8dcdf` | white-60 强边框（默认按钮边框、modal 边框、次级 hover 边框） |

**分层原则（实测归纳）**：画布 `--bg` 之上一层纯白 `--surface`，卡片靠 1px `--surface-3` 边框分层而非阴影（§1.5）；`--raise` 只用于可交互件（按钮/弹窗）边框。

#### 1.1.2 文字层级（`:root` 5 项）

| Token | 值 | 原型注释/用途 |
|---|---|---|
| `--tx-hi` | `#191a1e` | black-20 标题（h1、卡片头、表格主标题、toast 标题、数值） |
| `--tx` | `#222325` | black-30 正文 |
| `--tx-2` | `#5a5a5b` | black-50 次要文字（原型注释 ≈7:1）；副标题、说明、图标默认色 |
| `--tx-3` | `#6e6e71` | 三级文字（nav 未激活、rulebox、tag 默认） |
| `--tx-dim` | `#6e6e71` | 弱化文字（白底 ≥4.5:1）；表头、空态、时间线时间戳、徽标组标题 |

> `--tx-3` 与 `--tx-dim` 同值 `#6e6e71`，是两个语义位共用一值，实现建议保留双语义位（实现建议）。

#### 1.1.3 品牌色（`:root` 4 项）

| Token | 值 | 原型注释/用途 |
|---|---|---|
| `--brand` | `#c53520` | brand-20 主按钮底（白字 ≈4.9:1）、侧栏徽标、pip 角标、链接色变量 |
| `--brand-h` | `#a51e16` | brand-10 hover（亮色底用**加深而非提亮**） |
| `--brand-t` | `#c53520` | 品牌文字（P2 severity 文字、激活 nav 图标、tag.br 文字） |
| `--brand-w` | `#93551c` | 琥珀强调（源自站点 #93551c）；stat 警示数值、步进条当前标签 |

#### 1.1.4 语义状态色（`:root` 9 项；`-t` 为文字变体）

| Token | 值 | 文字变体值 | 用途 |
|---|---|---|---|
| `--red` / `--red-t` | `#c40f3a` | `#c40f3a`（同值） | P1 严重、失败、failed、删除行 diff、危险按钮 |
| `--green` / `--green-t` | `#0a8a54` | `#0a8a54`（同值） | 成功、已恢复、dot-ok、时间线人工节点、新增行 diff |
| `--teal` / `--teal-t` | `#0779a4` | `#0779a4`（同值） | 已通知/已确认态、链接 `a`、toast 默认边条、时间线 auto 节点 |
| `--purple` / `--purple-t` | `#9009e4` | `#8b12d6`（**加深变体**） | AI 语义专属（AI chip、aibox、审批、时间线 ai 节点 + 辉光）、焦点环 |
| `--gold` | `#93551c` | （与 `--brand-w` 同值） | P3 中、已止血、warning toast 边条 |

> 原型总注释（line 18-19）：状态色在白底上按**同色相加深**至正文对比度 ≥4.5:1；唯 `--purple-t` 相对 `--purple` 再加深一档。语义色**专色专用**：purple 只给 AI，teal 只给「已通知/确认/链接」，red 只给「严重/失败/危险」。

#### 1.1.5 语义 alpha 调色族（散落于组件样式，14 族；chip/tag/AI 框的背景与边框由此派生）

| 色族（RGB） | 出现的 alpha 值 | 用途 |
|---|---|---|
| brand `197,53,32` | `.12` `.13` `.18` `.25` `.40` | sev-p2 chip 底/边、tag.br 底、::selection 底、logo 阴影、pstep 激活阴影 |
| red `255,31,71` | `.08` `.10` `.16` `.35` `.40` | btn-d 三态、sev-p1/st-open chip、diff 删除行底 |
| gold `242,204,96` | `.08` `.12` `.30` | sev-p3/st-mit chip、tag.gd 底 |
| teal `0,209,255` | `.07` `.08` `.25` `.28` | sev-p4/st-notified/st-ack chip、env 徽标 |
| purple `178,54,255` | `.04` `.05` `.06` `.10` `.15` `.18` `.2` `.22` `.30` `.35` `.45` | AI 全场景：st-corr/st-cand/ai-chip、btn-ai、tag.pu、rulebox、simbar 轨道、aibox、pending 行高亮、findings 展开行 |
| purple 辉光 `144,9,228` | `.35` | 时间线 ai 节点圆点 glow |
| green `9,228,136` | `.08` `.09` `.32` | st-res/ok-chip、diff 新增行底 |
| green 辉光 `10,138,84` | `.40` | side-foot dot-ok glow |
| 行分隔灰 `34,35,37` | `.12` | td 底边、候选成员行分隔 |
| hover 灰 `25,26,30` | `.045` | 可点击表格行 hover |
| 中性灰 `128,128,131` | `.10` `.30` | st-supp/st-closed chip |
| 浮层阴影灰 `16,17,18` | `.12` `.18` `.25` | toast/modal 阴影、开关圆钮阴影 |
| scrim 灰 `22,23,25` | `.38`（+ `backdrop-filter:blur(2px)`） | 抽屉/弹窗遮罩 |
| 巡检 info 柱 `7,121,164` | `.45` | 趋势图 info 级柱 |

**派生规则（实测归纳）**：chip/tag 一律「10%~±3% 透明度底 + 30%~±5% 同色边框 + 对应 `-t` 文字色」；AI 系背景 alpha 统一偏低（.04~.10）以弱化大面积紫。

#### 1.1.6 散落硬编码色（token 体系外，实现时归一——归一目标为实现建议）

| 值 | 位置 | 归一建议 |
|---|---|---|
| `#e6522c` / `#8f1e12` | logo-mark 渐变端点（`#c53520 55%` 中段） | 收敛为品牌渐变 token |
| `#49023a` / `#992a6c` / `#f6c6d5` | 头像渐变底 ×2、头像字色 | 收敛为头像专用 token |
| `#c9cdd1` | 滚动条 thumb | 归入边框族 |
| `#e4e8eb` | toast 边框（唯一处，与 `--surface-3` 相近） | 归一至 `--surface-3`（实现建议） |
| `#f6f8fa` / `#2f3134` | `pre.code` 底/字色 | 收敛为代码块 token |
| `#fff` | 主按钮字、徽标字、开关圆钮等 | 即 `primary-foreground` 位 |

#### 1.1.7 对比度承诺（照抄原型注释）

原型注释声称：状态文字色同色相加深至**正文对比度 ≥4.5:1**；`--tx-2` ≈7:1；主按钮白字 ≈4.9:1；弱化文字 ≥4.5:1。以上数值**未独立计算验证** `[ASSUMPTION]`（前端 / P0 实装时以对比度工具逐对复核，不达标即在此登记偏差）。

### 1.2 圆角

| Token / 值 | 使用场景 |
|---|---|
| `--r-s: 8px` | 按钮、输入框、nav 项、分段器、图标钮容器、卡片内小框（rulebox）、周历日格、链接列表项、代码块 |
| `--r-m: 12px` | 卡片、统计卡、管道步骤卡、aibox |
| `--r-l: 14px` | 弹窗、原型外框 |
| 组件级固定值（实测） | chip `5px`；tag / focus 环 / toast 圆钮焦点 `4px`；ibtn / seg 内钮 / 滚动条 `6px`；bdg / logo-mark `9px`；switch / toast `10px`；pip `7px`；simbar / 步进条 `2px`；趋势柱顶角 `3px 3px 0 0`；头像 / 状态点 `50%`（圆） |

### 1.3 字体、字号与行高

**字体栈（`:root` 2 项）**：

- `--font: 'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif`（Inter 经 Google Fonts 引入，400/500/600/700 四字重）
- `--mono: ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace`

**全局基线**：`font: 400 14px/1.55 var(--font)`。

**字号阶梯（实测 14 档，含使用场景）**：

| 档 | 使用场景 |
|---|---|
| 22px | 统计卡数值 `.stat .v`（600 字重、tabular-nums、-.3px 字距） |
| 17px | 页面 h1、管道步骤卡数值 |
| 15px | 弹窗标题 h3 |
| 14.5px | 侧栏产品名 |
| 14px | 正文基线、抽屉告警标题 |
| 13.5px | 侧栏 nav 项 |
| 13px | 表格正文、卡片头、弹窗正文、空态、atitle |
| 12.5px | 按钮、页头副标题、tabs、kv、aibox、toast、时间线正文、候选成员行、链接列表、日历人名、输入框、角色切换器 |
| 12px | mono 标签、分段器按钮、toast 动作链接、NL 输入 textarea、事件 ID |
| 11.5px | `.tiny` 通用小字、统计卡标签/说明、小按钮、env 徽标、代码块 |
| 11px | 表格副标题 asub、时间线时间戳、日格星期、侧栏脚、头像字、管道步骤标签/说明、aibox 脚注 |
| 10.5px | 分组标题 navgrp、侧栏徽标、产品名副行、表头 th、步进条标签、日格备班行 |
| 10px | tag、趋势图柱标签 |
| 9.5px | 铃铛 pip 角标 |

**行高（显式声明仅 3 处）**：全局 `1.55`；`pre.code` `1.6`；侧栏产品副行 `1.2`；其余继承。**字重**：400 默认；500（按钮、chip、表头、atitle）；600（h1、卡片头、统计卡数值、弹窗标题、徽标、aibox 头、日历人名、toast 标题）；700（pip 角标）。

### 1.4 间距阶梯

| Token | 值 | 典型用途 |
|---|---|---|
| `--s1` | 4px | 微间距（chip 内 dot 与文字、进度条上边距） |
| `--s2` | 8px | 行内元素 gap（按钮组、卡片头图标 gap、toast 组间距） |
| `--s3` | 12px | 紧凑 gap（stats/pipe 网格列距、卡片头上下 padding 12px 16px） |
| `--s4` | 16px | 区块间距（页头下边距、grid2 列距、卡片头左右 padding） |
| `--s5` | 24px | 内容区左右 padding、区块下边距 |
| `--s6` | 32px | 内容区底部 padding |

原型注释自称「密度 8/10 间距节奏」；**实测辅助值**（token 外）：`5/6/7/9/10/13/14/18/20/36`（10px 高频用于行内 gap 与卡片内 padding；36px 为空态 padding）。实现建议：辅助值就近收敛到 4px 基数刻度（10→8 或 12、13→12、14→16、18→16、20→24），收敛以视觉走查验收 `[ASSUMPTION]`（前端 / P0 实装时校准）。

### 1.5 阴影与 Elevation（实测 9 处；**卡片无阴影**是硬规则）

| 阴影 | 位置 |
|---|---|
| `0 2px 8px rgba(197,53,32,.25)` | logo-mark（品牌色阴影） |
| `0 0 0 1px var(--brand), 0 2px 10px rgba(197,53,32,.12)` | 管道步骤卡激活态 / 今日日格外框 |
| `inset 2.5px 0 0 var(--brand)` | nav 激活态**左侧指示条**（内阴影实现） |
| `0 0 6px rgba(144,9,228,.35)` | 时间线 ai 节点圆点辉光 |
| `0 0 5px rgba(10,138,84,.4)` | 侧栏脚在线状态点辉光 |
| `0 24px 70px rgba(16,17,18,.18)` | modal |
| `0 10px 30px rgba(16,17,18,.12)` | toast |
| `0 1px 2px rgba(16,17,18,.25)` | 开关圆钮 |

分层规则：静态表面（卡片/表格/侧栏）= 边框、零阴影；阴影只用于**浮层**（modal/toast）与**状态强调**（激活/在线/AI）。

### 1.6 图标体系

内联 SVG `<symbol>` 共 **27 个**，其中 **25 个在用、2 个已定义未使用**（`i-filter`、`i-refresh`，实现可暂缓）。绘制规范：viewBox `0 0 24 24`、`stroke: currentColor`、`fill: none`、`stroke-width: 1.8`（logo 内 2）、round cap/join；默认尺寸 16×16（`.ic`），嵌套缩放 17/14/13/12/11px。

| 图标 | 语义用法 |
|---|---|
| `i-eye2` | 品牌.logo-mark |
| `i-siren` | 告警工作台（nav + 统计卡） |
| `i-layers` | 候选事件 |
| `i-zap` | 事件响应、关联事件入口 |
| `i-cal` | 排班与升级 |
| `i-radar` | 巡检看板、巡检规则库 |
| `i-spark` | AI 全场景（解释/任务/生成/审批） |
| `i-branch` | Workflow 编排 |
| `i-gear` | 管理后台 |
| `i-search` | 全局搜索 |
| `i-bell` | 通知铃、值班与升级卡 |
| `i-x` | 关闭、抑制建议、驳回 |
| `i-check` | 确认、Ack、成功 |
| `i-warn` | 警告、NoAI 降级、失败 |
| `i-shield` | 脱敏（BR-01 提示）、维护窗口、env 徽标 |
| `i-clock` | 时间、预算、超时 |
| `i-chl` / `i-chr` | 返回 / 前进、行内下级箭头 |
| `i-arr` | 转事件、toast 动作链接 |
| `i-file` | YAML / diff |
| `i-term` | 调用链（AICallLog） |
| `i-inbox` | 接入、降噪归因框 |
| `i-plus` | 添加处理记录 |
| `i-user` | 用户、角色切换器 |
| `i-link` | 关联、Provider |
| `i-filter` / `i-refresh` | **已定义未使用** |

### 1.7 微排版

- **字距**：logo `.2px`、h1 `.1px`、统计卡数值 `-.3px`、分组标题 `.14em`、表头 `.1em`、tag `.05em`；分组标题与表头另加 `text-transform: uppercase`。
- **数字**：`font-variant-numeric: tabular-nums` 应用于全部数值位（统计卡数值、管道数值、徽标、`.num` 工具类）。

### 1.8 Tailwind 映射表（机制引用 `03-frontend-design.md` §2.3：语义 CSS variables，shadcn/ui 约定 + 项目扩展）

| 原型 token | 承接变量（shadcn 标准位） | Tailwind 用法 | 备注 |
|---|---|---|---|
| `--bg` | `--background` | `bg-background` | |
| `--surface` | `--card` | `bg-card` | 侧栏/顶栏/浮层同用 |
| `--surface-2` | `--muted` | `bg-muted` | hover 填充 |
| `--surface-3` | `--border` | `border-border` | |
| `--raise` | 扩展 `--border-strong` | `border-border-strong` | 项目扩展位 |
| `--tx-hi` / `--tx` | `--foreground` | `text-foreground` | 两值相近（#191a1e / #222325），实现建议合并为一个前景位 `[ASSUMPTION]`（前端 / P0 实装校准） |
| `--tx-2` / `--tx-3` / `--tx-dim` | `--muted-foreground` + 扩展档 | `text-muted-foreground` 等 | 三档两值（#5a5a5b / #6e6e71），实现建议保留两档 |
| `--brand` / `#fff` 字 | `--primary` / `--primary-foreground` | `bg-primary text-primary-foreground` | |
| `--brand-h` | 扩展 `--primary-hover` | hover 态 | 亮色 hover 加深原则 |
| `--brand-t` | 扩展 `--primary-text` 或就近用 `--primary` | | |
| `--red(-t)` | `--destructive` | `text-destructive` 等 | |
| `--green(-t)` | 扩展 `--success` | | |
| `--teal(-t)` | 扩展 `--info` | | 链接色亦取此位 |
| `--purple(-t)` | 扩展 `--ai` | | AI 语义专属位 |
| `--gold` / `--brand-w` | 扩展 `--warning` | | 两 token 同值，实现建议合一 `[ASSUMPTION]` |
| alpha 调色族（§1.1.5） | 以 `color-mix` 或派生变量（如 `--ai-soft`）挂到对应语义位 | `bg-ai-soft` 等 | 派生规则见 §1.1.5 |
| `--s1..s6` | spacing 刻度 `1/2/3/4/6/8` | `p-1`…`p-8` | 4px 基数精确命中 |
| `--r-s/m/l` | 扩展 `--radius-sm/md/lg` | `rounded-md` 等 | |
| 字号 14 档 | 扩展 `fontSize` 主题项，**按原型精确值登记**，不硬套默认刻度 | `text-stat-v`（22px）等命名实现建议 | 命名以 P0 实装为准 `[ASSUMPTION]` |

具体变量命名以 P0 shadcn CLI 初始化产出为准 `[ASSUMPTION]`（前端 / P0 前端开发前），本文约束的是**值与语义位**。

## 2. 全局布局系统

### 2.1 应用骨架

```text
┌──────────────┬──────────────────────────────────────────┐
│ aside.side   │ header.topbar（52px，surface 底，下边框）   │
│ 228px 固定    ├──────────────────────────────────────────┤
│ surface 底    │ main.content（唯一滚动区）                  │
│ 右边框        │   padding: 24px 24px 32px                 │
│ 纵向 flex     │                                           │
└──────────────┴──────────────────────────────────────────┘
```

双栏 flex：`side` 固定 228px 不滚动（内容多时自身纵排）；`main` 纵向（topbar 52px 固定 + content `overflow-y: auto`）。原型演示容器高 900px、外框 1px `--surface-3` + `--r-l`；整页形态（原型末行样式）为 `100vh` 无外框、`html,body` 背景 `#f4f6f7`。**z-index 层级**：内容区默认 < scrim `40` < drawer/modal `41` < toasts `60`。

### 2.2 侧栏导航

- **logo 区**：30px 渐变方标（`--r-l` 语义 9px 圆角）+ 产品名（14.5px/600）+ 副行（10.5px `--tx-2`）。
- **分组标题 navgrp**：10.5px、uppercase、`.14em` 字距、`--tx-dim`、padding `10px 16px 4px`。五组（实测）：**数据面**（告警工作台 `i-siren`、候选事件 `i-layers`）、**控制面**（事件响应 `i-zap`、排班与升级 `i-cal`）、**运营面**（巡检看板 `i-radar`、Workflow 编排 `i-branch` + `P3` tag）、**智能面**（AI 任务中心 `i-spark`）、**系统**（管理后台 `i-gear`）。
- **导航项 nav**：13.5px、高约 32px（padding 7px 10px）、`--r-s`；图标 16px `--tx-2`；default 文字 `--tx-3`，hover 底 `--surface-2` 文字 `--tx`；**激活**：底 `--surface-2` + 文字 `--tx-hi` + 图标 `--brand-t` + 左侧 2.5px brand 内阴影指示条；`aria-current` 标记。
- **徽标 bdg**：右侧自动 margin、18px 胶囊、brand 底白字 10.5px/600、tabular-nums；`.pu` 变体紫底（仅 AI 待审批）。计数徽标由各页面数据驱动（告警/候选/活跃事件/待审批）。
- **side-foot**：`margin-top: auto` 吸底、上边框、11px `--tx-dim` + 7px 绿点（辉光）。原型文案「告警接入层正常 · 演示数据」。

### 2.3 顶栏（52px）

左→右：**env 环境徽标**（24px 高、teal 调底/边/字 11.5px、`i-shield` 12px）→ **全局搜索 gsearch**（300px × 32px、`--r-s`、surface 底 surface-3 边、`i-search` 14px、input 13px `--tx-hi`、placeholder `--tx-dim`）→ 弹性空隙 → **角色切换器 rolebox**（32px、无边 select 12.5px；演示装置，生产形态见 §4.9）→ **通知铃 iconbtn**（32px 方、`--r-s`、`i-bell`、右上 pip 角标 14px 胶囊 brand 底白字 9.5px/700）→ **头像 avatar**（28px 圆、紫渐变底、首字 11px/600）。iconbtn：default `--tx-2`、hover 底 `--surface-2`。

### 2.4 内容区与页面骨架

每页统一结构：**页头 ph**（h1 17px/600 + 副标题 12.5px `--tx-2` + 弹性空隙 + 右对齐主操作按钮组；下边距 16px）→ 可选 **管道卡行 pipe**（4 列 `1fr 1fr 1fr 1.2fr`、列距 12px）/ **统计卡行 stats**（`repeat(4,1fr)`、列距 12px）→ 主体卡片区（单卡表格或 **grid2** 双列 16px 列距）。**卡片 card**：surface 底 + 1px surface-3 边 + `--r-m`；**卡片头 card-h**：13px/600 `--tx-hi` + 图标（`--tx-2`）+ 右侧常用 tag/chip，padding 12px 16px、下边框。**筛选条 fbar**：卡片内顶部，分段器 + 下拉 + 右对齐计数（`--tx-dim` 11.5px tabular-nums）。

### 2.5 浮层体系

| 层 | 规格 |
|---|---|
| scrim | 铺满容器 `rgba(22,23,25,.38)` + `blur(2px)`，`fade .18s`，点击关闭，z-40 |
| **drawer 抽屉** | 右侧贴边 500px（`max-width:92%`）× 全高、surface 底 + 左边框、z-41、`slidein .2s ease-out`（右移 24px 入场）；结构 = 头（标题区 + 关闭钮）/ tabs（34px 高，激活 2px brand 下边框）/ 滚动体 / 底部操作条（上边框、按钮组 + 右侧提示文字） |
| **modal 弹窗** | 居中 `min(600px, 94%)`、`max-height:88%` 内滚、raise 边框 + `--r-l` + 大阴影、`pop .18s ease-out`（-2% 垂直缩放入场）；结构 = 头（图标 + 标题 15px/600 + 可选 tag + 关闭钮）/ 体（13px）/ 底（右对齐按钮组，主按钮在最右） |

### 2.6 Toast 系统

右下角 `16px` 定位、纵列 gap 8px、单条 `max-width:380px`、z-60、`aria-live="polite"`。结构：surface 底 + 1px 边框（#e4e8eb）+ **3px 左侧语义色条** + 标题 b（12.5px/600 `--tx-hi`）+ 正文（12.5px）+ 可选动作链接 `.ta`（teal-t 12px + `i-arr` 12px，hover 下划线）。类型边条色：默认 teal / `ok` green / `err` red / `ai` purple / `warn` gold。**时序（原型 JS 实测）**：入场 `tin .22s ease-out`（上移 8px 淡入）→ 停留 4200ms → 300ms 透明淡出后移除。

### 2.7 响应式行为（原型 media query 实测，仅两条）

| 断点 | 塌缩形态 |
|---|---|
| `≤1024px` | 统计卡 4→2 列；管道卡 4→2 列且**步骤间箭头隐藏**；grid2 双栏→单列；周历 7→4 列 |
| `≤820px` | **侧栏 228px→56px 图标态**：隐藏分组标题、产品名/副行、侧栏脚，logo 居中，nav 仅图标居中（padding 9px 0），徽标绝对定位偏移 `translate(10px,-8px)`；全局搜索 300px→150px；周历 4→2 列 |

断点取值与 Tailwind 映射（md=820 / lg=1024）遵循 `03-frontend-design.md` §2.3 结论。**事实说明**：原型样式注释宣称「375/768/1024/1440」四断点，但实测仅实现 1024/820 两条；≤768 与 ≥1440 无专属规则（内容区无 max-width 上限），见 §6。

### 2.8 动画与 prefers-reduced-motion

**keyframes 4 个**：`tin`（toast：opacity 0→1 + translateY 8px→0，.22s ease-out）；`slidein`（抽屉：opacity + translateX 24px→0，.2s ease-out）；`fade`（scrim：opacity，.18s）；`pop`（弹窗：opacity + 居中缩放 -48%→-50%，.18s ease-out）。**过渡**：nav/按钮/输入/开关 `.15s`；表格行 hover `.12s`；管道步骤卡 `.3s`。**降级（硬规则）**：`@media (prefers-reduced-motion: reduce)` 下 `*` 的 `animation` 与 `transition` 全部 `none !important`。

### 2.9 可访问性基线（实测）

- `:focus-visible`：2px `--purple` outline、offset 2px、4px 圆角（键盘可见焦点环统一紫色）。
- `::selection`：`rgba(197,53,32,.18)` 品牌选中底。
- 滚动条：10px、thumb `#c9cdd1` 6px 圆角 + 3px 画布色留边。
- aria 用法（原型已示范）：nav `aria-current`、tabs `role="tablist"/"tab"/aria-selected`、抽屉/弹窗 `role="dialog" aria-modal="true" aria-label`、toast 容器 `aria-live="polite"`、图标钮 `aria-label`、趋势图 `role="img" aria-label` 描述、筛选组 `role="group" aria-label`、单选组 `role="radiogroup" aria-label`。
- 状态不作纯色信息：chip 一律「彩点 + 文字」，severity 含文案（P1·严重 等）。

## 3. 逐页面排版布局

> 覆盖原型实际实现的 **9 个页面视图**（8 个导航页 + 事件详情子视图）与全局浮层；页面职责与操作流见 `02-interaction-flows.md` §4。以下「空态」为原型已有，「加载态」原型一律未覆盖（`[TBD-UX]`，见 §6）。

### 3.1 告警工作台（alerts）

```text
页头：告警工作台 + 副标（链路说明 + 更新时间）·······[模拟告警接入]
管道卡：① 接入 → ② 去重 → ③ 富化 → ④ 关联（每卡：标签/大数值/说明；激活卡 brand 描边）
统计卡 ×4：待处理告警 │ 去重抑制 │ P1/P2 活跃 │ 维护窗口抑制
主卡片：
  筛选条：severity 分段器(全部/P1-P4) + 状态下拉 + ····· 右侧计数
  表格：严重度 │ 告警/降噪归因 │ fingerprint │ 富化 │ 状态 │ 最近发生 │ 行操作
（点击行 → 右侧抽屉 §3.2）
```

- **信息层级**：一眼→管道四步计数（当前告警流健康度）；其次→统计卡（降噪成效）；主体→告警表格（合并计数 ×N 徽标 + 每行降噪归因摘要）。
- **组件**：pstep（含步骤间箭头与激活态）、stat（含 up/down/warm 涨跌色）、seg、select.inp、表格（mono fingerprint 截断列、sev chip、状态 chip、行操作 ibtn 组）、drawer、modal（抑制建议）。
- **空态**：表格「没有匹配的告警」；加载态未覆盖 `[TBD-UX]`。

### 3.2 告警详情抽屉（全局浮层，5 个 tab）

```text
头：sev chip + 告警标题（14px）· 状态 chip + ID(mono)
tabs：详情 │ 原始 Payload │ 富化字段 │ AI 解释 │ 关联事件
体（滚动）：随 tab 切换 —— kv 键值对 / 代码块 / kv+runbook 链接 / aibox(或 NoAI warn 变体) / 关联事件入口卡
脚：认领(Ack)主按钮 + 转事件 + 抑制建议 ····· 右侧审计提示（i-clock + BR-10 文案）
```

- **AI 解释 tab 三态（实测）**：无权限空态 / 未生成空态（提示 BR-09 触发条件）/ 正常态 aibox（模型、tokens、脱敏摘要脚注）/ **NoAI 降级态**（gold 调 aibox + 原始错误代码块）。
- 降噪归因在「详情」tab 以 teal 调信息框（`i-inbox`）呈现；归因可视化深化 `[TBD-UX]`（沿用交互文档 §7）。

### 3.3 候选事件确认队列（candidates）

```text
页头：候选事件确认队列 + 副标（BR-04 引用）
候选卡（纵列堆叠，每张）：
  卡头：i-layers + 事件标题 + 「候选 · CAND-xx」虚线感 tag
  rulebox：命中规则编号(bold 紫) + 规则描述 + 时间窗 + 相似度% + simbar 进度条
  成员告警行 ×N：sev chip + 标题 + ×count + fingerprint(mono)
  底部操作：确认立项(主) + 驳回 ····· 右侧「驳回原因回流」提示
```

- **信息层级**：一眼→候选标题与相似度；其次→成员告警清单；操作→确认/驳回。
- **空态**：「队列为空 · 所有候选已确认或驳回」；驳回走 modal 单选卡组（三原因）。

### 3.4 事件响应列表（incidents）

```text
页头：事件响应 + 副标（L3 状态机链说明）
单卡片表格：事件(ID mono + 标题) │ 严重度 │ 状态 │ 值班人(待认领=brand-w 警示字) │ 状态页(已同步 ok-chip / —) │ 创建时间
（点击行 → 事件详情 §3.5）
```

- 无筛选条（原型未实现，筛选需求待 UX `[TBD-UX]`）；加载态未覆盖 `[TBD-UX]`。

### 3.5 事件详情（incDetail）

```text
页头：← 返回 │ INC-xxxx + 标题(h1) + sev/status chip + 团队·时间 ··· [推进下一状态(主)] [发起 Agent 调查(ai 按钮, P3 tag)]
步进条：open ─ acknowledged ─ mitigated ─ resolved ─ closed（3px bar，done=green / cur=brand，标签 10.5px）
grid2 双栏：
  左栏 卡片：事件时间线（tl 竖线 + 四色节点 auto/man/esc/ai）+ 底部「添加处理记录」输入行
  右栏 纵列：值班与升级状态卡（linklist 只读行，投递留痕）→ 状态页同步卡（ok-chip + 撤回按钮）→ 关联告警卡（linklist 可点，跳告警抽屉）
```

- **信息层级**：一眼→状态机当前位置与下一步动作；其次→时间线最新条目；右栏→升级/状态页/关联告警三个支撑卡。
- 主按钮文案随状态机变化（确认处理/止血完成/根因恢复/关闭事件）；P1/P2 关闭时触发复盘模板 toast（L3 链路）。
- 加载态/错误态未覆盖 `[TBD-UX]`。

### 3.6 巡检看板（inspections）

```text
页头：巡检看板 + 副标（最近巡检时间 + 规则库数）····· 集群分段器（右对齐）
统计卡 ×4：集群健康分 │ open findings │ 已认领处置中 │ AI 已解释
grid2：趋势图卡（bars 堆叠柱 warn+/info + 图例）│ 巡检策略卡（kv：规则集/调度/ai_explain_level/转告警）
主卡片：Findings 表：规则(mono+ID) │ 资源 │ 严重度 │ 状态 │ AI 解释(已解释 ai-chip/未解释/info 不入 AI) │ 行操作
  可展开行：AI 解释 aibox（或「正在生成解释…」虚线框生成中态）
```

- **行操作三件**：认领（`i-check`）/ 忽略（`i-x`）/ AI 解释（btn-ai 小按钮；info 级禁用并提示 BR-09）。
- **空态**：「该集群暂无 findings」；生成中态已有（虚线边框 aibox），加载态未覆盖 `[TBD-UX]`。

### 3.7 AI 任务中心（ai）

```text
页头：AI 任务中心 + 副标（护栏规则编号串）
统计卡 ×4：本月调用 │ token 消耗(月度预算%) │ 待审批 │ 本地模型占比
主卡片：任务表：任务(ID+by) │ 类型(ai-chip) │ 对象(+说明) │ 模型 │ 预算(calls/tokens 双行 + 4px 进度条，>90% 变红) │ 状态 │ 行操作
  pending_approval 行：整行紫色 5% 底高亮
（审批 → modal；调用链 → modal；workflow_gen → YAML diff modal）
```

- **审批 modal**（AI 审批流核心）：工具命令代码块 + 预算已消耗 kv + 审批超时说明 + 危险拒绝（左）/ 主批准（右）。
- **加载态**未覆盖 `[TBD-UX]`；无权限时整页空态（权限提示）。

### 3.8 Workflow 编排（workflows，P3）

```text
页头：Workflow 编排 + P3 tag + 副标（BR-05 引用）····· [NL 生成 Workflow(btn-ai)]
卡片一：编排定义表：名称(mono) │ 版本 │ 来源(manual chip / ai_generated ai-chip + approved_by) │ 触发 │ 执行次数 │ 最近执行
卡片二：执行记录（linklist 只读行：版本 + 触发 + 状态 + waiting_approval 说明）
（NL 生成 → modal 文本域 → diff 预览 modal）
```

- **diff modal**：说明文案 + 代码块带 `+/-` 行高亮（add 绿底 / del 红底）+ 底部「需要修改（回 AI）」（左，普通钮）/「确认入库 v3」（右，主钮）——A3 人在回路核心交互（BR-05）。
- 编辑器本体（Monaco）原型未实现，仅示意 `[TBD-UX]`（P3 前出编辑器布局稿）。

### 3.9 排班与升级（oncall）

```text
页头：排班与升级 + 副标（BR-08 引用）····· 可编辑/只读 chip
卡片一：本周排班 week（7 列日格：星期 / 主班+小标 / 备班+小标；今日 brand 描边光环）+ 头部右侧 overrides 说明
卡片二：升级策略表：级别 │ 目标与渠道 │ 超时 │ 本周触发 + 底部说明行（降级链/留痕/记录数）
```

- 日期格内主班 12.5px/500 `--tx-hi`、备班 `--tx-3` 常规字重；编辑交互原型未实现 `[TBD-UX]`（P2 排班详设）。

### 3.10 管理后台（admin）

```text
页头：管理后台 + 副标（凭证安全提示）
grid2 四卡：
  集群与凭证（linklist：状态图标 + 集群名 + 版本 + 凭证 secret_ref，失败集群 gold 警示）
  Provider 接入（linklist：类型·category·pull_mode）
  巡检规则库（kv：总数/版本适配/更新来源）
  AI 预算与模型路由（kv：默认预算 / 本地优先 switch / 出域策略 + TBD tag）
```

- **硬规则**：凭证只展示 `secret_ref` 引用与轮换信息，永不回显值（安全红线）；写操作表单原型未实现 `[TBD-UX]`。

## 4. 组件规范

> 每类给出结构、尺寸与状态；token 引用见 §1。**不发明原型没有的组件。**

### 4.1 徽章族

| 组件 | 规格 | 状态/变体 |
|---|---|---|
| **severity chip** | 高 20px、`0 8px` 内边、圆角 5px、11px/500、6px 彩点 + 文案 | P1 `red-t`·「P1 · 严重」；P2 `brand-t`·「P2 · 高」；P3 `gold`·「P3 · 中」；P4 `teal-t`·「P4 · 低」 |
| **状态 chip**（告警 6 态） | 同上，dot 用 currentColor | notified 已通知 teal / correlated 已关联 purple / suppressed 已抑制灰 / **candidate 候选关联 purple + 虚线边框（专属形态）** / acked 已认领 teal / closed 已关闭灰 |
| **状态 chip**（事件 5 态） | 同上 | open 立项 open red / acknowledged 已确认 teal / mitigated 已止血 gold / resolved 已恢复 green / closed 已关闭灰 |
| **状态 chip**（AI 任务 8 态） | 同上 | created·sanitizing 脱敏中·running teal / pending_approval 紫（候选样式）/ completed green / cancelled 灰 / budget_exceeded gold（P3 样式）/ failed red |
| ai-chip / ok-chip | 同 chip | 紫（AI 类型/ai_generated/已解释）/ 绿（已同步等成功态） |
| **tag** | 高 17px、`0 6px`、圆角 4px、10px、`.05em` 字距 | 默认 surface-3/`--tx-3`；`.pu` 紫；`.br` brand；`.gd` gold；P3 分期角标用 `.pu` |
| **bdg 侧栏徽标** | 18px 胶囊、min-width 18px、10.5px/600、tabular-nums | brand 底白字；`.pu` 紫底（AI 待审批） |
| **pip 角标** | 14px 胶囊、9.5px/700 | brand 底白字，绝对定位于图标钮右上 |

### 4.2 按钮族（高 32px 基准、`--r-s`、12.5px/500、行内图标 14-16px）

| 变体 | default | hover | disabled |
|---|---|---|---|
| `btn` 默认 | surface-2 底 + raise 边框 + `--tx` | surface-3 底 | 全变体统一 `opacity:.45` + `cursor:not-allowed` |
| `btn-p` 主 | brand 底 + 白字 + 透明边 | brand-h（**加深**） | 同上 |
| `btn-ai` AI | 紫 10% 底 + 紫 45% 边 + `purple-t` 字 | 紫 20% 底 + purple 边 | 同上 |
| `btn-d` 危险 | red 8% 底 + red 40% 边 + `red-t` 字 | red 16% 底 | 同上 |
| `btn-sm` | 高 26px、11.5px、内边 `0 10px`（可与上述四色组合） | — | — |
| `ibtn` 行内图标钮 | 26px 方、6px 圆角、`--tx-2`、透明边 | surface-3 底 + `--tx-hi` | — |
| `iconbtn` 顶栏 | 32px 方、`--r-s`、`--tx-2` | surface-2 底 + `--tx` | — |

层级用法（实测）：每屏主操作唯一 `btn-p`；AI 能力一律 `btn-ai`（含「AI 解释」「NL 生成」「发起调查」）；终止/拒绝类 `btn-d`；其余默认钮。

### 4.3 输入与筛选

- **input/select（`.inp`）**：高 30px、`--r-s`、surface 底 surface-3 边、12.5px `--tx-hi`、placeholder `--tx-dim`；**focus 边框变 brand**；textarea 复用 `.inp`（原型 NL 输入即此，mono 12px）。
- **seg 分段器**：surface 底 + surface-3 边 + 2px 内边容器；内钮高 24px、12px、`--tx-2`；hover 文字 `--tx`；**激活** surface-3 底 + `--tx-hi` + 500 字重。
- **radios 单选卡组**：label 卡（surface-3 边 + `--r-s` + padding 9px 11px + 12.5px）、hover 边框升 raise；`accent-color: brand`。
- **switch 开关**：34×19px、10px 圆角轨道；未选中 surface-3；**选中 `rgba(10,138,84,.45)`（半透明绿）**；圆钮 14px 白 + 微阴影，选中位移 `translateX(15px)`；`.15s` 过渡。
- **gsearch**：见 §2.3。

### 4.4 数据表格

`width:100%`、13px、`border-collapse`；**th** 10.5px uppercase `.1em` `--tx-dim`/500、padding 9px 14px、下边框 surface-3、nowrap；**td** padding 10px 14px、下边框 `rgba(34,35,37,.12)`；可点击行 `tr.click`：pointer + hover `rgba(25,26,30,.045)`（.12s）；主标题 `atitle` 13px/500 `--tx-hi` + 副行 `asub` 11px `--tx-2`（图标 11px）；等宽内容（ID/fingerprint/规则码）用 `.mono`；行操作组 `rowacts` 右对齐 ibtn 列；**行内展开**（findings AI 解释）：`colspan` 全宽 + 紫 4% 底 + aibox；**行内进度条**（AI 预算）：4px 高 2px 圆角轨道 surface-3 + 填充 purple、**用量 >90% 变 red**。横向溢出包 `overflow-x:auto`。分页控件原型未实现 `[TBD-UX]`。

### 4.5 信息容器

- **card / card-h**：§2.4。
- **stat 统计卡**：padding 12px 14px；标签行（11.5px `--tx-2` + 13px 图标）/ 数值（22px/600 tabular-nums -.3px）/ 说明行（11.5px `--tx-dim`，涨跌用 `.up` green-t、`.down` red-t、`.warm` brand-w）。
- **pstep 管道步骤卡**：padding 11px 14px；标签 11px / 数值 17px/600 / 说明 11px；步骤间 `i-chr` 箭头绝对定位（右 -15px，仅 >1024 显示）；激活态 brand 描边 + 双层阴影（§1.5）。
- **rulebox 规则命中框**：紫 6% 底 + 紫 22% 边 + `--r-s`、12px `--tx-3`，规则编号紫色 600；配套 **simbar** 相似度条（4px 高、紫 18% 轨道 + purple 填充，宽 180px）。
- **aibox AI 内容框**：紫 6% 底 + 紫 35% 边 + `--r-m` + padding 13px 14px；头（`purple-t` 12.5px/600 + `i-spark` 14px + 可选 tag）；正文 12.5px；脚注（上边虚线 紫 30%、11px `--tx-2`、图标 12px、脱敏/模型/耗时/审计元信息）。**变体**：NoAI 警示（gold 调换色）、生成中（虚线边框）、信息提示（teal 调换色，降噪归因）。
- **kv 键值网格**：`110px 1fr` 两列、行距 6px 列距 12px、12.5px；dt `--tx-2`、dd `--tx-hi`。
- **pre.code 代码块**：`#f6f8fa` 底 + surface-3 边 + `--r-s` + padding 12px、mono 11.5px/1.6、`#2f3134`；diff 行高亮：`.add` 全行绿 9% 底 + green-t 字、`.del` 全行红 8% 底 + red-t 字。
- **linklist 链接行**：gap 6px 纵列；行（8px 10px、surface-3 边、`--r-s`、12.5px）；hover 边框 raise + surface-2 底；有只读变体（`cursor:default`）。
- **bars 迷你柱状图**：110px 高、底对齐、列距 6px；柱顶角 3px 圆角、min-height 2px；warn+ 柱用 brand 纵向渐变（brand-h→brand）、info 柱 `rgba(7,121,164,.45)`；列标签 10px `--tx-dim`；外层 `role="img"` + aria-label。
- **week/day 周历**：7 列 grid、gap 8px；日格（surface 底、surface-3 边、`--r-s`、padding 10px、min-height 86px）；今日 brand 描边 + 光环；星期 11px `--tx-2`、主班 12.5px/500 `--tx-hi`（small 副标 10.5px `--tx-2`/400）。
- **empty 空态**：padding 36px 居中、13px `--tx-dim`，可含图标与次级说明行（11.5px）。

### 4.6 时间线与步进条

- **tl 时间线**：容器左 padding 20px；1px surface-3 竖线（::before）；节点 = 9px 圆点 + 2px 画布色描边（制造与竖线的视觉缺口），绝对定位 left -19px；**节点色**：默认 `--tx-dim` / auto teal / **ai purple + 辉光** / esc brand / man green；时间戳行 `tt` 11px `--tx-dim`（附「· AI 调查 / · 升级链 / · 人工」类别后缀）；正文 `tx` 12.5px。追加输入行（flex 输入框 + 小按钮）置于列表底。
- **steps 步进条**：flex 等分；每步 3px 高 bar（2px 圆角）：未达 surface-3 / done green / **cur brand**；标签 10.5px 居中：done green-t、cur brand-w、未达 `--tx-dim`。

### 4.7 浮层与 toast

drawer / modal / scrim / toast 规格 §2.5、§2.6。规则：主操作在右下（modal）/ 底部左起（drawer 脚）；弹窗标题左侧语义图标（紫色 `i-spark`、中性 `i-x` 等）+ 右侧关闭 ibtn；Esc 与 scrim 点击关闭（原型 JS 为 scrim 点击关闭；Esc 行为实现建议补充）。

### 4.8 导航类

nav / navgrp / bdg（§2.2）；tabs（34px 高、12.5px、`--tx-2`，hover `--tx`，激活 `--tx-hi` + 2px brand 下边框、`margin-bottom:-1px` 压住容器下边框）；seg（§4.3）。

### 4.9 演示装置（生产不保留）

**rolebox 角色切换器**：顶栏 32px 下拉，切换后按权限矩阵过滤界面并 toast 提示——**仅原型演示用**；生产端会话与角色获取遵循 `03-frontend-design.md` §3.2（该处已标 `[ASSUMPTION]`），登录页形态随认证 `[TBD-INFRA]`。**「模拟告警接入」按钮**同为演示装置（验证管道四步卡激活动画），生产不保留。

## 5. 与原型的偏差治理

1. **本文为规范的单一事实源**：前端实现以本文为准；原型（v0.1，1039 行）是本文的提取基线。
2. **变更流程**：原型任何视觉/布局改动必须先改本文、再改原型/代码；未经本文登记的原型改动视为无效基准。
3. **偏差登记表**（当前为空——本文即从原型逐行提取，零偏差）：

| 编号 | 位置（原型行/组件） | 原型现状 | 本文规定 | 状态 |
|---|---|---|---|---|
| — | — | — | — | 无 |

4. **已知「原型未实现项」**（非偏差，属 §6 缺口）：tooltip 样式（`data-tooltip` 属性已埋、无 CSS）、768/375/1440 断点、表格分页、加载态、Esc 关闭弹层。
5. 发现实现与本文不一致时：实现服从本文；若确需偏离，先修订本文并在此表登记。

## 6. 开放问题

| 标记 | 问题 | 确认人 / 阶段 |
|---|---|---|
| `[TBD-UX]` | 暗色模式是否恢复（原型历史曾有暗色版，当前为亮色白底版；token 全部按亮色提取） | UX / P0 前端开发前 |
| `[TBD-UX]` | 加载态规范（skeleton/spinner）：原型全站无加载态，仅有空态与 AI 生成中态 | UX / P0 前端开发前 |
| `[TBD-UX]` | 表格分页 / 无限滚动控件形态（原型无分页 UI；虚拟滚动性能预算在 `03-frontend-design.md` §6） | UX / P0 前端开发前 |
| `[TBD-UX]` | tooltip：`data-tooltip` 已埋属性但原型无样式实现，悬停提示形态待定 | UX / P0 前端开发前 |
| `[TBD-UX]` | 错误态视觉（接口失败、全局错误页）：原型未覆盖 | UX / P0 前端开发前 |
| `[TBD-UX]` | 大屏（≥1440）与窄屏（≤768/375）适配：原型注释宣称四断点但仅实现 1024/820；内容区无 max-width 上限 | UX / P0 末视觉走查 |
| `[TBD-UX]` | 多语言（当前仅简体中文；字号阶梯按中英混排实测，其他语言长度/字重未验证） | UX / 国际化需求出现时 |
| `[TBD-UX]` | Workflow 编辑器（P3）与排班编辑（P2）、管理后台写表单的布局稿：原型仅列表/只读形态 | UX / 各分期设计前 |
| `[ASSUMPTION]` | 对比度数值（≥4.5:1、白字 ≈4.9:1、tx-2 ≈7:1）照抄原型注释，未独立验证 | 前端 / P0 实装时以工具逐对复核 |
| `[ASSUMPTION]` | §1.8 Tailwind 变量命名与文字档归并、§1.4 辅助间距收敛建议 | 前端 / P0 实装时校准 |
