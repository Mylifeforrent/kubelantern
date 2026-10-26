# KubeLantern 文档地图与规范

> 本文件是 `docs/` 的唯一入口与状态台账。新文档合入时必须同步更新本页索引。

## 1. 目录体系

一级目录**按研发生命周期编号分组**（对齐调研 → 业务 → 技术 → 契约 → 测试 → 发布 → 运维 → 复盘的时间线，新人可按序阅读；序号留有空位，插入新阶段不重排）。编号分组依据业界实践调研：ADR / Rust RFC 用编号承载时序与唯一性，Google SRE 规定复盘文档规范化沉淀，Diátaxis 建议面向使用者的手册类内容按主题组织（本仓库 `07-runbooks/` 内部适用）。

| 目录 | 阶段职责 | 状态 |
|---|---|---|
| `01-research/` | 调研与竞品对标分析（立项输入） | ✅ 已有内容 |
| `02-business-design/` | 业务设计：业务范围、角色、领域模型、交互链路、业务规则 | ✅ 已有内容 |
| `03-tech-design/` | 技术设计：系统架构（HLD）、模块详细设计（LLD）、架构决策记录（ADR） | ✅ 已有内容 |
| `04-api/` | API 契约（以 OpenAPI spec 为单一事实源，文档只做链接与说明） | ✅ 已有内容 |
| `05-qa/` | 测试计划、用例、测试报告 | ✅ 已有内容 |
| `06-release/` | 发布/部署计划、变更记录、回滚预案；本地 kind 演示环境 | ✅ 已有内容 |
| `07-runbooks/` | 运维手册与应急处置 SOP（`runbook-writer` agent 输出目录） | 📋 规划中 |
| `08-postmortems/` | 事故复盘，一篇一事，命名 `<日期>-<事件名>.md`（`runbook-writer` agent 输出目录） | 📋 规划中 |

> 状态为「规划中」的目录暂不创建空壳，用到时再建并更新本表。
>
> 本地演示环境入口：`deploy/README.md`（kind 3 节点集群 + Helm + 示例工程 + 端到端验收）。
>
> 开发与部署指南：`../DEVELOPMENT.md`；产品介绍与功能演示：`../README.md`。

## 2. 文档索引（状态台账）

| 文档 | 标题 | 状态 | 最近更新 |
|---|---|---|---|
| `01-research/01-benchmark-report.md` | 企业 SRE 运维平台开源对标分析报告 | accepted | 2026-10-24 |
| `01-research/01-benchmark-report.html` | 同上（HTML 演示版） | accepted | 2026-10-24 |
| `02-business-design/01-domain-model.md` | 业务建模：领域模型与业务规则 | accepted | 2026-10-24 |
| `02-business-design/02-interaction-flows.md` | 交互链路设计 | accepted | 2026-10-24 |
| `02-business-design/03-clickable-prototype.html` | 可点击交互原型（Keep 风格亮色版，覆盖关键页面与操作流） | accepted | 2026-10-24 |
| `03-tech-design/01-data-model.md` | 数据模型设计 | accepted | 2026-10-24 |
| `03-tech-design/02-architecture.md` | 整体架构设计（HLD） | accepted | 2026-10-24 |
| `03-tech-design/03-frontend-design.md` | 前端设计与技术栈 | accepted | 2026-10-24 |
| `03-tech-design/04-backend-design.md` | 后端设计与技术栈 | accepted | 2026-10-24 |
| `03-tech-design/05-fe-be-boundary.md` | 前后端开发边界 | accepted | 2026-10-24 |
| `04-api/openapi.yaml` | API 契约（OpenAPI 3.1，阶段一临时单一事实源，文件名序号例外见其 README §2.1） | accepted | 2026-10-25 |
| `02-business-design/04-hifi-design-spec.md` | 高保真设计规范（自可点击原型提取的设计系统） | accepted | 2026-10-24 |
| `04-api/README.md` | API 契约说明（治理、端点总览、约定速览、验证方法） | accepted | 2026-10-25 |
| `02-business-design/05-prd.md` | 产品需求文档（PRD）：产品全貌汇总与开放问题总清单 | accepted | 2026-10-24 |
| `05-qa/01-fe-be-integration-report.md` | 前后端联调报告（页面/端点矩阵、缺陷修复、契约补录、遗留问题） | accepted | 2026-10-25 |
| `06-release/01-kind-demo-cluster.md` | 本地 3 节点 kind 演示集群 | accepted | 2026-10-25 |
| `06-release/02-build-and-deploy.md` | 镜像构建与 Helm 部署 | accepted | 2026-10-25 |
| `06-release/03-feature-acceptance.md` | 功能验收与手工体验 | accepted | 2026-10-25 |
| `06-release/04-troubleshooting.md` | 排障与清理 | accepted | 2026-10-25 |
| `06-release/05-self-test-handbook.html` | 全功能自测操作手册（环境、kind 集群、故障注入、告警/巡检/事件/AI/RBAC 与架构原理） | accepted | 2026-10-26 |

## 3. 命名与编号规范

- **目录**：`NN-kebab-case`，两位序号（`01`、`02`…），小写连字符，全英文。
- **文件**：目录内两位序号 + kebab-case，如 `02-business-design/01-domain-model.md`；复盘文件用 `<日期>-<事件名>.md`；ADR 用四位零填充编号（`0001-verb-object.md`），编号永不复用。
- **文档头**：每篇文档头部含元信息块（状态 / 日期 / 依据 / 读者）。

## 4. 治理规则

1. **状态生命周期**：`draft`（起草）→ `in-review`（评审中）→ `accepted`（定稿）。`accepted` 文档原则上不再大改；实质性修正另立新篇，旧篇在本台账标注 `superseded`。
2. **单一事实源**：一个主题只在一处维护。API 以 `04-api/` 的 OpenAPI spec 为准；调研结论只在 `01-research/`；业务规则只在 `02-business-design/01-domain-model.md`（BR-xx 编号），其他文档引用编号不复制内容。
3. **缺失事实标记**：业务事实缺失标 `[ASSUMPTION]`（附验证方式），待确认标 `[TBD-BIZ]` / `[TBD-UX]` / `[TBD-FE]` / `[TBD-BE]` / `[TBD-INFRA]` 并写明确认人与阶段；不编造。
4. **复盘回流**：`08-postmortems/` 的 Action Items 回流到 `02-business-design/`（规则）与 `07-runbooks/`（操作），形成闭环。
5. **本台账随文档变更同步更新**；文档新增/改状态而未更新本页视为未完成。
