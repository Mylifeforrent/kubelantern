# 后端设计与技术栈

| 元信息 | |
|---|---|
| 状态 | accepted |
| 日期 | 2026-10-24 |
| 依据 | `docs/README.md`（治理规则）、`02-business-design/01-domain-model.md`（子域 §4、权限矩阵 §3、状态机 §6、BR-01~13、非功能 §8）、`02-business-design/02-interaction-flows.md`（L1-L4 / A1-A3、§6 异常降级）、`03-tech-design/01-data-model.md`（32 张表、枚举、D-1~D-11，存储模型唯一事实源）、`03-tech-design/02-architecture.md`（HLD：模块化单体 + arq worker、双部署单元、5 条队列、AI 网关唯一出域口、SSE 倾向） |
| 读者 | 后端研发、全栈研发 |

> 业务规则只引用 BR-xx 编号，唯一事实源为 `02-business-design/01-domain-model.md` §7。表结构、索引、枚举、保留策略唯一事实源为 `03-tech-design/01-data-model.md`，本文不重复、只引用（表名与 D 决策编号）。部署形态、队列划分、ADR 编号沿 `03-tech-design/02-architecture.md`，本文是其后端侧细化。技术栈为项目冻结结论，只展开不重选。凡上游未规定的技术演绎，标 `[ASSUMPTION]`（附验证方式）或 `[TBD-*]`（附确认人/阶段）。

---

## 1. 技术栈展开

### 1.1 总则与版本锁定

- 语言 **Python ≥ 3.12**，Web 框架 **FastAPI**，包管理 **uv**，任务队列 **arq**，存储 **PostgreSQL + Redis**，DB 访问 **SQLAlchemy 2.x（async）+ asyncpg + Alembic**——均为 HLD §3.1 与仓库根 `AGENTS.md` 的冻结结论。
- **版本锁定原则**（ADR-0008）：一切依赖版本以 `uv.lock` 为单一事实源，P0 首次构建时锁定当期稳定版并登记 ADR-0008；升级必须走 PR + 锁文件 diff + 项目验证命令。本文出现的所有具体版本号一律 `[TBD-INFRA]`（基础设施负责人 / P0 工程化），不编造。
- **依赖引入红线**（项目 `AGENTS.md`）：第三方依赖引入必须先过依赖审计；下文标「候选」的依赖在 P0 工程化评审通过前不进入 `pyproject.toml`。

| 类别 | 依赖 | 状态 |
|---|---|---|
| 已冻结（HLD/项目规则） | `fastapi`、`uvicorn`、`arq`、`redis`（async）、`sqlalchemy[asyncio]`、`asyncpg`、`alembic`、`kubernetes`、`pydantic`（v2，随 FastAPI） | 版本 `[TBD-INFRA]` |
| 已冻结（本文展开必需） | `pydantic-settings`（配置，§6.3）、`pytest`、`httpx`（测试栈） | 版本 `[TBD-INFRA]` |
| 候选（须过依赖审计 `[ASSUMPTION]`，验证方式：P0 工程化评审） | `structlog`（或标准库 JSON formatter）、`croniter`（策略 cron 判定）、`import-linter`（边界静态检查，ADR-0011）、`testcontainers`（或 fixture DB）、`fakeredis`、`pytest-asyncio` 或 `anyio` 插件 | 引入前逐项审计 |

### 1.2 uv 项目与依赖管理

- 仓库根 `pyproject.toml`（PEP 621 `[project]`）+ `uv.lock`，两者提交仓库；**禁止** pip 手写 `requirements.txt`，**禁止** poetry（项目规则）。
- 依赖组：运行依赖进 `[project.dependencies]`；开发依赖进 PEP 735 `[dependency-groups]` 的 `dev` 组（pytest/httpx/lint 等）。
- 常用命令：`uv add <pkg>` / `uv add --group dev <pkg>` 增依赖；`uv sync` 本地安装；部署安装必须 `uv sync --locked`（锁文件不一致即失败）；运行统一 `uv run <entry>`。
- 入口脚本经 `[project.scripts]` 暴露：`huntai-api`（api 部署单元入口）与 `huntai-worker`（worker 部署单元入口，接受队列组参数）——与「同镜像多角色」（ADR-0009）配合，镜像 entrypoint 默认 `huntai-api`，worker 以启动命令选择队列组 `[ASSUMPTION]`（验证方式：P0 部署联调，同一镜像双角色冒烟）。

### 1.3 FastAPI 应用工厂与双入口

- **工厂模式**：`create_app(settings) -> FastAPI`，测试可注入不同 Settings 与 lifespan 资源；模块级 `app = create_app()` 供 uvicorn 加载。

```python
# src/huntai/app/main.py（示意）
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="huntai-sre API", version="0.1.0",
                  lifespan=lifespan, ...)
    app.state.settings = settings
    app.include_router(api_v1_router, prefix="/api/v1")   # §4.1 路由聚合
    return app
```

- **lifespan 资源**：SQLAlchemy async engine 与 sessionmaker、Redis client、arq 任务池（`ArqRedis`，API 侧只投递不消费）、富化/关联规则缓存、SSE hub。资源挂 `app.state`，依赖注入经 `request.app.state` 获取，禁止模块级全局单例（可测试性）。
- **双入口**（HLD §6.1，同一镜像不同命令）：
  - api：`uvicorn huntai.app.main:app --host 0.0.0.0 --port 8000`，含路由、webhook 接入、SSE、静态资源；不消费任务队列。
  - worker：`arq huntai.workers.settings.<XxxWorker>`（§1.7），按队列分组启动。
- 中间件注册顺序（外→内）：`request_context`（actor/trace_id 注入，§6.2）→ `rate_limit`（仅 webhook 路由生效）→ 路由。访问日志由 `request_context` 中间件统一产出（§6.1）。

### 1.4 Pydantic v2 DTO 分层

DTO 分三层，**禁止** ORM 模型直接充当 response model（防字段泄漏）：

| 层 | 命名 | 位置 | 规则 |
|---|---|---|---|
| request | `XxxCreateRequest` / `XxxUpdateRequest` / `XxxQueryParams` | `domains/<x>/schemas/request.py` | 只含客户端可提交字段；校验规则（长度/枚举/条件必填）在此表达 |
| response | `XxxResponse` / `XxxDetailResponse` / `Page[XxxResponse]` | `domains/<x>/schemas/response.py` | `model_config = ConfigDict(from_attributes=True)`；敏感字段（`secret_ref`、`encrypted_original`、`raw_payload` 中凭据类内容等）**禁止**出现 |
| internal | 领域对象（dataclass / TypedDict） | `domains/<x>/` | service 与管道段的内部传参；入队载荷也用它约束（如 `IngestJob(alert_id: int)`） |

- Pydantic v2 语法基线：`model_dump()` / `model_validate()` / `ConfigDict`；不使用 v1 兼容层。
- 状态机字段的合法迁移在 **service 层**校验（§3 各域），DTO 只做值域校验（枚举与领域状态机值域严格一致，01-data-model §3）。

### 1.5 SQLAlchemy 2.0 async 数据访问

- 全量 32 张表的 ORM 模型与 `01-data-model.md` §2 一一对应，按域分文件（`domains/<x>/models.py`），**不复制表结构定义到本文**；枚举列实现为 `text + CHECK`（01-data-model §2.1），ORM 侧用 `str` Enum + `native_enum=False`，CHECK 约束在 Alembic 迁移中显式声明（autogenerate 不识别，见 §1.6）。
- 2.0 声明风格：`DeclarativeBase` + `Mapped[...]` / `mapped_column(...)`；时间列一律 `DateTime(timezone=True)`（D-4）。
- 引擎与会话：`create_async_engine(DATABASE_URL, pool_size=..., max_overflow=...)` + `async_sessionmaker(engine, expire_on_commit=False)`。事务边界：
  - API 请求：每请求一个事务（`get_session` 依赖 yield session，成功 commit、异常 rollback）；业务变更与审计写入**同一事务**（§6.2）。
  - worker 任务：管道/巡检等长任务按「段」开短事务（段间状态落库，HLD §2 说明），不做跨段大事务。
- 计数与并发：`occurrence_count` 等计数只允许 SQL 原子表达式（`occurrence_count + 1`），**禁止** read-modify-write。
- 性能约定：热路径查询走 01-data-model 已定索引（如 `idx_alerts_status_severity`、GIN `idx_alerts_labels`）；新增查询在代码评审时对照索引清单，缺索引属 01-data-model 增补项（见 §4.2 团队过滤的标注）。

### 1.6 Alembic 迁移纪律

- 迁移目录 `migrations/`（仓库根），`alembic.ini` 指向 `src/huntai` 的模型元数据；`alembic revision --autogenerate` 生成后**必须人工审查**——部分唯一索引（D-1）、CHECK 约束（枚举值域）、`REVOKE UPDATE, DELETE`（D-6）autogenerate 不识别，必须手写。
- 纪律（必须遵守）：
  1. 一条迁移一个变更意图；文件名保留 alembic revision id + 意图描述。
  2. 已合入 main 的迁移文件**禁止**修改；修正走新迁移。
  3. 每条迁移必须提供可执行的 `downgrade`。
  4. 迁移序列对齐 01-data-model §7 分期：P0 建库迁移（14 张）→ P1（+4）→ P2（+12）→ P3（+2）；建表即含 D-1/D-10 的约束与 D-9 分区模板（分区落地时机沿 01-data-model D-9 `[TBD-BIZ]`）。
  5. D-6 的 `REVOKE UPDATE, DELETE ON audit_logs / ai_call_logs / notification_records` 写入首次建表迁移；后续涉及这三张表的迁移必须重放权限语句。
  6. 迁移执行时机：部署流水线在 api 启动前执行 `alembic upgrade head`（编排细节 `[TBD-INFRA]`，基础设施负责人 / P0 部署设计）。

### 1.7 arq worker 编排

- 队列与分组沿 HLD §6.1 的 5 条队列，不新增队列名。每个队列一个 `WorkerSettings` 类（公共基类注入 Redis/DB/缓存 on_startup）：

```python
# src/huntai/workers/settings.py（示意）
class AlertPipelineWorker(BaseWorkerSettings):
    queue_name = "q-alert-pipeline"
    functions = [alert_process_pipeline]
    cron_jobs = [cron(replay_scan, minute=None),               # 回放扫描
                 cron(maintenance_close_windows, minute=None)]  # 窗口结束扫描 BR-07
    job_timeout = 60        # 秒 [ASSUMPTION]（P0 压测校准）
    max_tries = 3

class EscalationWorker(BaseWorkerSettings):
    queue_name = "q-escalation"
    functions = [escalation_check_ack]
    cron_jobs = [cron(escalation_timeout_sweep, minute=None)]   # 升级链兜底扫描
    ...
```

- 任务命名：`<域>.<动作>` 点号命名空间（`alert.process_pipeline`、`inspection.run`、`inspection.schedule_tick`、`cluster.probe`、`ai.execute_task`、`approval.scan_timeouts`、`notify.dispatch`、`escalation.check_ack`、`replay.scan`、`maintenance.close_windows`）`[ASSUMPTION]`（验证方式：P0 工程化评审固化清单）。
- 任务载荷：只传 id 与少量参数（如 `alert_id`、`policy_id`），数据由 worker 自取；**禁止**大 payload 进 Redis。
- 超时与重试按任务类别配置 `[ASSUMPTION]`（P0 压测校准）：管道任务 `max_tries=3`；巡检 `job_timeout` 放宽（多集群拉取长任务）；AI 任务不框架级自动重试（预算语义，BR-03），A1 失败重试 1 次为业务层重试（沿交互文档 §7 已标 `[ASSUMPTION]`）。
- cron 归属：巡检调度 tick、集群探活 → q-inspection 组；升级兜底扫描 → q-escalation 组；回放/维护窗口扫描 → q-alert-pipeline 组；审批超时扫描（HLD §5.4）→ q-ai 组。多副本部署时 cron 触发以 PG advisory lock 防重 `[ASSUMPTION]`（验证方式：P0 工程化评审）。
- **延迟任务**：arq `enqueue_job(..., _defer_by=timedelta)` 用于升级链各级超时检查（§3.5）；审批超时不用延迟任务，沿 HLD §5.4 用 cron 扫描 `ai_tasks.approval_deadline_at`。
- API 侧投递：`app.state.arq_pool.enqueue_job(name, *args, _queue=...)`；队列名常量收敛在 `core/config.py`，禁止散落字符串。

### 1.8 测试栈

- `pytest` + `httpx`（`AsyncClient(transport=ASGITransport(app=...))` 直连 ASGI，不起真实端口）+ `pytest-asyncio`/`anyio` 插件（二选一 `[ASSUMPTION]`，P0 工程化定）+ `pytest-cov`。
- 目录 `tests/{unit,integration,e2e_flows}`，策略见 §7。所有测试命令收敛进 `pyproject.toml` 的 dev 组脚本与 CI（具体 CI 平台 `[TBD-INFRA]`，基础设施负责人 / P0 工程化）。

## 2. 工程结构

### 2.1 目录树

```text
huntai-sre/
├── pyproject.toml              # uv 项目定义（依赖 + dev 依赖组，§1.2）
├── uv.lock                     # 锁文件，版本唯一事实源（ADR-0008）
├── .env                        # 运行配置（已 gitignore，§6.3）
├── alembic.ini
├── migrations/                 # Alembic 迁移（env.py + versions/，§1.6）
├── src/huntai/
│   ├── app/                    # ── 应用层（api 部署单元，§1.3）──
│   │   ├── main.py             # create_app() 工厂 + 入口
│   │   ├── deps.py             # get_session / get_current_user / require_perm
│   │   ├── middleware/         # request_context（actor/trace_id）、rate_limit
│   │   ├── openapi.py          # OpenAPI 导出（§4.5）
│   │   └── routers/            # 薄路由层：webhooks / alerts / incidents /
│   │                           # inspections / findings / oncall / ai_tasks /
│   │                           # workflows / clusters / notifications / iam / stream
│   ├── domains/                # ── 领域模块（按子域，§3）──
│   │   ├── alerts/             # models / schemas / repository / service
│   │   ├── incidents/
│   │   ├── inspections/
│   │   ├── oncall/
│   │   ├── ai/
│   │   ├── workflows/          # P3，模块隔离（ADR-0010）
│   │   ├── clusters/           # 含 connector.py（只读 K8s 连接池 + 探活）
│   │   ├── notifications/
│   │   └── iam/                # 用户/角色 + record_audit（§6.2）
│   ├── pipeline/               # ── L1 管道（告警管理域执行面，§3.2）──
│   │   ├── normalizer.py       # payload 归一化 + fingerprint 计算（纯函数）
│   │   ├── dedup.py            # upsert 判重与合并（D-1）
│   │   ├── enrich.py           # 富化规则匹配（纯函数）
│   │   └── correlate.py        # 关联引擎（BR-04）
│   ├── workers/                # ── arq 任务（worker 部署单元，§1.7）──
│   │   ├── settings.py         # 5 个 WorkerSettings（按队列分组）
│   │   ├── context.py          # WorkerContext：session/redis/缓存工厂
│   │   └── tasks/              # alert_pipeline / inspection / ai_tasks /
│   │                           # notification / replay
│   ├── gateway/                # ── AI 网关（唯一模型出域口，ADR-0004，§3.4）──
│   │   ├── gateway.py          # AIGateway 主流程
│   │   ├── sanitizer.py        # 脱敏与本地还原（BR-01）
│   │   ├── router.py           # 模型路由（BR-12）
│   │   ├── budget.py           # 预算检查（BR-03）
│   │   ├── circuit.py          # NoAI 熔断（ADR-0005）
│   │   └── providers/          # ModelProvider 抽象：base / local / external
│   ├── realtime/               # ── 实时推送（SSE，§5）──
│   │   ├── hub.py              # Redis Stream 发布 / 订阅 / 回放
│   │   └── payloads.py         # 事件载荷构造
│   └── core/                   # ── 横切（无业务依赖，被所有层引用）──
│       ├── config.py           # pydantic-settings（读 .env，§6.3）
│       ├── db.py / redis.py    # engine / sessionmaker / arq pool
│       ├── context.py          # contextvar：actor / trace_id
│       ├── logging.py          # 结构化日志（§6.1）
│       ├── security.py         # 认证抽象 + 权限依赖工厂（§4.2）
│       ├── pagination.py       # 分页/排序解析（§4.3）
│       └── errors.py           # RFC 7807 problem（§4.4）
└── tests/
    ├── unit/  ├── integration/  └── e2e_flows/
```

包名采用复数形式（`incidents`、`workflows` 等），与 HLD §6.2 模块清单一一对应（`incident`→`incidents`、`cluster_access`→`clusters` 等），属命名统一非结构变更 `[ASSUMPTION]`（验证方式：P0 工程化评审一并固化）。

### 2.2 模块 import 边界（ADR-0011 / ADR-0010）

**规则**（以 import 静态检查拦截，工具候选 `import-linter`，引入须过依赖审计 `[ASSUMPTION]`，ADR-0011 固化）：

| 方向 | 规则 |
|---|---|
| `app` → `domains` / `pipeline` / `gateway` / `realtime` / `core` | 允许（路由只调 service，禁止触 repository/models） |
| `workers` / `pipeline` / `gateway` → `domains`（service 公开接口）+ `core` | 允许 |
| `domains/X` → `domains/Y` | 仅允许 import Y 的 `service.py` 公开函数（跨域表访问一律经对方 service）；**禁止** import 对方 `models` / `repository` |
| `domains/*` → `workers` / `pipeline` / `gateway` / `app` | **禁止**（执行面不反向依赖领域） |
| `core` → 任何业务模块 | **禁止**（core 零依赖；audit_logs 写入在 `domains/iam/service.py`，core 只提供 context） |
| `workflows`（P3） | 与其余模块隔离（ADR-0010）：只暴露 service 接口，允许未来拆独立部署单元零代码改动 |
| 跨域直查他域表 | **禁止**（HLD §6.2，表归属见 01-data-model §2 分域分组） |

边界示例（管道写事件域表必须走 service）：`pipeline/correlate.py` 产出候选事件时调用 `incidents.service.create_candidate(...)` / `merge_into_incident(...)`，不直接操作 `incident_candidates` / `incidents` 表。

## 3. 领域模块设计

### 3.1 模块-表-任务总览

| 域包 | 覆盖表（01-data-model §2 分组） | 触发的队列任务 |
|---|---|---|
| `domains/alerts` + `pipeline/` | providers、alerts、enrichment_rules、correlation_rules（P2）、maintenance_windows（P2） | `alert.process_pipeline`、`replay.scan`、`maintenance.close_windows` |
| `domains/incidents` | incident_candidates、incidents、incident_alerts、postmortems、postmortem_action_items、status_page_entries、status_page_updates | （消费 alerts 管道产出；A2 触发经 `ai.execute_task`，P3） |
| `domains/inspections` | inspection_rules、inspection_policies、inspection_policy_rules、inspection_runs、findings | `inspection.schedule_tick`、`inspection.run` |
| `domains/oncall` | oncall_schedules、escalation_policies | `escalation.check_ack`、`escalation.timeout_sweep` |
| `domains/ai` + `gateway/` | ai_tasks、ai_mask_mappings、ai_explanations、ai_call_logs | `ai.execute_task`、`approval.scan_timeouts` |
| `domains/workflows`（P3） | workflows、workflow_runs | Workflow 执行任务（P3 详设，投递队列沿 HLD §6.3 演进预留） |
| `domains/clusters` | clusters、credentials | `cluster.probe`（探活 cron） |
| `domains/notifications` | notification_records | `notify.dispatch` |
| `domains/iam` | users、roles、user_roles、audit_logs | —（同步写） |

各域统一分层：`routers`（app）→ `service`（业务与状态机）→ `repository`（纯数据访问）。以下重点写透四个模块，其余给紧凑设计。

### 3.2 告警管理域与 L1 管道（重点）

职责：webhook 接入、去重（D-1）、富化、关联（BR-04）、维护窗口抑制（BR-07）、告警工作台操作（认领/关闭/转事件）。实现交互文档 L1 时序图的每一步。

#### 3.2.1 同步接入段：先落库再入队（ADR-0003）

```python
# domains/alerts/service.py
class AlertService:
    async def ingest(self, session, provider: Provider, raw_payload: dict) -> IngestOutcome:
        """归一化 → 指纹 upsert 落库 → 入队 → 返回应答数据。"""

# pipeline/normalizer.py（纯函数）
def normalize(provider_type: str, raw_payload: dict) -> NormalizedAlert: ...
def compute_fingerprint(fingerprint_fields: list[str], labels: Mapping) -> str: ...
```

流程（webhook 路由 `POST /api/v1/webhooks/{provider_name}`）：

1. Provider 认证（令牌/签名 `[ASSUMPTION]`，沿 HLD §1.3，P0 Provider 框架详设）。
2. `normalize` + `compute_fingerprint`（字段取自 `providers.fingerprint_fields`）。
3. **落库 upsert**——一条 SQL 原子完成「新指纹插入 / 活跃指纹合并计数」，重复上报不产生新行：

```sql
INSERT INTO alerts (fingerprint, provider_id, severity, labels, raw_payload,
                    first_occurred_at, last_occurred_at, status, occurrence_count)
VALUES (...)
ON CONFLICT (fingerprint) WHERE status <> 'resolved'   -- 部分唯一索引 uk_alerts_active_fingerprint（D-1）
DO UPDATE SET occurrence_count  = alerts.occurrence_count + 1,
              last_occurred_at  = EXCLUDED.last_occurred_at
RETURNING id, (xmax = 0) AS inserted;
```

4. `inserted=true`（新告警，status=received）→ 投递 `alert.process_pipeline(alert_id)` 到 `q-alert-pipeline`；`inserted=false`（合并）→ 不入队（计数已持久化，工作台实时可见）。
5. 应答 `202 Accepted`，body `{alert_id, merged}`。

要点：

- 「先落库再入队」的物理含义即本 upsert：**任何上报都以持久化形式落地**（新告警插行或合并计数），Redis/管道故障不丢数据（非功能 §8 可用性；HLD §4.1）。
- Redis 判重缓存为热路径优化（upsert 前 `SETNX fingerprint→alert_id` 预判，命中走 UPDATE 快路径），Redis 不可用时直走 upsert，正确性由 D-1 兜底（HLD §4.1 第 3 条）。缓存与 PG 的一致性以 PG 为准，缓存仅加速 `[ASSUMPTION]`（验证方式：P0 管道压测，决定是否启用预判层）。
- 同指纹 severity 变化策略（取最高还是取最新）`[ASSUMPTION]`（验证方式：P0 告警管道详设评审，涉及降噪语义，需与告警工作台展示联动确认）。
- 恢复事件（Alertmanager resolved 等）由 `normalize` 识别并驱动 `resolve()`，活跃指纹释放后同指纹再现开新行（D-1 语义闭环）`[ASSUMPTION]`（恢复语义映射，P0 Provider 框架详设）。

#### 3.2.2 异步管道段（worker 任务 `alert.process_pipeline`）

worker 按 `alert_id` 取行，四步顺序执行（顺序不可调换，L1 设计），每步一个短事务、状态推进即落库：

| 步 | 实现 | 状态推进（领域 §6 Alert 状态机） |
|---|---|---|
| 1 幂等门闩 | `UPDATE alerts SET status='enriched', ... WHERE id=:id AND status IN ('received','deduplicated')`，rowcount=0 即已被处理（重放/重复投递），安全返回 | received → enriched |
| 2 富化 | `enrich.apply_enrichments(rules, labels) -> dict` 纯函数匹配 `enrichment_rules`（matchers 谓词 + priority 排序，mappings 为 extraction/mapping 两类），写入 `alerts.enrichments`（与原始 labels 分离，01-data-model §2.4） | —（与门闩同事务） |
| 3 关联（P2） | `correlate.correlate_alert(session, alert)`：按 `correlation_rules.conditions`（AND/OR）+ `time_window_seconds` 在窗口内匹配告警（GIN `idx_alerts_labels`），三种结果见下 | enriched → correlated / standalone |
| 4 窗口检查 + 通知触发 | BR-07：命中 `maintenance_windows.scope` → status=suppressed + `suppressed_by_window_id`（D-10 约束）；否则置 notified 并入队 `notify.dispatch`（§3.5） | correlated/standalone → suppressed / notified |

去重状态值（`deduplicated`）的物理落点：同步段合并发生且原行尚未被 worker 消费时（received 且 occurrence_count>1），worker 门闩先置 `deduplicated` 再富化为 `enriched`；「发生过合并」的持久表达是 `occurrence_count`/`last_occurred_at`，不依赖该状态值（供降噪归因展示，交互文档 §4.1）。去重在物理上分裂为同步段 upsert（判重与合并）与 worker 段收尾，语义与 L1 时序图一致，队列任务仍按「去重→富化→关联」三段命名——此为对 HLD §4.1/§4.2 的细化 `[ASSUMPTION]`（验证方式：P0 告警管道详设评审；§4.2 预算总值不变）。

关联三结果（BR-04 落地）：

- `mode=auto`：直接归并进已有 incident（`incident_alerts` 插入 + alert.status=correlated）。auto 准入门槛（运行 ≥30 天且零误报，`activated_at` + `confirm_count`/`reject_count`，01-data-model §2.4）在**规则创建/切换为 auto 时**由 service 校验，门槛细则 `[TBD-BIZ]`（业务负责人 / P2 设计前）。
- `mode=candidate`：经 `incidents.service.create_candidate(rule, member_alert_ids, similarity)` 写 `incident_candidates(status=pending)`（D-8 候选独立表），并经 SSE 推送待确认提醒（候选确认队列，交互文档 §4.1）；**不产生 incident**。
- 未命中：`standalone`，进通知。

#### 3.2.3 幂等与重放（L1 积压回放）

- **幂等三支柱**：① 指纹唯一性由部分唯一索引 `uk_alerts_active_fingerprint`（D-1）在库级保证，upsert 天然幂等；② worker 门闩（状态条件 UPDATE）保证同一 alert_id 重复投递无副作用（at-least-once 语义下安全）；③ 合并计数为 SQL 原子表达式，重放叠加计数与单次执行结果一致。
- **限流降级落盘**（HLD §5.3）：webhook 超限请求仍落盘（upsert 照常，等价于「标记 pending」——行保持 received 未入队），返回 429；队列积压超阈值时 webhook 切「只落盘不入队」模式。阈值 `[ASSUMPTION]`（P0 压测校准）。
- **回放器**（`replay.scan` cron）：扫描「已落盘但未被管道消费」的告警——判据 `status='received' AND updated_at < now() - stale_threshold`（正常消费秒级推进状态，阈值 60s `[ASSUMPTION]`）——按 `first_occurred_at` 顺序重新投递；重放幂等性由上述三支柱保证（HLD §5.3「重放幂等」）。积压超阈值经平台自监控直发告警给 admin（§6.5）。

#### 3.2.4 其余 service 函数

```python
class AlertService:
    async def acknowledge(self, session, alert_id: int, actor: Actor) -> Alert: ...   # 认领 + 审计
    async def resolve(self, session, alert_id: int, actor: Actor) -> Alert: ...       # 人工关闭
    async def suppress_feedback(self, session, alert_id: int, ...) -> None: ...       # 误报标记 → 降噪规则反馈池
    async def list(self, session, query: AlertListQuery, scope: TeamScope) -> Page[Alert]: ...
```

用表：alerts、providers、enrichment_rules、correlation_rules（P2）、maintenance_windows（P2）。规则集（enrichment/correlation）进程内缓存 + TTL 30s 起步，配置变更加速失效策略 `[ASSUMPTION]`（验证方式：P0 管道详设，压测后决定是否引入失效广播）。

### 3.3 巡检诊断域与 L4 执行器（重点）

职责：规则库与策略管理、cron 调度、只读集群拉取、确定性规则判定、Finding 批量写入、BR-09 分流。实现 L4 时序图全步骤。

```python
# 规则引擎：内置规则注册表（k8sgpt analyzer 移植风格）
class Analyzer(Protocol):
    code: str            # 对应 inspection_rules.code（业务键）
    category: str
    def analyze(self, snapshot: ResourceSnapshot) -> list[FindingDraft]: ...  # 纯函数

BUILTIN_ANALYZERS: dict[str, Analyzer]   # 注册表；code ↔ inspection_rules 行对齐

# domains/inspections/service.py
class InspectionService:
    async def create_policy(self, session, req: PolicyCreateRequest, actor: Actor) -> InspectionPolicy: ...
    async def trigger_run(self, session, policy_id: int, trigger: Literal["schedule","manual"], actor: Actor | None) -> InspectionRun: ...

# workers/tasks/inspection.py
async def schedule_tick(ctx: WorkerContext) -> None:
    """cron 每分钟：查 enabled 策略 → 判定 cron 到期 → 入队 inspection.run（防重复触发）。"""
async def run_inspection(ctx: WorkerContext, policy_id: int, trigger: str = "schedule") -> None: ...
```

`run_inspection` 执行序（L4 时序图逐步对应）：

1. 建 `inspection_runs(status=running)`；cluster 不健康（探活非 connected）时置 failed 并通知 admin（异常降级路径，交互文档 §6）。
2. **只读拉取**：`domains/clusters/connector.py` 取集群连接（仅加载 `scope=readonly` 凭证，BR-02；凭证经 secret_ref 运行时取用、内存态，D-2），按规则集涉及的对象粒度拉取 pods/deployments/pvc/nodes/events 等快照。
3. **规则判定**：逐条 `BUILTIN_ANALYZERS[code].analyze(snapshot)`，纯函数判定（输入资源清单 → 输出 `FindingDraft{rule_code, resource_ref, severity, raw_error}`），单测友好（§7.1）；`severity` 默认取 `inspection_rules.severity_default`，analyzer 可按错误内容覆盖。
4. **批量写入**：`findings` 批量 INSERT，业务键唯一 `(run_id, rule_code, resource_ref)`（01-data-model §2.6）；同资源已 open 的历史 finding 复现时按 Finding 状态机「in_progress → open 复现重开」处理 `[ASSUMPTION]`（验证方式：P0 巡检域详设评审）。
5. **BR-09 分流**：`severity ∈ {warning, critical}`（「warn 以上」= warning/critical，01-data-model §2.4 alert_severity 注）→ 转告警：构造归一化告警（fingerprint 由 `rule_code + resource_ref + cluster` 派生 `[ASSUMPTION]`，P0 巡检域详设）经 `AlertService.ingest` 进入 L1 upsert（与真实告警同管道同去重），finding 置 `converted_to_alert` + `converted_alert_id` 回链；`info` 仅入看板。
6. **可选 AI 解释**：`severity` 达到 `inspection_policies.ai_explain_level` 时入队 `ai.execute_task(finding_id)` 到 `q-ai`（P1 起；BR-09）。
7. 汇总 `result` / `findings_count`，置 succeeded/failed。

调度细节：`schedule_tick` 判定「策略 cron 是否到期」需 cron 表达式解析（候选 `croniter`，依赖审计 `[ASSUMPTION]`）；防重复触发以该策略最近一次 `trigger='schedule'` 的 run 记录判断 `[ASSUMPTION]`（验证方式：P0 巡检域详设，inspection_policies 无 next_run 字段——01-data-model 定稿不增列）。

用表：inspection_rules、inspection_policies、inspection_policy_rules（D-11 多对多）、inspection_runs、findings、alerts（转告警）。

### 3.4 AI 智能体域与 AI 网关（重点）

职责拆分：`domains/ai` 承担任务管理（创建/查询/审批 API、预算字段维护）；`gateway/` 承担执行面（脱敏→路由→预算→调用→回填→审计）。**AI 网关只在 worker 部署单元内运行**——api 进程无模型外呼能力，出域网络策略可对 api 一刀切封禁 `[ASSUMPTION]`（验证方式：P1 部署设计评审，与 HLD §4.3「网络层限制外呼端点」配合）。

```python
# gateway/gateway.py —— 唯一模型调用出口（ADR-0004）
class AIGateway:
    async def execute_task(self, ctx: WorkerContext, task_id: int) -> None:
        """AITask 状态机驱动：created→sanitizing→running→(pending_approval)→completed/failed/budget_exceeded"""

# gateway/sanitizer.py —— BR-01
class Sanitizer:
    def sanitize(self, text: str, task_id: int) -> SanitizedText: ...
        # 掩码 namespace/pod/IP/凭据类字段 → placeholder（K8S_MASK_xxxx）；
        # 原值经信封加密写 ai_mask_mappings.encrypted_original（仅本地，不出域不外发）
    def restore(self, text: str, task_id: int) -> str: ...   # 结果回填：本地还原 placeholder

# gateway/router.py —— BR-12
class ModelProvider(Protocol):
    name: str
    is_local: bool
    async def complete(self, req: ModelRequest) -> ModelResponse: ...

# gateway/providers/：local.py（Ollama / vLLM）优先注册；external.py 仅 AI_EGRESS_ENABLED=true 时注册

# domains/ai/service.py
class AITaskService:
    async def create(self, session, req, actor: Actor) -> AITask: ...      # budget 默认 BR-03（40 次 / 100k token）
    async def approve(self, session, task_id: int, decision, actor: Actor) -> AITask: ...  # 批准/拒绝（权限矩阵：sre 限本团队）
    async def list(self, session, query, scope: TeamScope) -> Page[AITask]: ...
```

网关管道逐环（每环对应一条 BR）：

| 环节 | 落地 | 依据 |
|---|---|---|
| 脱敏 | 出站前 `Sanitizer.sanitize`；`ai_mask_mappings` 原值加密仅存本地（密钥 `[TBD-INFRA]`，基础设施负责人 / P1 部署设计）；出域文本仅含 placeholder；回填后产物落 `ai_explanations`（A1）或 `ai_tasks.result` | BR-01 |
| 模型路由 | `ModelProvider` 抽象 + 本地优先注册；是否允许数据出域由管理员配置，默认仅本地；任务类型分级路由（explain 小模型、investigate 强模型——领域 §8 成本分级） | BR-12（默认值 `[TBD-BIZ]`，业务负责人 / P1 设计前） |
| 预算检查 | 每次模型调用前与 A2 每轮循环前检查 `ai_tasks.budget {max_calls, max_output_tokens}` 与 `calls_used` / `tokens_used`（字段见 01-data-model §2.7）；超限 graceful 终止：status=budget_exceeded、is_partial=true、输出部分结论并显式标注「未完成」 | BR-03（默认 40 次 / 100k 输出 token） |
| 审批挂起 | A2 高危工具调用 → status=pending_approval + `approval_deadline_at`（默认 30min `[ASSUMPTION]`，P3 上线前校准）+ 审批通知；批准→running 继续、拒绝→cancelled（上下文留存可重发）、超时由 `approval.scan_timeouts` cron 置 cancelled 并通知发起人（HLD §5.4）；A3 生成物确认后经 API 创建 workflows 行（`approved_by` 必填，D-10），任务侧等待期置 pending_approval `[ASSUMPTION]`（A3 任务状态细节，P3 详设） | BR-02 / BR-05 |
| 调用审计 | 每次调用写 `ai_call_logs`（model、tool_used、`prompt_digest` sha-256 不存明文、tokens_in/out、latency_ms、result_code）；只追加（D-6） | BR-10 |
| NoAI 熔断 | `circuit.py` 维护模型端点熔断状态（连续失败 N 次开路、半开探测，参数 `[ASSUMPTION]` P1 校准，ADR-0005）；开路时 A1 直接落 NoAI 结果（透出 raw_error + 人工入口）、A2/A3 拒绝新任务；熔断状态经 SSE `system` 主题下发，SPA 显著标识（交互文档 §6） | ADR-0005 |

用表：ai_tasks、ai_mask_mappings、ai_explanations、ai_call_logs、findings（A1 输入）/incidents（A2 输入，P3）。

### 3.5 通知中心与升级引擎（重点，L2）

职责：渠道抽象与投递、降级链（BR-13）、升级链状态机（各级超时）、NotificationRecord 留痕（BR-08）。实现 L2 时序图全步骤。

```python
# domains/notifications/channels.py —— 渠道抽象（Provider 出站接口）
class Channel(Protocol):
    name: str                                  # im / sms / voice（组合 [TBD-BIZ]）
    async def send(self, target: str, message: OutboundMessage) -> DeliveryResult: ...

# domains/notifications/service.py
class NotificationService:
    async def dispatch(self, ctx, req: DispatchRequest) -> None: ...
        # 写 notification_records(queued) → 渠道 send → sent/failed；失败走降级链重试
    async def handle_ack(self, session, record_id: int, action: str, actor: Actor) -> None: ...
        # Ack/Escalate/Resolve 回调 → record.status=acked + ack_action/ack_at（BR-08）
        # Ack 同步驱动升级链停止（告警 acknowledged / 事件 acknowledged 状态迁移）

# domains/oncall/escalation.py —— 升级引擎
class EscalationService:
    async def start(self, session, source: AlertRef | IncidentRef) -> None: ...
        # 查 escalation_policies（含 oncall_schedules）→ 解析当前值班（rotation_rules + calendar + overrides）
        # → dispatch(level=1) → 排延迟任务 escalation.check_ack(level=1, _defer_by=T1)
    async def check_ack(self, ctx, source: NotifySourceRef, level: int) -> None: ...
        # 该 level 已 acked → 结束；未 ack → 升级 level+1（投递 + 排下一级 check）
    async def timeout_sweep(self, ctx) -> None: ...   # cron 兜底：补偿丢失的延迟任务
```

升级链状态机的实现约定：

- **各级超时用 arq 延迟任务**：投递第 N 级时即 `enqueue_job('escalation.check_ack', _defer_by=levels[N].timeout_min)`；各级默认超时与渠道 `[TBD-BIZ]`（业务负责人 / P2 设计前，沿领域 §9）。兜底：低频 cron `escalation.timeout_sweep` 扫描未 ack 且超时的投递补偿升级（防延迟任务随 Redis 故障丢失）`[ASSUMPTION]`（验证方式：P2 值班域详设，以 arq 任务可靠性验证为准）——兜底扫描与 HLD §6.1「升级超时扫描」对应，主实现为延迟任务。
- **每一步留痕**：每次投递尝试（含降级尝试、升级投递）独立写 `notification_records`（channel、target、`content_digest` 摘要不存全文、status、escalation_level、error），构成完整审计链（BR-08）；只追加（D-6）。
- **降级链（BR-13）**：渠道失败按 `escalation_policies.channel_fallbacks` 依序降级（IM → 短信 → 电话，组合 `[TBD-BIZ]`）；**全渠道失败不停链**——当前级全部渠道失败后直接进入下一级目标，不等待本级超时。
- 通知触发源：告警管道末段（§3.2.2 第 4 步，`notify.dispatch` 入 `q-notification`）；事件立项/状态变化的通知策略 `[ASSUMPTION]`（验证方式：P2 事件域详设评审）。
- 排班解析（当前值班人计算：rotation_rules + calendar + overrides 纯函数）属 `domains/oncall/service.py`，供升级引擎调用（跨域 service 调用）。

用表：notification_records、escalation_policies、oncall_schedules、alerts / incidents（触发源与 ack 状态）。

### 3.6 事件响应域（incidents）

```python
class IncidentService:
    async def create_candidate(self, session, rule: CorrelationRule, member_alert_ids: list[int]) -> IncidentCandidate: ...  # BR-04/D-8
    async def confirm_candidate(self, session, candidate_id: int, actor: Actor) -> Incident: ...
        # 候选确认 → 建 incident(source=correlation, candidate_id) + incident_alerts；
        # P1/P2 事件自动同步状态页（BR-06）；关联告警状态置 correlated
    async def reject_candidate(self, session, candidate_id: int, reason: str, actor: Actor) -> None: ...
        # 驳回原因（规则过宽/时间窗过长/富化字段错误）结构化留存，回流规则调优（交互文档 §4.2）
    async def transition(self, session, incident_id: int, to_status: str, actor: Actor, **ctx) -> Incident: ...
        # 状态机流转：open→acknowledged→mitigated→resolved→closed；cancelled 必填原因（D-10）
    async def sync_status_page(self, ...) / revoke_status_page_update(...) -> None: ...   # BR-06 同步与撤回
    async def generate_postmortem_template(...) -> Postmortem: ...                        # 时间线自动汇总（L3）
```

状态机校验在 `transition` 内集中实现（合法迁移表 + 必填上下文校验），路由层禁止绕过。用表：§3.1 所列事件域 8 张表。

### 3.7 值班响应域（oncall）

- `ScheduleService`：排班 CRUD、overrides 编辑、`resolve_oncall(team, at) -> list[OncallPerson]` 纯函数（轮换/日历/顶班解析，单测重点）。
- `EscalationPolicyService`：升级策略 CRUD（levels/channel_fallbacks 结构校验，值 `[TBD-BIZ]`）。
- 用表：oncall_schedules、escalation_policies。

### 3.8 集群接入域（clusters）

- `ClusterService`：集群/凭证引用 CRUD（`secret_ref` 引用制，D-2；`providers.config` 禁止写入密钥值）。
- `ClusterConnector`：只读 K8s 客户端池（官方 `kubernetes` 客户端，HLD §3.1），凭证运行时经密钥管理取用、内存态使用、**禁止**落日志；`probe(ctx)` cron 探活更新 `clusters.status`（connected/degraded/disconnected/unknown，01-data-model §2.3 值域）。
- 探活失败 → 平台自监控直发告警（§6.5），巡检 run 置 failed 并通知 admin（异常降级路径）。

### 3.9 流程编排域（workflows，P3）

- `WorkflowService`：YAML 解析与校验、版本管理（「一版本一行」，01-data-model §2.9）、A3 确认入库（`source='ai_generated'` 时 `approved_by` 必填——D-10 库级约束兜底 + service 校验）、版本同步 Git `[TBD-INFRA]`（对接方式，基础设施负责人 / P3 设计前）。
- `WorkflowRunService`：执行实例状态机（triggered→running→waiting_approval→…，7 态）与 `steps_log` 记录；高危步骤挂起审批（BR-05，审批超时同 §3.4 扫描）。
- 引擎语义与执行队列沿 HLD §6.3（Keep YAML 语义改造借鉴；拆分预留 ADR-0010），P3 详设另立文档。

### 3.10 身份与审计域（iam）

- `UserService` / `RoleService`：用户/角色/授权管理（`user_roles.team_scope` 支撑 T 列团队隔离）；权限矩阵落库为 `roles.permissions` JSONB（结构示例见 §4.2）。
- `record_audit(session, action, resource_type, resource_id, detail, cost)`：全模块共用的审计写入（§6.2），与业务变更同事务。
- 认证方式（SSO/LDAP/本地）`[TBD-INFRA]`（基础设施负责人 / P0 部署设计，沿数据模型 §9）——实现收敛在 `core/security.py` 抽象后，service 层不感知具体机制。

## 4. API 层设计原则

### 4.1 路由分层与命名

- 前缀 `/api/v1`；资源复数 kebab-case：`/api/v1/alerts`、`/api/v1/incident-candidates`、`/api/v1/inspection-runs`、`/api/v1/ai-tasks` 等。
- 两个人口分治（HLD §1.3）：机器入口 `POST /api/v1/webhooks/{provider_name}`（Provider 令牌/签名认证 `[ASSUMPTION]`，独立限流）；人类入口其余路由（用户认证）。SSE 端点见 §5。
- 路由层薄：参数解析（DTO）→ 依赖注入（认证/权限/团队 scope）→ service 调用 → response 序列化。**禁止**路由层写业务逻辑与 SQL。
- 写操作命名：动作用子资源（`POST /alerts/{id}/acknowledge`、`POST /incident-candidates/{id}/confirm`、`POST /ai-tasks/{id}/approve`），与状态机动作一一对应。

### 4.2 鉴权与权限矩阵落地（领域 §3 → 依赖项 + 行级过滤）

```python
# core/security.py
async def get_current_user(...) -> User: ...            # 认证实现 [TBD-INFRA]，抽象点
def require_permission(resource: str, action: str):     # 权限依赖工厂
    ...                                                  # 读 roles.permissions 判定 Y / N / T
def resolve_team_scope(user: User, resource: str) -> TeamScope: ...
    # developer（user_roles.team_scope 非空）→ TeamScope(team=...)；否则 ALL

# 路由使用
@router.get("/alerts", dependencies=[Depends(require_permission("alerts", "read"))])
async def list_alerts(scope: TeamScope = Depends(resolve_team_scope), ...): ...
```

- `roles.permissions` JSONB 结构 `[ASSUMPTION]`（验证方式：P0 权限模块详设评审，与 01-data-model §2.2 标注一致）：

```json
{"alerts": {"read": "T", "acknowledge": "T", "close": "N"}, "clusters": {"read_config": "N"}}
```

- **T（限本团队）= 行级过滤**：service 查询自动附加团队条件（alerts 的 team 在 `enrichments->>'team'`；incidents 有 `team` 列）。`enrichments` 团队过滤的表达式索引支撑可能需增补索引——属 01-data-model 增补项 `[TBD-BE]`（后端负责人 / P0 权限模块详设，确认后回流 01-data-model 修订）。
- 写操作在权限之外仍须过审批流（BR-02）——权限矩阵只表达「谁可以发起」（领域 §3 注）。
- webhook 机器入口不走用户认证体系，权限模型不适用（Provider 级准入）。

### 4.3 分页 / 过滤 / 排序约定

- **分页**：offset/limit 起步（`?offset=0&limit=50`，limit 上限 200，offset 上限 10000 防深分页 `[ASSUMPTION]`——验证方式：P0 压测；若告警台出现深翻页需求再演进 cursor）。响应统一 `{items, total, offset, limit}`。
- **排序**：`?sort=-last_occurred_at,severity`（`-` 前缀降序）；可排序字段白名单按资源在 DTO `QueryParams` 中声明。
- **过滤**：标量字段 `?status=received&severity=critical&team=xxx`；labels/enrichments 半结构化字段 `?labels.env=prod`（转 JSONB 查询，走 GIN 索引，01-data-model §2.4）；时间范围 `?last_occurred_at.gte=...&last_occurred_at.lte=...`。
- 解析与校验收敛在 `core/pagination.py`，非法字段返回 400（§4.4）。

### 4.4 错误响应结构（结论：RFC 7807）

**采用 RFC 7807 `application/problem+json`**。理由：标准化字段（type/title/status/detail）+ 可扩展成员（`code`、`trace_id`），FastAPI 生态支持好（自定义 exception handler），前端可统一按 `status` 分支、按 `code` 精确提示；自定义结构无增益。

```json
{
  "type": "https://huntai.example/problems/state-conflict",
  "title": "Alert state conflict",
  "status": 409,
  "detail": "alert 123 is already resolved",
  "code": "ALERT_STATE_CONFLICT",
  "trace_id": "01J...(请求级，与日志关联)"
}
```

常用映射：400 参数/过滤字段非法、401 未认证、403 权限矩阵拒绝、404 资源不存在（团队隔离下的越权访问一律 404 防资源探测）、409 状态机非法迁移（如 cancelled 缺原因、已 resolved 再认领）、422 请求体校验失败（FastAPI 默认响应改写为 problem 格式）、429 webhook 限流（仍落盘，§3.2.3）、500 内部错误（detail 不泄内部信息）。`type` URL 域名占位，随部署域名定 `[TBD-INFRA]`。

### 4.5 OpenAPI 与 `04-api/` 的同步流程（结论：代码生成 spec）

**结论：spec 由代码生成（FastAPI 自动生成），导出物入 `docs/04-api/` 作为对外单一事实源；不采用手写 spec 先行。**

理由：

1. FastAPI 的类型注解即契约——API-first 在框架内原生成立，手写第二份 spec 必然漂移；
2. 治理规则（`docs/README.md` §4）要求「API 以 `04-api/` 的 OpenAPI spec 为单一事实源」——本流程下该 spec 是经评审冻结的导出物，事实源唯一性不变；
3. 前后端同仓同节奏（SPA 同步开发），不存在「先契约后实现」的外部协作时序诉求。

同步流程（必须执行）：

1. 路由与 DTO 变更 → `uv run python -m huntai.app.openapi`（`app/openapi.py`）导出 `openapi.json` 至 `docs/04-api/openapi.json`；
2. CI 校验：导出物与仓库内文件 `git diff --exit-code`，不一致即失败——杜绝「改了代码忘同步 spec」；
3. PR 评审以 spec diff 为契约变更审查面；破坏性变更（删字段/改语义/改状态码）必须在 PR 描述标注；
4. 前端基于该 spec 生成 TS client（是否自动生成 `[TBD-FE]`，前端 / P0 联调前定）。

若未来出现要求 design-first 的外部消费方，再评估「手写 spec + 生成物一致性校验」流程（登记 §8）。

## 5. 实时推送（SSE）

选型沿 HLD §3.3 倾向 SSE（ADR-0006，`[TBD-FE]` 最终确认，前端 / P0 技术设计时）；本文按 **SSE 实现但通道无关设计**（端点语义与载荷结构不绑传输，若结论翻转为 WebSocket，载荷与恢复语义平移）。

### 5.1 端点设计

```
GET /api/v1/stream?topics=alerts,incidents,ai-tasks
Accept: text/event-stream
Last-Event-ID: <上次收到的 id>          # 断连重连时携带
```

- 认证同人类入口；连接建立时按 `resolve_team_scope`（§4.2）确定团队过滤——T 角色不接收他团队事件（行级隔离在推送层同样生效）。
- topics 候选集 `[ASSUMPTION]`（验证方式：P0 前端联调评审）：`alerts`、`incidents`、`candidates`（候选事件提醒，L1）、`inspections`（finding 产出）、`ai-tasks`（任务与 pending_approval 状态）、`notifications`（ack 状态）、`system`（平台/AI 熔断全局状态，HLD §5.1）。
- 连接管理：每连接一个订阅协程；心跳为 SSE comment（`: ping`，15s `[ASSUMPTION]`）；单实例连接数上限与多副本广播策略 `[ASSUMPTION]`（验证方式：P0 部署设计评审；Redis pub/sub 天然支持多 api 副本各持连接）。

### 5.2 事件载荷结构

```
id: 1729730000000-0            # Redis Stream ID（与恢复游标统一，§5.3）
event: alert.status_changed
data: {"resource": "alert", "resource_id": 123, "team": "platform",
       "type": "status_changed", "from": "enriched", "to": "notified",
       "occurred_at": "2026-10-24T08:00:00Z", "summary": {...}}
```

- `data` 为最小事件载荷（变更摘要），详情由前端按 `resource_id` 拉取详情 API——推送只做「通知变更」，不承载完整对象。
- 发布点收敛在 `realtime/hub.py`：`publish(topic, event)` → Redis `XADD`（持久事件流）+ `PUBLISH`（实时扇出）；调用方为各域 service 状态推进处（§3 各状态机落库同事务后发布，推送失败不回滚业务、仅记日志 `[ASSUMPTION]`——验证方式：P0 详设评审一致性取舍）。

### 5.3 断连恢复（Last-Event-ID）

- 事件持久层用 **Redis Stream**（非纯 pub/sub）：pub/sub 断线即丢，Stream 提供可回放 backlog；`XTRIM` 维护保留窗口（30min `[ASSUMPTION]`，验证方式：P0 压测按事件量定窗口与内存预算）。
- 恢复协议：客户端 EventSource 自动重连并携带 `Last-Event-ID` → 服务端 `XRANGE(stream, last_id, +)` 回放缺失事件（按连接团队 scope 过滤）→ 追平后切换 `XREAD` 实时消费；无 Last-Event-ID 的首连从 `XREAD` 最新开始（首屏数据走列表 API 全量拉取，不回放历史）。
- Stream ID 即 SSE `id`，二者统一，避免双游标。

## 6. 横切关注点

### 6.1 结构化日志

- 全部日志 JSON 结构化输出（`structlog` 或标准库 JSON formatter，二选一 `[ASSUMPTION]`，验证方式：P0 工程化评审）；字段基线：`timestamp`、`level`、`logger`、`event`、`trace_id`、`actor`（user id / `system:任务名`）、`resource`（resource_type:resource_id）。
- `trace_id` 传播：API 入口中间件生成（或透传 `X-Request-ID`）→ contextvar → 入队载荷携带 → worker 日志续带，串联「webhook → 队列 → 管道/巡检/AI」全链路 `[ASSUMPTION]`（验证方式：P0 工程化评审）。
- **日志红线**：凭据值、`secret_ref` 解析结果、掩码原值、明文 prompt、`.env` 值**禁止**入日志（领域 §8；§6.4）；日志脱敏过滤器兜底拦截（键名黑名单 + secret_scan 离线扫描）。

### 6.2 审计中间件与审计写入（BR-10）

- **写入位置在 service 层显式调用**（`iam.service.record_audit`），与业务变更**同一事务**——审计与业务同生共死，杜绝「变更成功审计丢失」或反之。
- **HTTP 中间件职责收缩为上下文**：`request_context` 中间件提取 actor（认证结果）、ip、user_agent、trace_id 写入 contextvar，供 `record_audit` 读取（audit_logs 字段见 01-data-model §2.2）；HTTP 层访问日志由中间件产出，不重复写 audit_logs。
- **机器触发**：worker 任务入口设置 `actor_type=system` 的 contextvar；系统关键决策事件（BR-09 转告警、BR-07 抑制、升级链触发、审批结果）写 audit_logs(actor_type=system) `[ASSUMPTION]`（验证方式：P0 审计模块详设评审——人类写操作全量入 audit_logs，机器自动流转以各流水表（alerts/notification_records/inspection_runs）本身为审计载体，避免流水表+审计双倍写入）。
- `detail` 记录变更摘要且**排除凭据字段**（D-2 / 01-data-model §6.2）；AI 类操作 `cost` 记 tokens 计数。
- 不可删改：应用层无 UPDATE/DELETE 路径 + 库级 `REVOKE`（D-6，§1.6 迁移纪律第 5 条）。

### 6.3 配置管理（pydantic-settings）

- `core/config.py`：`Settings(BaseSettings)` 读仓库根 `.env`（`model_config = SettingsConfigDict(env_file=".env", env_prefix="HUNTAI_")`）；前缀 `HUNTAI_` `[ASSUMPTION]`（验证方式：P0 工程化评审固化清单）；值校验（URL 格式、枚举），启动即 fail-fast。
- 配置项清单（示例值均为占位符，**禁止**真实值入库入文档）：

| 配置项 | 用途 | 示例（占位符） |
|---|---|---|
| `HUNTAI_ENV` | 运行环境 | `dev` |
| `HUNTAI_DATABASE_URL` | PG 连接（asyncpg） | `postgresql+asyncpg://huntai:your-password@db:5432/huntai` |
| `HUNTAI_DATABASE_POOL_SIZE` / `MAX_OVERFLOW` | 连接池 | `10` / `20` |
| `HUNTAI_REDIS_URL` | Redis（队列/缓存/Stream） | `redis://redis:6379/0` |
| `HUNTAI_API_HOST` / `API_PORT` | uvicorn | `0.0.0.0` / `8000` |
| `HUNTAI_LOG_LEVEL` / `LOG_FORMAT` | 日志 | `info` / `json` |
| `HUNTAI_SECRET_BACKEND` | 密钥后端类型 | `vault`（`[TBD-INFRA]`） |
| `HUNTAI_MASK_ENCRYPTION_KEY_REF` | 掩码加密密钥引用 | `vault:transit/keys/huntai-mask`（`[TBD-INFRA]`） |
| `HUNTAI_AI_LOCAL_ENDPOINT` | 本地模型端点 | `http://ollama:11434` |
| `HUNTAI_AI_EGRESS_ENABLED` | 出域开关（默认 `false`，BR-12） | `false`（放开值 `[TBD-BIZ]`） |
| `HUNTAI_AI_BUDGET_DEFAULT_CALLS` / `_TOKENS` | 任务预算默认（BR-03） | `40` / `100000` |
| `HUNTAI_AI_CIRCUIT_FAILURES` / `RESET_SECONDS` | NoAI 熔断参数 | `5` / `60`（`[ASSUMPTION]` P1 校准） |
| `HUNTAI_APPROVAL_TIMEOUT_MINUTES` | 审批超时 | `30`（`[ASSUMPTION]`） |
| `HUNTAI_REPLAY_STALE_SECONDS` / `SCAN_SECONDS` | 回放参数（§3.2.3） | `60` / `30`（`[ASSUMPTION]`） |
| `HUNTAI_RATE_LIMIT_*` | webhook 限流（HLD §5.3） | 值 `[ASSUMPTION]` P0 压测定 |
| `HUNTAI_SSE_HEARTBEAT_SECONDS` / `STREAM_RETENTION_MINUTES` | SSE（§5） | `15` / `30`（`[ASSUMPTION]`） |
| `HUNTAI_NOTIFICATION_*` | 渠道配置（组合 `[TBD-BIZ]`） | 占位符 |

- 密钥类配置（模型 API key 等）：本地 dev 可入 `.env`（已 gitignore）；生产一律 `secret_ref` 引用密钥管理（§6.4）。

### 6.4 密钥红线

- 集群/Provider 凭证**永不落库**：`credentials.secret_ref` 引用制（D-2），运行时经密钥后端取用、仅内存态；`providers.config` 严禁写入密钥值。
- 代码/文档/命令/日志中一律 `$ENV_VAR` 或占位符（`your-api-key`）；仓库侧由 pre-commit hooks 与 `secret_scan.py` 强制拦截（项目 `AGENTS.md`）。
- `ai_mask_mappings.encrypted_original` 信封加密、仅本地、严禁外发（BR-01 / 01-data-model §6.2）；密钥管理方式 `[TBD-INFRA]`（基础设施负责人 / P1 部署设计）。

### 6.5 平台自监控（ADR-0012）

- 五类指标（HLD §4.1）：api/worker 存活、队列深度（5 条队列 LLEN）、PG/Redis 连通性、集群探活结果。指标暴露方式（探活脚本直查 or 复用巡检框架）`[ASSUMPTION]`（验证方式：P0 部署设计评审二选一）。
- 告警**直发 IM 渠道，不经平台自身告警管道**（避免自指失效）；直发客户端独立于 `domains/notifications` 的管道链路（复用 Channel 抽象但不经队列）`[ASSUMPTION]`（验证方式：P0 部署设计评审）。
- 积压超阈值、探活失败的通知对象：admin（交互文档 §6）。

## 7. 测试策略

### 7.1 单元测试（管道与规则纯函数化）

`pipeline/`（normalizer、fingerprint、enrich 匹配、correlate 条件求值）、巡检 `Analyzer`、排班解析、`Sanitizer` 掩码/还原、预算判定、状态机迁移表——全部按纯函数设计（§3），单测不触 DB/Redis。状态机测试逐迁移断言（合法迁移通过 + 非法迁移抛 409 语义异常）。

### 7.2 集成测试

- DB：testcontainers PostgreSQL 或共享 fixture DB，二选一 `[ASSUMPTION]`（验证方式：P0 工程化评审，考量 CI 环境容器可用性）——重点覆盖 §1.6 迁移可执行、D-1 部分唯一索引行为、D-6 REVOKE 生效、D-10 CHECK 约束。
- API：`httpx` ASGI transport + 覆盖认证/权限矩阵（逐角色 × 关键资源断言 Y/N/T，T 断言行级过滤结果）。
- worker：任务函数直接调用（注入 WorkerContext 与 fixture session），Redis 交互用 fakeredis 候选 `[ASSUMPTION]`（依赖审计通过前以接口抽象隔离）。

### 7.3 链路测试（必测清单，三条）

1. **L1 幂等**：同 fingerprint 活跃告警重复上报 N 次 → 恰 1 行、`occurrence_count=N`、`last_occurred_at` 前进、无重复入队副作用；resolved 后同指纹再现 → 新行（D-1 语义）；人为制造积压（只落盘不入队）→ 回放器补投 → 状态正常推进且重复补投无副作用。
2. **BR-04 候选流**：candidate 规则命中 → `incident_candidates(pending)` 且**无** incident；确认 → incident 建立 + `incident_alerts` 关联 + 候选置 confirmed；驳回 → rejected + `reject_reason` 留存；auto 模式在 `activated_at < 30 天` 时创建/切换被拒绝。
3. **BR-03 预算耗尽**：`max_calls=2` 的任务 → 第 3 次调用前 graceful 终止 → `status=budget_exceeded`、`is_partial=true`、result 含「未完成」标注、`ai_call_logs` 恰 2 条、`calls_used=2`。

### 7.4 BR 覆盖矩阵（其余重点）

| BR | 必测断言（补充于 §7.3 之外） |
|---|---|
| BR-01 | 脱敏往返：出域文本零原值（扫描 placeholder 之外的敏感模式）、还原后完整；映射表不出现在任何出站请求 |
| BR-02 | 连接器仅加载 readonly 凭证；高危工具触发 pending_approval |
| BR-05 | ai_generated Workflow 无 approved_by 时入库被拒（service 层与 D-10 库级双层） |
| BR-07 | 窗口内 suppressed + 窗口结束 cron 重投 |
| BR-08 | 升级链每步投递/失败/ack 均有 notification_records（含降级尝试） |
| BR-09 | warning/critical 转告警且 converted_alert_id 回链；info 不转 |
| BR-13 | 渠道失败依 fallbacks 降级；全失败直接进下一级不停链 |

## 8. 开放问题

| 标记 | 问题 | 确认人 / 阶段 |
|---|---|---|
| `[TBD-INFRA]` | 全部依赖版本锁定清单（uv.lock 首锁）、CI 平台与验证命令 | 基础设施负责人 / P0 工程化（ADR-0008） |
| `[TBD-INFRA]` | 认证方式（SSO/LDAP/本地）与用户会话机制（`core/security.py` 实现落点） | 基础设施负责人 / P0 部署设计 |
| `[TBD-INFRA]` | secret_ref 密钥后端选型、掩码加密密钥管理、迁移执行时机编排、出域网络策略 | 基础设施负责人 / P0-P1 部署设计 |
| `[TBD-BIZ]` | 同指纹 severity 变化策略、恢复事件语义映射（Provider 归一化细则输入） | 业务负责人 + 后端 / P0 管道详设 |
| `[TBD-BIZ]` | auto 关联模式准入细则、通知渠道组合与各级超时、AI 出域默认策略 | 业务负责人 / P1-P2 设计前（沿领域 §9） |
| `[TBD-BE]` | 团队行级过滤的索引支撑（`enrichments->>'team'` 表达式索引）——确认后回流 01-data-model 增补 | 后端负责人 / P0 权限模块详设 |
| `[TBD-FE]` | SSE 最终确认（ADR-0006）；前端是否由 openapi.json 自动生成 TS client | 前端 / P0 技术设计与联调前 |
| `[ASSUMPTION]` | §3.2 同步段 upsert 与「去重三段」的物理映射、回放阈值、cron 多副本防重、规则缓存失效、审计写入边界（人类/机器）、审计与推送的最终一致性取舍、arq 延迟任务丢失率（升级链兜底扫描必要性）、SSE 保留窗口与连接上限、asyncio 测试插件与集成测试 DB 方案、候选依赖清单（structlog/croniter/import-linter/testcontainers/fakeredis） | 验证方式均见各节标注，随 P0 工程化/详设评审/压测收敛 |
| `[ASSUMPTION]` | OpenAPI 若未来出现 design-first 外部消费方，评估手写 spec + 一致性校验流程 | 后端负责人 / 出现外部消费方时 |
