# 数据模型设计

| 元信息 | |
|---|---|
| 状态 | accepted |
| 日期 | 2026-10-24 |
| 依据 | `02-business-design/01-domain-model.md`（实体字典 §5.1、状态机 §6、业务规则 BR-01~13 §7、非功能约束 §8）、`02-business-design/02-interaction-flows.md`（L1-L4/A1-A3 链路）、`01-research/01-benchmark-report.md`（存储与技术栈对标） |
| 读者 | 后端研发、SRE、前端研发 |

> 业务规则只引用 BR-xx 编号，规则正文唯一事实源为 `02-business-design/01-domain-model.md` §7。本文档中的技术演绎（字段类型、索引、分区等）凡领域文档未规定者，均以 `[ASSUMPTION]`（附验证方式）或 `[TBD-*]` 标注。

---

## 1. 存储选型与理由

| 存储 | 用途 | 理由 | 出处 |
|---|---|---|---|
| **PostgreSQL（单库）** | 全部业务状态：告警、事件、巡检、AI 任务、排班、审计、编排 | ① Keep 与本平台同构（FastAPI + PG），数据模式可直接参考；② OneUptime 验证了「PG 管业务状态」的职责划分；③ 单库起步与「模块化单体」架构建议一致，运维成本最低；④ JSONB 原生支持 labels/raw_payload/matchers 等半结构化字段（§5 决策 D-3） | 对标报告 §0/§4/§6.2 |
| **Redis** | ① 高频去重指纹的快速判重缓存（L1 热路径，最终一致性以 PG 唯一约束兜底）；② 异步任务队列（Celery/ARQ 类）的 broker；③ SSE/实时推送的轻量状态 | Keep 同构实践（PG + Redis/Celery 起步）。**部署形态（自建/托管、单实例/哨兵）`[TBD-INFRA]`，由基础设施负责人在 P0 部署设计时确认** | 对标报告 §6.2；领域文档 §8 |
| 不自建遥测存储 | 日志/指标/trace 的采集与存储 | 平台 Out of scope，复用企业已有 Prometheus/Grafana/Loki `[TBD-INFRA]`；`alerts.raw_payload` 只存告警原文快照，不承担遥测存储职责 | 领域文档 §2 |

**演进预留**：当告警/AI 调用量达到容量上限（非功能 §8 性能项 `[ASSUMPTION]` 待容量规划验证）时，优先按 §5 决策 D-9 做表分区，再评估引入独立分析型存储（对标报告 §6.2 的 ClickHouse 分层建议），不在本期范围。

## 2. 逻辑模型

### 2.1 通用约定

| 项 | 约定 | 备注 |
|---|---|---|
| 命名 | 表名 snake_case 复数；字段 snake_case；索引 `idx_<表>_<字段>`，唯一索引 `uk_<表>_<字段>` | — |
| 主键 | `id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY` | `[ASSUMPTION]` 单库内部系统无分布式主键需求；若未来分库再评估 UUIDv7（验证方式：架构评审） |
| 时间 | 一律 `timestamptz`，UTC 存储、前端本地化展示 | 领域文档 §5.2 |
| 字符串长度 | 默认 `text` 不限长 | `[ASSUMPTION]` PG 下预设长度收益低，唯一约束字段按需收紧（验证方式：性能实测 + 编码规范评审） |
| 枚举 | 一律 `text` + `CHECK` 约束（不使用 PG ENUM 类型） | `[ASSUMPTION]` 便于值域演进与跨环境迁移（验证方式：后端技术评审） |
| 半结构化字段 | labels / raw_payload / matchers / mappings / levels / steps_log 等用 `jsonb` | 见 §5 决策 D-3 |
| 建库字符集 | UTF-8 | — |

以下按领域文档 §4 子域分组给出表设计。`分期` 列标注该表首次建表的阶段（与 §7 一致）。

### 2.2 身份与审计域（P0）

#### users（用户）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| username | text | NOT NULL, UNIQUE | 登录名 |
| email | text | NOT NULL, UNIQUE | — |
| display_name | text | NOT NULL | 展示名 |
| team | text | NULL | 所属团队；团队/服务归属数据源（CMDB 对接 or 平台自维护）`[TBD-BIZ]`（业务负责人 / P0 设计前），先以冗余文本建模 |
| is_active | boolean | NOT NULL DEFAULT true | 停用即置 false（状态化删除，见 D-7） |
| created_at / updated_at | timestamptz | NOT NULL | — |

不含密码/凭据字段：认证方式（SSO/LDAP/本地）`[TBD-INFRA]`（基础设施负责人 / P0 部署设计）。

#### roles（角色）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| code | text | NOT NULL, UNIQUE | 领域文档 §3：`admin` / `sre` / `oncall_manager` / `developer` / `viewer` |
| name | text | NOT NULL | 展示名 |
| permissions | jsonb | NOT NULL | 领域文档 §3 权限矩阵（资源 × 动作）落库为结构化 JSON `[ASSUMPTION]`（验证方式：P0 权限模块详设评审） |
| created_at / updated_at | timestamptz | NOT NULL | — |

#### user_roles（用户-角色授予）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| user_id | bigint | PK, FK → users.id ON DELETE CASCADE | — |
| role_id | bigint | PK, FK → roles.id | — |
| team_scope | text | NULL | `developer` 角色「限本团队」的授权范围（权限矩阵 T 列）；其他角色为 NULL `[ASSUMPTION]`（验证方式：P0 权限模块详设评审） |
| granted_at | timestamptz | NOT NULL | — |
| granted_by | bigint | NULL, FK → users.id | 授予人（审计追溯） |

#### audit_logs（审计日志，BR-10）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| actor_user_id | bigint | NULL, FK → users.id | 操作人；系统自动触发时为 NULL |
| actor_type | text | NOT NULL DEFAULT 'user' | `user` / `system` `[ASSUMPTION]`（验证方式：P0 审计模块详设） |
| action | text | NOT NULL | 动作标识，如 `cluster.create`、`alert.acknowledge` |
| resource_type | text | NOT NULL | 目标表名，如 `clusters` |
| resource_id | text | NOT NULL | 目标行主键（多态引用，统一 text） |
| detail | jsonb | NOT NULL DEFAULT '{}' | 变更内容摘要（who/when/what，BR-10） |
| cost | jsonb | NULL | 成本计量（BR-10 的 cost 项；AI 类写操作记录 tokens 等计数） |
| ip | text | NULL | 来源 IP，审计溯源 `[ASSUMPTION]`（验证方式：P0 审计模块详设） |
| user_agent | text | NULL | 同上 |
| created_at | timestamptz | NOT NULL | 即 BR-10 的 when |

约束与索引：**只追加不可改**（BR-10，实现见 D-6）；`idx_audit_logs_resource(resource_type, resource_id)`；`idx_audit_logs_actor(actor_user_id, created_at)`；`idx_audit_logs_created(created_at)`。分区见 D-9。

### 2.3 集群接入域（P0）

#### credentials（凭证引用）

> 红线：本表**只存外部密钥管理系统的引用，不存任何凭证值**（领域文档 §8 凭据安全；BR-02）。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| name | text | NOT NULL, UNIQUE | — |
| secret_ref | text | NOT NULL | 密钥管理引用（如 vault 路径 / KMS key id），格式随密钥系统 `[TBD-INFRA]`（基础设施负责人 / P0 部署设计） |
| scope | text | NOT NULL DEFAULT 'readonly', CHECK ∈ {readonly, write} | 默认 readonly（BR-02：写须审批且管理员显式开启） |
| expires_at | timestamptz | NULL | 到期提醒用 |
| created_at / updated_at | timestamptz | NOT NULL | — |

#### clusters（集群）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| name | text | NOT NULL, UNIQUE | — |
| environment | text | NOT NULL | 环境标识（dev/staging/prod 等开放值，不做枚举） |
| api_endpoint | text | NOT NULL | — |
| status | text | NOT NULL DEFAULT 'unknown', CHECK ∈ {connected, degraded, disconnected, unknown} | 值域 `[ASSUMPTION]`：领域文档未定义状态机，按「连接健康」语义推导（验证方式：P0 接入域详设评审） |
| k8s_version | text | NULL | 最近探测到的版本 |
| credential_id | bigint | NOT NULL, FK → credentials.id | 只读凭证引用（领域 ER：多集群可复用同一凭证） |
| last_checked_at | timestamptz | NULL | 最近一次探活时间（异常降级路径：集群连接失败 → 探活告警，交互文档 §6） |
| deleted_at | timestamptz | NULL | 软删（D-7） |
| created_at / updated_at | timestamptz | NOT NULL | — |

索引：`idx_clusters_status(status)`。

### 2.4 告警管理域（P0/P2）

#### providers（告警源提供方）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| name | text | NOT NULL, UNIQUE | — |
| type | text | NOT NULL | 类型标识（如 `alertmanager`、`prometheus`、`dingtalk-action`），开放集合 |
| category | text | NOT NULL, CHECK ∈ {source, query, action} | 三类角色统一抽象（实体字典 §5.1） |
| pull_mode | text | NULL, CHECK ∈ {push, poll} | 仅 category=source 有意义 `[ASSUMPTION]`（验证方式：P0 Provider 框架详设） |
| config | jsonb | NOT NULL DEFAULT '{}' | 非敏感配置（endpoint、过滤条件等）；**严禁写入任何密钥值**（领域文档 §8） |
| credential_id | bigint | NULL, FK → credentials.id | Provider 凭据同样只存引用 |
| fingerprint_fields | jsonb | NOT NULL DEFAULT '[]' | 参与指纹计算的字段清单（Keep 范式，实体字典 §5.1） |
| enabled | boolean | NOT NULL DEFAULT true | — |
| created_at / updated_at | timestamptz | NOT NULL | — |

#### alerts（告警，L1 管道核心表）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| fingerprint | text | NOT NULL | 去重主维度（业务键） |
| provider_id | bigint | NOT NULL, FK → providers.id | 上报来源 |
| title | text | NULL | 列表展示标题，从 payload 归一化提取 `[ASSUMPTION]`（验证方式：P0 前端信息架构评审，关联交互文档 §4.1 告警工作台） |
| severity | text | NOT NULL, CHECK ∈ {info, warning, critical} | 归一化严重度；值域 `[ASSUMPTION]`：领域文档未定义 Alert severity 值域，BR-09 的「warn 以上」对应本枚举 warning/critical（验证方式：P0 Provider 归一化设计评审） |
| status | text | NOT NULL DEFAULT 'received', CHECK ∈ {received, deduplicated, enriched, correlated, standalone, suppressed, notified, resolved} | 与领域文档 §6 Alert 状态机严格一致 |
| labels | jsonb | NOT NULL DEFAULT '{}' | 归一化标签（原始标签） |
| enrichments | jsonb | NOT NULL DEFAULT '{}' | 富化管道附加字段（team/影响面/oncall 组等）；与原始 labels 分离存储便于「降噪归因」展示 `[ASSUMPTION]`（验证方式：P0 告警域详设评审） |
| raw_payload | jsonb | NOT NULL | 原始上报内容快照；保留期见 §6 |
| occurrence_count | integer | NOT NULL DEFAULT 1 | 同 fingerprint 合并计数（L1：命中时 +1） |
| first_occurred_at | timestamptz | NOT NULL | 实体字典 occurred_at 拆为首末两个时点 |
| last_occurred_at | timestamptz | NOT NULL | 命中合并时更新（L1） |
| assignee_id | bigint | NULL, FK → users.id | 认领人（交互文档 §4.2 告警处置流） |
| acknowledged_at | timestamptz | NULL | 认领时间 |
| resolved_at | timestamptz | NULL | 恢复/人工关闭时间 |
| suppressed_by_window_id | bigint | NULL, FK → maintenance_windows.id | 被哪个维护窗口抑制（BR-07；状态 = suppressed 时非空） |
| created_at / updated_at | timestamptz | NOT NULL | — |

索引：
- `uk_alerts_active_fingerprint UNIQUE (fingerprint) WHERE status <> 'resolved'` —— **活跃周期内指纹唯一**：同指纹活跃告警合并计数，resolved 后同指纹再现则开新记录（D-1）
- `idx_alerts_labels GIN (labels jsonb_path_ops)` —— 富化/关联条件按标签检索
- `idx_alerts_provider_time (provider_id, last_occurred_at DESC)`
- `idx_alerts_status_severity (status, severity)` —— 工作台筛选

#### enrichment_rules（富化规则）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| name | text | NOT NULL, UNIQUE | — |
| matchers | jsonb | NOT NULL | 匹配条件（对 labels 的谓词） |
| mappings | jsonb | NOT NULL | 富化动作：`[{type: extraction\|mapping, source, target, ...}]`（实体字典 §5.1 extraction/mapping 两类） |
| priority | integer | NOT NULL DEFAULT 0 | 多条命中时的应用顺序 `[ASSUMPTION]`（验证方式：P0 富化引擎详设） |
| enabled | boolean | NOT NULL DEFAULT true | — |
| deleted_at | timestamptz | NULL | 软删（D-7） |
| created_at / updated_at | timestamptz | NOT NULL | — |

#### correlation_rules（关联规则，P2）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| name | text | NOT NULL, UNIQUE | — |
| conditions | jsonb | NOT NULL | AND/OR 组合条件（实体字典 §5.1） |
| time_window_seconds | integer | NOT NULL | 关联时间窗（秒存储） |
| mode | text | NOT NULL DEFAULT 'candidate', CHECK ∈ {auto, candidate} | 「候选」英译 candidate `[ASSUMPTION]`；candidate 必须人工确认（BR-04），auto 准入门槛见 BR-04 `[TBD-BIZ]` |
| activated_at | timestamptz | NULL | 规则生效时间，供 BR-04「已运行 ≥30 天」准入计算 |
| confirm_count | integer | NOT NULL DEFAULT 0 | 候选被确认次数（运营统计，支撑 auto 准入）`[ASSUMPTION]` |
| reject_count | integer | NOT NULL DEFAULT 0 | 候选被驳回次数（同上，驳回原因回流见 incident_candidates） |
| enabled | boolean | NOT NULL DEFAULT true | — |
| deleted_at | timestamptz | NULL | 软删（D-7） |
| created_at / updated_at | timestamptz | NOT NULL | — |

#### maintenance_windows（维护窗口，P2，支撑 BR-07）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| name | text | NOT NULL | — |
| scope | jsonb | NOT NULL | 抑制范围匹配器（集群/namespace/labels 谓词） |
| starts_at | timestamptz | NOT NULL | — |
| ends_at | timestamptz | NOT NULL | 窗口结束未恢复的告警重新进入管道（BR-07） |
| reason | text | NOT NULL | — |
| created_by | bigint | NULL, FK → users.id | — |
| created_at | timestamptz | NOT NULL | — |

索引：`idx_maintenance_windows_ends(ends_at)`（窗口结束扫描）。领域实体字典未单列该实体，本设计依据 BR-07 与 Alert 状态机 suppressed 状态将其落为独立表 `[ASSUMPTION]`（验证方式：P2 告警域详设评审）。

### 2.5 事件响应域（P2）

#### incident_candidates（候选事件，BR-04）

> 领域实体字典未单列；为使 `incident_status` 与领域状态机严格一致（open 即已立项），候选事件独立建表，确认后转入 incidents `[ASSUMPTION]`（验证方式：P2 事件域详设评审）。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| correlation_rule_id | bigint | NOT NULL, FK → correlation_rules.id | 命中规则 |
| title | text | NOT NULL | 规则动态命名 |
| member_alert_ids | jsonb | NOT NULL | 成员告警 id 数组（展示「命中规则 + 成员告警」，交互文档 §4.2） |
| similarity | numeric | NULL | 相似度展示值（计算产出，来源见交互文档 §4.2）`[ASSUMPTION]` |
| status | text | NOT NULL DEFAULT 'pending', CHECK ∈ {pending, confirmed, rejected} | 值域 `[ASSUMPTION]`（验证方式：P2 事件域详设） |
| reject_reason | text | NULL | 驳回原因（规则过宽/时间窗过长/富化字段错误等，交互文档 §4.2；作为规则调优输入回流） |
| decided_by | bigint | NULL, FK → users.id | 确认/驳回人 |
| decided_at | timestamptz | NULL | — |
| created_at | timestamptz | NOT NULL | — |

#### incidents（事件）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| title | text | NOT NULL | — |
| severity | text | NOT NULL, CHECK ∈ {P1, P2, P3, P4} | 实体字典 §5.1（P1-P4） |
| status | text | NOT NULL DEFAULT 'open', CHECK ∈ {open, acknowledged, cancelled, mitigated, resolved, closed} | 与领域文档 §6 Incident 状态机严格一致 |
| source | text | NOT NULL, CHECK ∈ {correlation, manual} | 规则归并 / 人工立项（状态机入口）`[ASSUMPTION]` 值域（验证方式：P2 事件域详设） |
| candidate_id | bigint | NULL, FK → incident_candidates.id | 候选确认立项的来源回链（BR-04） |
| correlation_rule_id | bigint | NULL, FK → correlation_rules.id | auto 归并来源（L1） |
| team | text | NULL | 影响团队（富化字段） |
| assignee_id | bigint | NULL, FK → users.id | 值班处置人 |
| created_by | bigint | NULL, FK → users.id | 人工立项人 |
| status_page_sync | boolean | NOT NULL DEFAULT false | 是否已同步状态页（BR-06） |
| cancelled_reason | text | NULL | 误报关闭原因（状态机：cancelled 必填，应用层校验） |
| acknowledged_at / mitigated_at / resolved_at / closed_at | timestamptz | NULL | 状态时间戳 |
| created_at / updated_at | timestamptz | NOT NULL | — |

索引：`idx_incidents_status_severity(status, severity)`；`idx_incidents_team(team)`。

#### incident_alerts（事件-告警关联，多对多）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| incident_id | bigint | PK, FK → incidents.id | — |
| alert_id | bigint | PK, FK → alerts.id | — |
| correlation_rule_id | bigint | NULL, FK → correlation_rules.id | 由哪条规则关联 |
| linked_at | timestamptz | NOT NULL | — |

索引：`idx_incident_alerts_alert(alert_id)`（反查告警所属事件）。

#### postmortems（复盘报告）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| incident_id | bigint | NOT NULL, UNIQUE, FK → incidents.id | 一事一复盘（领域 ER 1:0..1） |
| timeline | jsonb | NOT NULL | 时间线（自动 + 人工汇总，L3） |
| root_cause | text | NOT NULL | 根因 |
| created_by | bigint | NOT NULL, FK → users.id | — |
| created_at / updated_at | timestamptz | NOT NULL | — |

`action_items[{owner, due, status}]`（实体字典 §5.1）拆为子表 postmortem_action_items，支撑分派与跟踪（L3）`[ASSUMPTION]`（验证方式：P2 事件域详设评审）。

#### postmortem_action_items（复盘行动项）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| postmortem_id | bigint | NOT NULL, FK → postmortems.id ON DELETE CASCADE | — |
| content | text | NOT NULL | 行动项内容 |
| owner_id | bigint | NULL, FK → users.id | 负责人 |
| due_date | date | NULL | 截止日 |
| status | text | NOT NULL DEFAULT 'pending', CHECK ∈ {pending, in_progress, done} | 值域 `[ASSUMPTION]`（验证方式：P2 事件域详设） |
| created_at / updated_at | timestamptz | NOT NULL | — |

#### status_page_entries（状态页条目）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| incident_id | bigint | NOT NULL, UNIQUE, FK → incidents.id | 事件状态自动同步（BR-06；领域 ER 1:0..1） |
| title | text | NOT NULL | 对外标题 |
| visibility | text | NOT NULL DEFAULT 'internal', CHECK ∈ {public, internal} | 受众；默认值取决于状态页受众结论 `[TBD-BIZ]`（业务负责人 / P2 设计前） |
| service_status | text | NOT NULL | 服务状态快照（如 operational/degraded/outage），值域随状态页详定 `[ASSUMPTION]`（验证方式：P2 状态页详设） |
| created_at / updated_at | timestamptz | NOT NULL | — |

`updates[]`（实体字典 §5.1）拆为子表 status_page_updates，支撑时间线与撤回审计 `[ASSUMPTION]`（验证方式：P2 状态页详设）。

#### status_page_updates（状态页更新）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| entry_id | bigint | NOT NULL, FK → status_page_entries.id ON DELETE CASCADE | — |
| message | text | NOT NULL | 更新内容 |
| status_snapshot | text | NULL | 本次更新的服务状态 |
| posted_by | bigint | NULL, FK → users.id | 发布人（系统同步时为 NULL） |
| posted_at | timestamptz | NOT NULL | — |
| is_revoked | boolean | NOT NULL DEFAULT false | 人工撤回标记（BR-06 同步动作可人工撤回） |
| revoked_at / revoked_by | timestamptz / bigint | NULL | 撤回审计 |

### 2.6 巡检诊断域（P0）

#### inspection_rules（巡检规则）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| code | text | NOT NULL, UNIQUE | 规则代码（业务键组成，如 `pod-crashloopbackoff` 风格） |
| name | text | NOT NULL | — |
| category | text | NOT NULL | 规则分类（对齐 k8sgpt analyzer 体系：pod/pvc/deployment/node 等，开放集合） |
| severity_default | text | NOT NULL, CHECK ∈ {info, warning, critical} | 默认严重度（实际判定可覆盖） |
| k8s_version_fit | text | NOT NULL | 版本适配范围（如 `>=1.24`），规则随 K8s 版本维护（对标报告 §6.4） |
| description | text | NULL | 规则说明（可附 AI 解释的规则上下文，A1 链路） |
| enabled | boolean | NOT NULL DEFAULT true | — |
| created_at / updated_at | timestamptz | NOT NULL | — |

#### inspection_policies（巡检策略）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| cluster_id | bigint | NOT NULL, FK → clusters.id | 按领域 ER 1:N 落单集群外键；若需跨集群复用策略，演进为多对多中间表 `[ASSUMPTION]`（验证方式：P0 巡检域详设评审） |
| name | text | NOT NULL | — |
| schedule | text | NOT NULL | 调度表达式（cron） |
| ai_explain_level | text | NOT NULL DEFAULT 'off', CHECK ∈ {off, info, warning, critical} | 该级别及以上触发 AI 解释（BR-09）；P0 无 AI，默认 off；值域 `[ASSUMPTION]`（验证方式：P1 AI 域详设） |
| enabled | boolean | NOT NULL DEFAULT true | — |
| created_at / updated_at | timestamptz | NOT NULL | — |

UNIQUE(cluster_id, name)。`rule_set`（实体字典 §5.1）由中间表 inspection_policy_rules 承载：领域 ER 画为 1:N，但规则库跨策略复用是 k8sgpt analyzer 范式的基本诉求，故落多对多 `[ASSUMPTION]`（验证方式：P0 巡检域详设评审）。

#### inspection_policy_rules（策略-规则包含，中间表）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| policy_id | bigint | PK, FK → inspection_policies.id ON DELETE CASCADE | — |
| rule_id | bigint | PK, FK → inspection_rules.id | — |

#### inspection_runs（巡检执行）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| policy_id | bigint | NOT NULL, FK → inspection_policies.id | — |
| cluster_id | bigint | NOT NULL, FK → clusters.id | 冗余存储，看板按集群聚合免 join `[ASSUMPTION]` |
| trigger | text | NOT NULL DEFAULT 'schedule', CHECK ∈ {schedule, manual} | 触发方式 `[ASSUMPTION]`（验证方式：P0 巡检域详设） |
| status | text | NOT NULL DEFAULT 'running', CHECK ∈ {running, succeeded, failed} | 值域 `[ASSUMPTION]`：领域文档未定义状态机，依据 L4 与异常降级路径（failed 并通知 admin）推导（验证方式：P0 巡检域详设） |
| result | jsonb | NULL | 汇总结果 |
| findings_count | integer | NOT NULL DEFAULT 0 | — |
| error | text | NULL | 失败原因 |
| started_at | timestamptz | NOT NULL | — |
| finished_at | timestamptz | NULL | — |

索引：`idx_inspection_runs_cluster_time(cluster_id, started_at DESC)`。

#### findings（巡检发现）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| run_id | bigint | NOT NULL, FK → inspection_runs.id | — |
| cluster_id | bigint | NOT NULL, FK → clusters.id | 冗余，看板聚合 `[ASSUMPTION]` |
| rule_code | text | NOT NULL | FK 逻辑引用 inspection_rules.code（业务键，领域 §5.2） |
| resource_ref | jsonb | NOT NULL | 结构化资源引用 {kind, namespace, name}；JSONB 参与业务键唯一约束 |
| severity | text | NOT NULL, CHECK ∈ {info, warning, critical} | BR-09 分流依据 |
| raw_error | jsonb | NOT NULL | 结构化原始错误（确定性产出，AI 解释的输入，A1） |
| status | text | NOT NULL DEFAULT 'open', CHECK ∈ {open, acknowledged, in_progress, resolved, ignored, converted_to_alert} | 与领域文档 §6 Finding 状态机严格一致 |
| assignee_id | bigint | NULL, FK → users.id | 认领人 |
| ignored_reason | text | NULL | 忽略原因（状态机：ignored 必填） |
| converted_alert_id | bigint | NULL, FK → alerts.id | 转告警回链（status = converted_to_alert 时非空，BR-09） |
| resolved_at | timestamptz | NULL | — |
| created_at / updated_at | timestamptz | NOT NULL | — |

索引：业务键 `uk_findings_run_rule_resource UNIQUE (run_id, rule_code, resource_ref)`（领域 §5.2）；`idx_findings_status_severity(status, severity)`；`idx_findings_cluster_rule(cluster_id, rule_code)`。

### 2.7 AI 智能体域（P1/P3）

#### ai_tasks（AI 任务，BR-03/BR-05 载体）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| type | text | NOT NULL, CHECK ∈ {explain, investigate, workflow_gen} | 实体字典 §5.1 |
| status | text | NOT NULL DEFAULT 'created', CHECK ∈ {created, sanitizing, running, pending_approval, cancelled, completed, failed, budget_exceeded} | 与领域文档 §6 AITask 状态机严格一致 |
| context_refs | jsonb | NOT NULL | 上下文对象引用（finding/incident/alert 等 id 集合） |
| finding_id | bigint | NULL, FK → findings.id | type=explain 时指向解释对象 |
| incident_id | bigint | NULL, FK → incidents.id | type=investigate 时指向调查对象（领域 ER：可选外键） |
| budget | jsonb | NOT NULL | `{max_calls, max_output_tokens}`；默认值取 BR-03（40 次调用 / 100k 输出 token），管理员可调 |
| calls_used | integer | NOT NULL DEFAULT 0 | 已消耗调用次数 |
| tokens_used | integer | NOT NULL DEFAULT 0 | 已消耗输出 token |
| requires_approval | boolean | NOT NULL DEFAULT false | 高危工具/生成物挂起审批（BR-02/BR-05） |
| requested_by | bigint | NOT NULL, FK → users.id | 发起人 |
| approval_deadline_at | timestamptz | NULL | 审批截止；默认 30min 超时=拒绝（沿用交互文档 §7 已标注的 `[ASSUMPTION]`，P3 上线前校准） |
| approved_by | bigint | NULL, FK → users.id | 审批人 |
| decided_at | timestamptz | NULL | 批准/拒绝时间 |
| result | jsonb | NULL | 产出（RCA 报告 / 解释引用 / 生成的 Workflow 草稿） |
| is_partial | boolean | NOT NULL DEFAULT false | 超预算优雅降级的部分结论标注（BR-03） |
| error | text | NULL | — |
| created_at / updated_at / finished_at | timestamptz | NOT NULL / NOT NULL / NULL | — |

索引：`idx_ai_tasks_status(status)`；`idx_ai_tasks_incident(incident_id)`；`idx_ai_tasks_finding(finding_id)`。

#### ai_mask_mappings（AI 掩码映射，BR-01）

> BR-01：掩码可逆映射**仅存本地**。映射原值属敏感数据，存储必须加密，且严禁外发（BR-12）。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| task_id | bigint | NOT NULL, FK → ai_tasks.id ON DELETE CASCADE | 所属任务（脱敏发生在 sanitizing 阶段） |
| placeholder | text | NOT NULL | 掩码占位符（如 `K8S_MASK_0001` 风格） |
| kind | text | NOT NULL | 掩码类别（namespace/pod/ip/凭据类字段等） |
| encrypted_original | bytea | NOT NULL | **加密后**的原始值（信封加密）；密钥管理方式 `[TBD-INFRA]`（基础设施负责人 / P1 部署设计） |
| created_at | timestamptz | NOT NULL | — |

UNIQUE(task_id, placeholder)。保留期见 §6。

#### ai_explanations（AI 解释，范式 A 产物）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| finding_id | bigint | NOT NULL, UNIQUE, FK → findings.id | 领域 ER：一个 Finding 至多一条当前解释 |
| task_id | bigint | NULL, FK → ai_tasks.id | 产生该解释的任务 |
| sanitized_input_digest | text | NOT NULL | 脱敏输入摘要（sha-256），可复现性校验 |
| output | jsonb | NOT NULL | 结构化诊断 + 修复建议（A1：LLM 返回结构化产物） |
| model | text | NOT NULL | 模型标识（本地优先，BR-12） |
| tokens | integer | NOT NULL | — |
| created_at | timestamptz | NOT NULL | — |

#### ai_call_logs（AI 调用日志，BR-10 全量审计）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| task_id | bigint | NOT NULL, FK → ai_tasks.id | — |
| model | text | NOT NULL | 实际调用的模型 |
| tool_used | text | NULL | 工具标识（A2 循环中的工具调用） |
| prompt_digest | text | NOT NULL | prompt 摘要（sha-256）；**不存明文**，明文含敏感上下文（BR-01/BR-12，见 §6） |
| tokens_in / tokens_out | integer | NOT NULL | 成本计量（BR-10 cost） |
| latency_ms | integer | NOT NULL | — |
| result_code | text | NOT NULL, CHECK ∈ {ok, error, timeout} | 值域 `[ASSUMPTION]`（验证方式：P1 AI 网关详设） |
| error | text | NULL | — |
| created_at | timestamptz | NOT NULL | — |

索引：`idx_ai_call_logs_task(task_id)`；`idx_ai_call_logs_created(created_at)`。只追加（BR-10，同 D-6）。

### 2.8 值班响应域（P2）

#### oncall_schedules（排班表）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| name | text | NOT NULL, UNIQUE | — |
| team | text | NOT NULL | 值班团队 |
| rotation_rules | jsonb | NOT NULL | 轮换规则（成员、周期、顺序） |
| calendar | jsonb | NOT NULL | 排班日历数据（当前排班由此派生） |
| overrides | jsonb | NOT NULL DEFAULT '[]' | 临时顶班 / Out-of-Office（L2） |
| enabled | boolean | NOT NULL DEFAULT true | — |
| created_at / updated_at | timestamptz | NOT NULL | — |

轮换/日历/顶班的内部结构随排班算法详定，先以 JSONB 承载 `[ASSUMPTION]`（验证方式：P2 值班域详设评审；结构固化后再评估拆表）。

#### escalation_policies（升级策略）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| name | text | NOT NULL, UNIQUE | — |
| schedule_id | bigint | NOT NULL, FK → oncall_schedules.id | 领域 ER：策略绑定排班表 |
| levels | jsonb | NOT NULL | `[{level, target, channel, timeout_min}]`（实体字典 §5.1）；各级默认超时与渠道 `[TBD-BIZ]`（业务负责人 / P2 设计前） |
| channel_fallbacks | jsonb | NOT NULL DEFAULT '[]' | 渠道降级链（IM → 短信 → 电话等，BR-13；组合 `[TBD-BIZ]`） |
| enabled | boolean | NOT NULL DEFAULT true | — |
| created_at / updated_at | timestamptz | NOT NULL | — |

#### notification_records（通知记录，BR-08/BR-13 审计）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| channel | text | NOT NULL | 投递渠道（IM/短信/电话 `[TBD-BIZ]`） |
| target | text | NOT NULL | 投递目标（人/群/号码） |
| content_digest | text | NOT NULL | 内容摘要（不存全文，控制敏感面与体积）`[ASSUMPTION]`（验证方式：P2 通知中心详设） |
| status | text | NOT NULL DEFAULT 'queued', CHECK ∈ {queued, sent, failed, acked} | 值域 `[ASSUMPTION]`：领域文档未定义状态机，依据 L2（status=sent、Ack、渠道失败降级）与 BR-08 推导（验证方式：P2 通知中心详设） |
| ack_action | text | NULL | 响应动作（一键 Ack/Escalate/Resolve，L2/对标 OneUptime） |
| ack_at | timestamptz | NULL | — |
| alert_id | bigint | NULL, FK → alerts.id | 触发源：告警 |
| incident_id | bigint | NULL, FK → incidents.id | 触发源：事件 |
| escalation_policy_id | bigint | NULL, FK → escalation_policies.id | 经哪条升级链（领域 ER：策略触发） |
| escalation_level | integer | NULL | 第几级投递（升级留痕，BR-08） |
| error | text | NULL | 失败原因（降级链触发依据，BR-13） |
| created_at | timestamptz | NOT NULL | — |

索引：`idx_notification_records_alert(alert_id)`；`idx_notification_records_incident(incident_id)`；`idx_notification_records_status(status, created_at)`。只追加（审计链，同 D-6）。

### 2.9 流程编排域（P3）

#### workflows（编排定义，BR-05）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| name | text | NOT NULL | — |
| version | integer | NOT NULL | 版本号（A3：新版本入库、diff 预览） |
| yaml | text | NOT NULL | 编排定义 |
| source | text | NOT NULL, CHECK ∈ {manual, ai_generated} | 实体字典 §5.1 |
| approved_by | bigint | NULL, FK → users.id | **CHECK：source='ai_generated' 时必填**（BR-05 落为库级约束；人工确认前不得执行） |
| enabled | boolean | NOT NULL DEFAULT true | — |
| is_current | boolean | NOT NULL DEFAULT true | 当前生效版本 |
| created_by | bigint | NOT NULL, FK → users.id | — |
| created_at / updated_at | timestamptz | NOT NULL | — |

UNIQUE(name, version)；部分唯一索引 `uk_workflows_current UNIQUE (name) WHERE is_current`。按「一版本一行」实现版本历史 `[ASSUMPTION]`（验证方式：P3 编排域详设评审）。

#### workflow_runs（编排执行）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | bigint | PK, IDENTITY | — |
| workflow_id | bigint | NOT NULL, FK → workflows.id | — |
| workflow_version | integer | NOT NULL | 执行时的版本号 |
| yaml_snapshot | text | NOT NULL | 执行快照（可审计可回放）`[ASSUMPTION]`（验证方式：P3 编排域详设） |
| trigger_type | text | NOT NULL, CHECK ∈ {alert, manual, schedule} | 实体字典 §5.1 |
| triggered_by | bigint | NULL, FK → users.id | manual 触发人 |
| alert_id | bigint | NULL, FK → alerts.id | alert 触发上下文 |
| incident_id | bigint | NULL, FK → incidents.id | 事件关联上下文 `[ASSUMPTION]`（验证方式：P3 编排域详设） |
| status | text | NOT NULL DEFAULT 'triggered', CHECK ∈ {triggered, running, waiting_approval, cancelled, succeeded, failed, timeout} | 与领域文档 §6 WorkflowRun 状态机严格一致 |
| steps_log | jsonb | NOT NULL DEFAULT '[]' | 步骤执行日志（含 waiting_approval 的审批步骤） |
| error | text | NULL | — |
| started_at / finished_at | timestamptz | NOT NULL / NULL | — |
| created_at | timestamptz | NOT NULL | — |

索引：`idx_workflow_runs_workflow(workflow_id, created_at DESC)`；`idx_workflow_runs_status(status)`。

## 3. 枚举字典

枚举实现为 `text + CHECK`（§2.1）。**值与领域文档 §6 状态机严格一致**；非状态机来源的枚举单独标注出处。

| 枚举名 | 值 | 来源 |
|---|---|---|
| credential_scope | `readonly` \| `write` | 实体字典 §5.1 Credential |
| cluster_status | `connected` \| `degraded` \| `disconnected` \| `unknown` | `[ASSUMPTION]`（无状态机，按连接健康推导；P0 接入域详设验证） |
| provider_category | `source` \| `query` \| `action` | 实体字典 §5.1 Provider |
| provider_pull_mode | `push` \| `poll` | 实体字典 §5.1 Provider |
| alert_severity | `info` \| `warning` \| `critical` | `[ASSUMPTION]`（值域未定；BR-09 的「warn 以上」= warning/critical；P0 Provider 归一化评审验证） |
| **alert_status** | `received` \| `deduplicated` \| `enriched` \| `correlated` \| `standalone` \| `suppressed` \| `notified` \| `resolved` | 状态机 §6 Alert（8 态） |
| correlation_mode | `auto` \| `candidate` | 实体字典 §5.1（「候选」译 candidate `[ASSUMPTION]`） |
| incident_severity | `P1` \| `P2` \| `P3` \| `P4` | 实体字典 §5.1 Incident |
| **incident_status** | `open` \| `acknowledged` \| `cancelled` \| `mitigated` \| `resolved` \| `closed` | 状态机 §6 Incident（6 态） |
| incident_source | `correlation` \| `manual` | `[ASSUMPTION]`（状态机入口语义；P2 事件域详设验证） |
| incident_candidate_status | `pending` \| `confirmed` \| `rejected` | `[ASSUMPTION]`（BR-04 候选流程；P2 事件域详设验证） |
| finding_severity | `info` \| `warning` \| `critical` | `[ASSUMPTION]`（同 alert_severity） |
| **finding_status** | `open` \| `acknowledged` \| `in_progress` \| `resolved` \| `ignored` \| `converted_to_alert` | 状态机 §6 Finding（6 态） |
| inspection_run_status | `running` \| `succeeded` \| `failed` | `[ASSUMPTION]`（L4 与异常降级路径推导；P0 巡检域详设验证） |
| inspection_run_trigger | `schedule` \| `manual` | `[ASSUMPTION]`（P0 巡检域详设验证） |
| ai_explain_level | `off` \| `info` \| `warning` \| `critical` | `[ASSUMPTION]`（BR-09 分级；P1 AI 域详设验证） |
| ai_task_type | `explain` \| `investigate` \| `workflow_gen` | 实体字典 §5.1 AITask |
| **ai_task_status** | `created` \| `sanitizing` \| `running` \| `pending_approval` \| `cancelled` \| `completed` \| `failed` \| `budget_exceeded` | 状态机 §6 AITask（8 态） |
| ai_call_result_code | `ok` \| `error` \| `timeout` | `[ASSUMPTION]`（P1 AI 网关详设验证） |
| notification_status | `queued` \| `sent` \| `failed` \| `acked` | `[ASSUMPTION]`（L2/BR-08 推导；P2 通知中心详设验证） |
| status_page_visibility | `public` \| `internal` | 实体字典 §5.1 StatusPageEntry |
| action_item_status | `pending` \| `in_progress` \| `done` | `[ASSUMPTION]`（P2 事件域详设验证） |
| workflow_source | `manual` \| `ai_generated` | 实体字典 §5.1 Workflow |
| workflow_run_trigger | `alert` \| `manual` \| `schedule` | 实体字典 §5.1 WorkflowRun |
| **workflow_run_status** | `triggered` \| `running` \| `waiting_approval` \| `cancelled` \| `succeeded` \| `failed` \| `timeout` | 状态机 §6 WorkflowRun（7 态） |

> 加粗枚举为领域状态机的直接落地，值域**禁止**增删改；如需扩展须先修订领域文档并同步本表。

## 4. ER 图（物理表级）

关键索引以 `%% idx:` 注释标注；属性块仅列主键/外键/业务键，全量字段见 §2。

```mermaid
erDiagram
    users ||--o{ user_roles : "user_id"
    roles ||--o{ user_roles : "role_id"
    users ||--o{ audit_logs : "actor_user_id"

    credentials ||--o{ clusters : "credential_id"
    credentials ||--o{ providers : "credential_id (opt)"
    clusters ||--o{ inspection_policies : "cluster_id"
    clusters ||--o{ inspection_runs : "cluster_id (redundant)"
    clusters ||--o{ findings : "cluster_id (redundant)"

    providers ||--o{ alerts : "provider_id"
    maintenance_windows ||--o{ alerts : "suppressed_by_window_id (opt)"

    inspection_policies ||--o{ inspection_policy_rules : "policy_id"
    inspection_rules ||--o{ inspection_policy_rules : "rule_id"
    inspection_policies ||--o{ inspection_runs : "policy_id"
    inspection_runs ||--o{ findings : "run_id"
    findings |o--o| alerts : "converted_alert_id (opt, BR-09)"
    findings ||--o| ai_explanations : "finding_id (unique)"
    findings |o--o{ ai_tasks : "finding_id (opt)"
    ai_tasks ||--o{ ai_mask_mappings : "task_id"
    ai_tasks ||--o{ ai_call_logs : "task_id"
    ai_tasks |o--o{ incidents : "incident_id (opt)"

    correlation_rules ||--o{ incident_candidates : "correlation_rule_id"
    correlation_rules |o--o{ incidents : "correlation_rule_id (opt)"
    incident_candidates |o--o{ incidents : "candidate_id (opt, BR-04)"
    incidents ||--o{ incident_alerts : "incident_id"
    alerts ||--o{ incident_alerts : "alert_id"
    incidents ||--o| postmortems : "incident_id (unique)"
    postmortems ||--o{ postmortem_action_items : "postmortem_id"
    incidents ||--o| status_page_entries : "incident_id (unique)"
    status_page_entries ||--o{ status_page_updates : "entry_id"

    oncall_schedules ||--o{ escalation_policies : "schedule_id"
    escalation_policies |o--o{ notification_records : "escalation_policy_id (opt)"
    alerts |o--o{ notification_records : "alert_id (opt)"
    incidents |o--o{ notification_records : "incident_id (opt)"

    workflows ||--o{ workflow_runs : "workflow_id"
    alerts |o--o{ workflow_runs : "alert_id (opt)"
    users |o--o{ workflow_runs : "triggered_by (opt)"

    %% ============ 实体属性（PK/FK/业务键） ============
    users {
        bigint id PK
        text username UK "idx: uk_users_username"
        text team "TBD-BIZ 团队数据源"
    }
    roles {
        bigint id PK
        text code UK
        jsonb permissions "领域§3 权限矩阵"
    }
    user_roles {
        bigint user_id PK_FK
        bigint role_id PK_FK
        text team_scope
    }
    audit_logs {
        bigint id PK
        bigint actor_user_id FK
        text resource_type "idx: (resource_type, resource_id)"
        text resource_id
        timestamptz created_at "idx: created_at; 只追加 BR-10"
    }
    credentials {
        bigint id PK
        text secret_ref "仅引用密钥管理, 不存凭证值"
        text scope "readonly|write, 默认 readonly BR-02"
    }
    clusters {
        bigint id PK
        text name UK
        bigint credential_id FK
        text status
    }
    providers {
        bigint id PK
        text name UK
        text category "source|query|action"
        jsonb fingerprint_fields
    }
    alerts {
        bigint id PK
        text fingerprint "idx: 部分唯一(活跃) D-1"
        bigint provider_id FK
        text status "状态机 8 态"
        jsonb labels "idx: GIN"
        jsonb raw_payload
        integer occurrence_count "L1 计数合并"
    }
    enrichment_rules {
        bigint id PK
        text name UK
        jsonb matchers
        jsonb mappings "extraction|mapping"
    }
    correlation_rules {
        bigint id PK
        text name UK
        text mode "auto|candidate BR-04"
        integer time_window_seconds
    }
    maintenance_windows {
        bigint id PK
        jsonb scope
        timestamptz ends_at "idx: ends_at; BR-07"
    }
    incident_candidates {
        bigint id PK
        bigint correlation_rule_id FK
        text status "pending|confirmed|rejected"
        jsonb member_alert_ids
    }
    incidents {
        bigint id PK
        text severity "P1-P4"
        text status "状态机 6 态"
        bigint candidate_id FK "opt BR-04"
    }
    incident_alerts {
        bigint incident_id PK_FK
        bigint alert_id PK_FK "idx: alert_id 反查"
    }
    postmortems {
        bigint id PK
        bigint incident_id UK_FK
        jsonb timeline
    }
    postmortem_action_items {
        bigint id PK
        bigint postmortem_id FK
        bigint owner_id FK "opt"
    }
    status_page_entries {
        bigint id PK
        bigint incident_id UK_FK "BR-06"
        text visibility "public|internal"
    }
    status_page_updates {
        bigint id PK
        bigint entry_id FK
        boolean is_revoked "BR-06 撤回"
    }
    inspection_rules {
        bigint id PK
        text code UK
        text severity_default
        text k8s_version_fit
    }
    inspection_policies {
        bigint id PK
        bigint cluster_id FK
        text ai_explain_level "BR-09"
    }
    inspection_policy_rules {
        bigint policy_id PK_FK
        bigint rule_id PK_FK
    }
    inspection_runs {
        bigint id PK
        bigint policy_id FK
        bigint cluster_id FK "idx: (cluster_id, started_at)"
        text status "running|succeeded|failed"
    }
    findings {
        bigint id PK
        bigint run_id FK
        text rule_code "uk: (run_id, rule_code, resource_ref)"
        jsonb resource_ref
        text status "状态机 6 态"
    }
    ai_tasks {
        bigint id PK
        text type "explain|investigate|workflow_gen"
        text status "状态机 8 态"
        bigint incident_id FK "opt"
        bigint finding_id FK "opt"
        jsonb budget "BR-03"
    }
    ai_mask_mappings {
        bigint id PK
        bigint task_id FK "uk: (task_id, placeholder); BR-01 仅本地"
        bytea encrypted_original "加密存储"
    }
    ai_explanations {
        bigint id PK
        bigint finding_id UK_FK
        text sanitized_input_digest
    }
    ai_call_logs {
        bigint id PK
        bigint task_id FK "idx: task_id; 只追加 BR-10"
        text prompt_digest "sha-256 不存明文"
    }
    oncall_schedules {
        bigint id PK
        text name UK
        text team
        jsonb rotation_rules
    }
    escalation_policies {
        bigint id PK
        bigint schedule_id FK
        jsonb levels "TBD-BIZ 超时与渠道"
        jsonb channel_fallbacks "BR-13"
    }
    notification_records {
        bigint id PK
        bigint alert_id FK "opt; idx"
        bigint incident_id FK "opt; idx"
        text status "queued|sent|failed|acked"
    }
    workflows {
        bigint id PK
        text name "uk: (name, version)"
        integer version
        text source "manual|ai_generated"
        bigint approved_by FK "ai_generated 必填 BR-05"
    }
    workflow_runs {
        bigint id PK
        bigint workflow_id FK
        text status "状态机 7 态"
        text yaml_snapshot
    }
```

## 5. 关键设计决策

| # | 决策 | 说明 |
|---|---|---|
| D-1 | **alerts 指纹唯一采用部分唯一索引**：`UNIQUE(fingerprint) WHERE status <> 'resolved'`，命中即 `occurrence_count += 1` 并刷新 `last_occurred_at`（L1 去重）。 | 纯全局 UNIQUE 会让「已恢复后复发」的同指纹告警永远并入历史记录，丢失新告警语义；部分唯一索引限定**活跃周期内**唯一，resolved 后同指纹再现开新记录。Redis 仅做热路径判重缓存，正确性以本索引兜底。 |
| D-2 | **凭证永不落库**：`credentials` 表只存 `secret_ref`（外部密钥管理引用）；providers.config 禁止写入密钥值（代码审查 + secret_scan 拦截）。 | 领域文档 §8 凭据安全红线；BR-02。 |
| D-3 | **JSONB 承载半结构化字段**：labels / enrichments / raw_payload / matchers / mappings / conditions / levels / rotation_rules / steps_log / context_refs / budget 等。 | 告警标签与规则条件天然 schema-free（Keep 实践）；`labels` 建 GIN 索引支撑富化/关联检索。结构固化且需强约束的字段（如未来排班算法）再评估拆表。 |
| D-4 | **时间一律 `timestamptz` UTC**。 | 领域文档 §5.2。 |
| D-5 | **业务键与主键分离**：主键均为代理键 `id`；对外/跨系统用业务键（alerts.fingerprint、findings 的 run_id+rule_code+resource_ref、inspection_rules.code），并建唯一约束。 | 领域文档 §5.2。 |
| D-6 | **审计只追加**：`audit_logs`、`ai_call_logs`、`notification_records` 不提供 UPDATE/DELETE 路径（应用层无接口 + 库权限 `REVOKE UPDATE, DELETE`），保留期内不可删改。 | BR-10 / BR-08。归档迁移策略见 §6 `[TBD-BIZ]`。 |
| D-7 | **删除策略分两类**：① 配置类（clusters、providers、enrichment_rules、correlation_rules 等）用 `deleted_at` 软删——下游流水（alerts/findings 等）持有其外键，物理删除会破坏审计链；② 流水类（alerts、findings、inspection_runs、ai_call_logs、notification_records 等）不删，走保留期清理/归档（§6）；③ users/roles 用 `is_active`/状态化停用。 | 软删字段必须从所有唯一约束的可见集合排除（查询默认 `deleted_at IS NULL`）。 |
| D-8 | **候选事件独立表**（incident_candidates），确认后才写 incidents：保持 `incident_status` 与领域状态机严格一致（open 即已立项），驳回原因结构化留存供规则调优（BR-04）。 | 见 §2.5 表头说明。 |
| D-9 | **高增长表预留按月 RANGE 分区**：alerts、audit_logs、ai_call_logs、notification_records、findings、inspection_runs、workflow_runs。分区键 `created_at`，保留期确定后落地（§6 `[TBD-BIZ]`）。 | `[ASSUMPTION]` 非功能 §8 性能项待容量规划验证；建表即用分区模板（或 PG 原生分区）可避免后期在线改造，代价可接受（验证方式：容量规划 + P0 建库评审）。 |
| D-10 | **BR 落库为库级/行级约束**：workflows 的 `source='ai_generated' → approved_by NOT NULL`（BR-05）；alerts.status='suppressed' → suppressed_by_window_id NOT NULL（BR-07）；incidents.status='cancelled' → cancelled_reason NOT NULL（状态机「记录原因」）；findings.status='ignored' → ignored_reason NOT NULL。 | 能用约束表达的护栏不依赖应用层自觉；其余流程性 BR（预算、审批流）由应用层保证并落 audit_logs。 |
| D-11 | **巡检策略-规则为多对多中间表**（inspection_policy_rules）：领域 ER 画为 1:N，但规则库跨策略复用是 k8sgpt analyzer 移植的基本诉求。 | `[ASSUMPTION]` 偏离领域 ER 形态，已在 §2.6 标注验证方式（P0 巡检域详设评审，确认后回流领域文档修订）。 |

## 6. 数据保留与脱敏

### 6.1 保留策略

| 数据 | 保留策略 | 依据 |
|---|---|---|
| alerts.raw_payload | 告警行保留期内保留原文；期满后可降级为仅保留 labels/指纹摘要 | 保留天数 `[TBD-BIZ]`（业务负责人 / P0 上线前） |
| alerts / findings / inspection_runs / notification_records / workflow_runs | 流水保留期后归档或清理（分区 DROP，D-9） | 保留天数 `[TBD-BIZ]`（业务负责人 / 对应阶段上线前） |
| audit_logs / ai_call_logs | 保留期内**不可删改**（BR-10）；期满归档迁移至冷存储（归档介质与年限 `[TBD-BIZ]`，安全合规负责人确认） | BR-10 |
| ai_mask_mappings | 随任务生命周期保留至脱敏还原不再需要；建议任务结束后短期清理以缩小敏感面，具体天数 `[TBD-BIZ]`（安全合规负责人 / P1 设计前） | BR-01 |

保留期数值领域文档均未规定，一律 `[TBD-BIZ]`，禁止臆造；确定后回填本节。

### 6.2 脱敏与数据边界

| 措施 | 落库设计 | 依据 |
|---|---|---|
| AI 掩码映射仅存本地 | `ai_mask_mappings.encrypted_original` 加密（bytea）存于平台 PG，**不出域、不外发**；密钥管理 `[TBD-INFRA]` | BR-01 |
| 脱敏字段不外发 | 发往外部模型的请求体不落库；`ai_call_logs` 只存 `prompt_digest`（sha-256）不存明文 | BR-12、§2.7 |
| 凭证不入库不入日志 | `secret_ref` 引用制（D-2）；audit_logs.detail 记录变更摘要时排除凭据字段 | 领域文档 §8 |
| 通知内容最小化 | `notification_records.content_digest` 只存摘要不存全文 | §2.8 |
| 数据出域开关 | 模型路由与出域策略为 AI 网关行为（BR-12 `[TBD-BIZ]`），数据层不存明文 prompt，出域与否不改变本节约束 | BR-12 |

## 7. 分期落地顺序

与领域文档 §2 分期一致；每阶段建表后用迁移工具（如 Alembic）版本化，先于对应链路联调。

| 阶段 | 新建表 | 支撑链路（交互文档 §5） |
|---|---|---|
| **P0**（14 张） | users、roles、user_roles、audit_logs、credentials、clusters、providers、alerts、enrichment_rules、inspection_rules、inspection_policies、inspection_policy_rules、inspection_runs、findings | L1（接入+去重+富化）、L4（无 AI）、IAM 与审计（BR-02/BR-09/BR-10 的 P0 部分） |
| **P1**（+4 张） | ai_tasks、ai_mask_mappings、ai_explanations、ai_call_logs | A1（解释）、L4 接入 A1（BR-01/BR-03/BR-12 的 P1 部分） |
| **P2**（+12 张） | correlation_rules、maintenance_windows、incident_candidates、incidents、incident_alerts、postmortems、postmortem_action_items、status_page_entries、status_page_updates、oncall_schedules、escalation_policies、notification_records | L1（关联）、L2（升级）、L3（事件闭环）（BR-04/BR-06/BR-07/BR-08/BR-13） |
| **P3**（+2 张） | workflows、workflow_runs | A2、A3、Workflow 引擎（BR-05） |

> 合计 32 张。P4（AI 修复 PR、窄路径处置）实体按领域文档 §2 暂不细化，届时增补。

## 8. 领域模型追溯表

物理表 ↔ 领域实体（`02-business-design/01-domain-model.md` §5.1）一一映射：

| 领域实体 | 分期 | 物理表 | 备注 |
|---|---|---|---|
| Cluster | P0 | clusters | — |
| Credential | P0 | credentials | 仅存引用（D-2） |
| Provider | P0 | providers | — |
| Alert | P0 | alerts | 多对多关联经 incident_alerts |
| EnrichmentRule | P0 | enrichment_rules | — |
| CorrelationRule | P2 | correlation_rules | — |
| Incident | P2 | incidents | 候选态独立表（D-8） |
| —（Incident↔Alert 关联） | P2 | incident_candidates、incident_alerts | 候选表为 BR-04 落库新增 `[ASSUMPTION]` |
| Postmortem | P2 | postmortems、postmortem_action_items | action_items 拆子表 `[ASSUMPTION]` |
| StatusPageEntry | P2 | status_page_entries、status_page_updates | updates 拆子表 `[ASSUMPTION]` |
| InspectionRule | P0 | inspection_rules | — |
| InspectionPolicy | P0 | inspection_policies、inspection_policy_rules | rule_set 落多对多（D-11） |
| InspectionRun | P0 | inspection_runs | — |
| Finding | P0 | findings | — |
| AIExplanation | P1 | ai_explanations | — |
| AITask | P1/P3 | ai_tasks | — |
| AICallLog | P1 | ai_call_logs | — |
| —（BR-01 掩码映射） | P1 | ai_mask_mappings | BR-01 落库新增 `[ASSUMPTION]` |
| —（BR-07 维护窗口） | P2 | maintenance_windows | BR-07 落库新增 `[ASSUMPTION]` |
| OnCallSchedule | P2 | oncall_schedules | — |
| EscalationPolicy | P2 | escalation_policies | levels 以 JSONB 承载 |
| NotificationRecord | P2 | notification_records | — |
| Workflow | P3 | workflows | 版本化存储 `[ASSUMPTION]` |
| WorkflowRun | P3 | workflow_runs | — |
| User / Role | P0 | users、roles、user_roles | 授予多对多经 user_roles |
| AuditLog | P0 | audit_logs | 只追加（D-6） |

追溯校验：领域实体字典 24 个实体（21 个单列实体 + User / Role / AuditLog）全部覆盖，无遗漏；新增 6 张表（incident_candidates、incident_alerts、postmortem_action_items、status_page_updates、ai_mask_mappings、maintenance_windows）均为关系表或 BR 条款落库，来源已在备注标注。

## 9. 开放问题

| 标记 | 问题 | 确认人 / 阶段 |
|---|---|---|
| `[TBD-INFRA]` | Redis 部署形态（缓存/队列用途的实例规划） | 基础设施负责人 / P0 部署设计 |
| `[TBD-INFRA]` | 已有可观测栈与工单系统对接方式（决定是否需要补充集成表） | 基础设施负责人 / P0 设计前 |
| `[TBD-INFRA]` | 掩码映射加密的密钥管理方式（信封加密 KMS 选型） | 基础设施负责人 / P1 部署设计 |
| `[TBD-INFRA]` | 用户认证方式（SSO/LDAP），决定 users 是否需补充外部身份字段 | 基础设施负责人 / P0 部署设计 |
| `[TBD-BIZ]` | raw_payload 与各流水表保留天数、audit_logs 归档年限 | 业务负责人、安全合规负责人 / 对应阶段上线前 |
| `[TBD-BIZ]` | 团队/服务归属数据源（users.team 建模走向） | 业务负责人 / P0 设计前 |
| `[TBD-BIZ]` | 升级链各级默认超时与渠道组合、状态页受众默认可见性 | 业务负责人 / P2 设计前 |
| `[ASSUMPTION]` | 全部枚举值域（非状态机部分）、软删/分区/版本化等技术演绎 | 见 §3 与 §5 各条标注的验证方式，随对应阶段详设评审收敛 |
