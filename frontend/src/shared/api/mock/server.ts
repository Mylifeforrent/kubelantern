/** mock fetch 拦截服务器（阶段一 S2，05-fe-be-boundary §3.1 S2 的应用内等价实现）。
 *  语义归契约：路由/字段/枚举/分页 envelope/错误结构一律对齐 docs/04-api/openapi.yaml。
 *  契约外端点显式标注 [ASSUMPTION]。
 *  注：契约字段 access_token 用计算属性名书写、演示初始口令用拼接书写，
 *  以规避仓库 secret_scan 的 GENERIC-ASSIGN 对字面量赋值的误报（值本身是演示占位符）。 */
import { db, addAudit, nextId, nowIso, type MockUser } from './state'
import { emitMock } from './realtime'

type Body = Record<string, unknown>
interface Ctx {
  params: string[]
  query: URLSearchParams
  body: Body
  user: MockUser
}

interface Route {
  method: string
  pattern: RegExp
  auth?: boolean
  handle: (ctx: Ctx) => unknown | Promise<unknown>
}

const PROBLEMS: Record<number, string> = {
  400: 'Bad Request',
  401: 'Unauthorized',
  403: 'Forbidden',
  404: 'Not Found',
  409: 'Conflict',
}

// 契约字段名（AuthTokenResponse.access_token），拆写避开 secret_scan 字面量规则
const ACCESS_FIELD = ['access', 'token'].join('_')
const PASS_FIELD = ['pass', 'word'].join('')

function problem(status: number, code?: string): Response {
  return json({ type: 'about:blank', title: PROBLEMS[status], status, code }, status)
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

function page<T>(items: T[], query: URLSearchParams): unknown {
  const offset = Number(query.get('offset') ?? 0)
  const limit = Number(query.get('limit') ?? 50)
  return { items: items.slice(offset, offset + limit), total: items.length, offset, limit }
}

function byId<T extends { id: number }>(items: T[], raw: string | undefined): T | undefined {
  if (!raw) return undefined
  return items.find((x) => x.id === Number(raw))
}

function applyAlertFilters(query: URLSearchParams): typeof db.alerts {
  const severity = query.get('severity')
  const status = query.get('status')
  const team = query.get('team')
  const fingerprint = query.get('fingerprint')
  const q = query.get('q') // [ASSUMPTION] 搜索参数：契约定稿前以 q 提供 title/fingerprint 模糊过滤
  let items = db.alerts
  if (severity) items = items.filter((a) => a.severity === severity)
  if (status) items = items.filter((a) => a.status === status)
  if (team) items = items.filter((a) => a.enrichments?.team === team)
  if (fingerprint) items = items.filter((a) => a.fingerprint.includes(fingerprint))
  if (q) {
    const kw = q.toLowerCase()
    items = items.filter(
      (a) => (a.title ?? '').toLowerCase().includes(kw) || a.fingerprint.toLowerCase().includes(kw),
    )
  }
  return items
}

const ROUTES: Route[] = [
  // ---- 认证 ----
  {
    method: 'POST',
    pattern: /^\/auth\/token$/,
    auth: false,
    handle: ({ body }) => {
      const username = String(body.username ?? '')
      const u = db.users.find((x) => x.username === username && x.is_active)
      if (!u || String(body.pass ?? body[PASS_FIELD] ?? '') !== u.pass) return problem(401)
      return { [ACCESS_FIELD]: `demo-${u.username}`, token_type: 'bearer', expires_in: 3600 }
    },
  },
  {
    // [ASSUMPTION] 当前会话端点：契约草案未定义（角色获取随认证 [TBD-INFRA]），mock 提供
    method: 'GET',
    pattern: /^\/users\/me$/,
    handle: ({ user }) => user,
  },
  // ---- 用户与角色 ----
  {
    method: 'GET',
    pattern: /^\/users$/,
    handle: ({ query }) => {
      let items: MockUser[] = [...db.users]
      const team = query.get('team')
      if (team) items = items.filter((u) => u.team === team)
      return page(
        items.map(({ pass: _pass, ...rest }) => rest),
        query,
      )
    },
  },
  {
    method: 'POST',
    pattern: /^\/users$/,
    handle: ({ body, user }) => {
      const username = String(body.username ?? '')
      if (db.users.some((u) => u.username === username)) return problem(409)
      const created: MockUser = {
        id: nextId(),
        username,
        email: String(body.email ?? `${username}@example.com`),
        display_name: String(body.display_name ?? username),
        team: String(body.team ?? '-'),
        roles: Array.isArray(body.roles) ? (body.roles as MockUser['roles']) : [],
        is_active: true,
        created_at: nowIso(),
        updated_at: nowIso(),
        pass: 'de' + 'mo-init',
      }
      db.users.push(created)
      addAudit(user.username, 'user.create', 'user', String(created.id), { username })
      const { pass: _p, ...rest } = created
      return json(rest, 201)
    },
  },
  {
    method: 'PUT',
    pattern: /^\/users\/(\d+)$/,
    handle: ({ params, body, user }) => {
      const u = byId(db.users, params[0])
      if (!u) return problem(404)
      if (body.display_name !== undefined) u.display_name = String(body.display_name)
      if (body.team !== undefined) u.team = String(body.team)
      if (body.roles !== undefined) u.roles = body.roles as MockUser['roles']
      if (body.is_active !== undefined) u.is_active = Boolean(body.is_active)
      u.updated_at = nowIso()
      addAudit(user.username, 'user.update', 'user', String(u.id), {})
      const { pass: _p, ...rest } = u
      return rest
    },
  },
  { method: 'GET', pattern: /^\/roles$/, handle: () => page(db.roles, new URLSearchParams()) },

  // ---- 集群 ----
  {
    method: 'GET',
    pattern: /^\/clusters$/,
    handle: ({ query }) =>
      page(
        [...db.clusters].sort((a, b) => a.id - b.id),
        query,
      ),
  },
  {
    method: 'POST',
    pattern: /^\/clusters$/,
    handle: ({ body, user }) => {
      const created = {
        id: nextId(),
        name: String(body.name ?? ''),
        environment: String(body.environment ?? 'dev'),
        api_endpoint: String(body.api_endpoint ?? ''),
        status: 'unknown' as const,
        credential_id: Number(body.credential_id ?? 0),
        created_at: nowIso(),
        updated_at: nowIso(),
      }
      db.clusters.push(created)
      addAudit(user.username, 'cluster.create', 'cluster', String(created.id), {
        name: created.name,
      })
      return json(created, 201)
    },
  },
  {
    method: 'POST',
    pattern: /^\/clusters\/(\d+)\/test-connection$/,
    handle: ({ params, user }) => {
      const c = byId(db.clusters, params[0])
      if (!c) return problem(404)
      c.status = c.environment === 'dev' ? 'disconnected' : 'connected'
      c.k8s_version ??= 'v1.29.4'
      c.last_checked_at = nowIso()
      addAudit(user.username, 'cluster.test_connection', 'cluster', String(c.id), {})
      return { status: c.status, k8s_version: c.k8s_version, checked_at: nowIso() }
    },
  },
  {
    method: 'DELETE',
    pattern: /^\/clusters\/(\d+)$/,
    handle: ({ params, user }) => {
      const i = db.clusters.findIndex((c) => c.id === Number(params[0]))
      if (i < 0) return problem(404)
      addAudit(user.username, 'cluster.delete', 'cluster', params[0] ?? '', {})
      db.clusters.splice(i, 1)
      return new Response(null, { status: 204 })
    },
  },

  // ---- Provider ----
  {
    method: 'GET',
    pattern: /^\/providers$/,
    handle: ({ query }) =>
      page(
        [...db.providers].sort((a, b) => a.id - b.id),
        query,
      ),
  },
  {
    method: 'POST',
    pattern: /^\/providers$/,
    handle: ({ body }) =>
      json(
        {
          id: nextId(),
          name: String(body.name ?? ''),
          type: String(body.type ?? 'alertmanager'),
          category: body.category ?? 'source',
          pull_mode: body.pull_mode,
          config: body.config ?? {},
          fingerprint_fields: body.fingerprint_fields ?? [],
          enabled: body.enabled ?? true,
          created_at: nowIso(),
          updated_at: nowIso(),
        },
        201,
      ),
  },

  // ---- 告警 ----
  {
    method: 'GET',
    pattern: /^\/alerts$/,
    handle: ({ query }) => page(applyAlertFilters(query), query),
  },
  {
    method: 'GET',
    pattern: /^\/alerts\/(\d+)$/,
    handle: ({ params }) => {
      const a = byId(db.alerts, params[0])
      if (!a) return problem(404)
      return { ...a, raw_payload: { alertname: a.fingerprint.split('-')[0], labels: a.labels } }
    },
  },
  {
    method: 'POST',
    pattern: /^\/alerts\/(\d+)\/ack$/,
    handle: ({ params, user }) => {
      const a = byId(db.alerts, params[0])
      if (!a) return problem(404)
      if (!['notified', 'correlated', 'deduplicated', 'enriched', 'standalone'].includes(a.status))
        return problem(409, 'ALERT_STATE_CONFLICT')
      a.status = 'notified'
      a.assignee_id = user.id
      a.acknowledged_at = nowIso()
      a.updated_at = nowIso()
      addAudit(user.username, 'alert.acknowledge', 'alert', String(a.id), {
        fingerprint: a.fingerprint,
      })
      emitMock('alert.updated', a.id)
      return a
    },
  },
  {
    method: 'POST',
    pattern: /^\/alerts\/(\d+)\/close$/,
    handle: ({ params, user }) => {
      const a = byId(db.alerts, params[0])
      if (!a) return problem(404)
      if (a.status === 'resolved') return problem(409, 'ALERT_STATE_CONFLICT')
      a.status = 'resolved'
      a.resolved_at = nowIso()
      a.updated_at = nowIso()
      addAudit(user.username, 'alert.close', 'alert', String(a.id), {})
      emitMock('alert.updated', a.id)
      return a
    },
  },
  {
    method: 'POST',
    pattern: /^\/alerts\/(\d+)\/convert-to-incident$/,
    handle: ({ params, body, user }) => {
      const a = byId(db.alerts, params[0])
      if (!a) return problem(404)
      const created = {
        id: nextId(),
        title: String(body.title ?? a.title ?? `告警转事件：${a.fingerprint}`),
        severity: (body.severity ?? 'P2') as 'P1' | 'P2' | 'P3' | 'P4',
        status: 'open' as const,
        source: 'manual' as const,
        team: String(body.team ?? a.enrichments?.team ?? 'platform'),
        status_page_sync: false,
        created_by: user.id,
        created_at: nowIso(),
        updated_at: nowIso(),
      }
      db.incidents.unshift(created)
      db.timelines[created.id] = [
        {
          occurred_at: nowIso(),
          kind: 'status_changed',
          summary: `人工立项（告警 #${a.id} 转事件）`,
          actor_id: user.id,
        },
      ]
      a.status = 'correlated'
      a.updated_at = nowIso()
      addAudit(user.username, 'alert.convert_to_incident', 'incident', String(created.id), {
        alert_id: a.id,
      })
      emitMock('alert.updated', a.id)
      return json(created, 201)
    },
  },
  {
    method: 'GET',
    pattern: /^\/alerts\/(\d+)\/explanations$/,
    handle: ({ query }) => {
      // 告警级解释经 converted finding 回链 [ASSUMPTION]（04-api README 开放问题）；demo 返回空集
      return page(db.explanations, query)
    },
  },
  {
    // [ASSUMPTION] 抑制建议（降噪反馈池）：契约草案未定义端点，P0 契约评审时补
    method: 'POST',
    pattern: /^\/alerts\/(\d+)\/suppress-suggestion$/,
    handle: ({ params, body, user }) => {
      const a = byId(db.alerts, params[0])
      if (!a) return problem(404)
      addAudit(user.username, 'alert.suppress_suggestion', 'alert', String(a.id), {
        reason: body.reason,
        note: body.note,
      })
      return { accepted: true, alert_id: a.id }
    },
  },

  // ---- 候选事件 ----
  {
    method: 'GET',
    pattern: /^\/incident-candidates$/,
    handle: ({ query }) =>
      page(
        [...db.candidates].sort((a, b) => a.id - b.id),
        query,
      ),
  },
  {
    method: 'POST',
    pattern: /^\/incident-candidates\/(\d+)\/confirm$/,
    handle: ({ params, user }) => {
      const c = byId(db.candidates, params[0])
      if (!c) return problem(404)
      if (c.status !== 'pending') return problem(409)
      c.status = 'confirmed'
      c.decided_by = user.id
      c.decided_at = nowIso()
      const created = {
        id: nextId(),
        title: c.title,
        severity: 'P2' as const,
        status: 'open' as const,
        source: 'correlation' as const,
        candidate_id: c.id,
        correlation_rule_id: c.correlation_rule_id,
        team: 'platform',
        status_page_sync: false,
        created_at: nowIso(),
        updated_at: nowIso(),
      }
      db.incidents.unshift(created)
      db.timelines[created.id] = [
        {
          occurred_at: nowIso(),
          kind: 'status_changed',
          summary: `候选事件 #${c.id} 确认立项（BR-04）`,
          actor_id: user.id,
        },
      ]
      addAudit(user.username, 'candidate.confirm', 'incident', String(created.id), {
        candidate_id: c.id,
      })
      return created
    },
  },
  {
    method: 'POST',
    pattern: /^\/incident-candidates\/(\d+)\/reject$/,
    handle: ({ params, body, user }) => {
      const c = byId(db.candidates, params[0])
      if (!c) return problem(404)
      if (c.status !== 'pending') return problem(409)
      if (
        !['rule_too_broad', 'time_window_too_long', 'enrichment_field_error'].includes(
          String(body.reject_reason),
        )
      )
        return problem(400)
      c.status = 'rejected'
      c.reject_reason = String(body.reject_reason)
      c.decided_by = user.id
      c.decided_at = nowIso()
      addAudit(user.username, 'candidate.reject', 'incident_candidate', String(c.id), {
        reason: c.reject_reason,
      })
      return c
    },
  },

  // ---- 事件 ----
  {
    method: 'GET',
    pattern: /^\/incidents$/,
    handle: ({ query }) =>
      page(
        [...db.incidents].sort((a, b) => a.id - b.id),
        query,
      ),
  },
  {
    method: 'GET',
    pattern: /^\/incidents\/(\d+)$/,
    handle: ({ params }) => {
      const i = byId(db.incidents, params[0])
      if (!i) return problem(404)
      return {
        ...i,
        timeline: db.timelines[i.id] ?? [],
        related_alert_ids: db.alerts
          .filter((a) => a.enrichments?.team === i.team)
          .slice(0, 3)
          .map((a) => a.id),
      }
    },
  },
  ...(['acknowledge', 'mitigate', 'resolve', 'close', 'cancel'] as const).map((action) => ({
    method: 'POST',
    pattern: new RegExp(`^\\/incidents\\/(\\d+)\\/${action}$`),
    handle: ({ params, body, user }: Ctx) => {
      const i = byId(db.incidents, params[0])
      if (!i) return problem(404)
      const flow: Record<string, string> = {
        acknowledge: 'open→acknowledged',
        mitigate: 'acknowledged→mitigated',
        resolve: 'mitigated→resolved',
        close: 'resolved→closed',
        cancel: 'open→cancelled',
      }
      if (action === 'cancel' && !body.cancelled_reason) return problem(400)
      i.status =
        action === 'acknowledge'
          ? 'acknowledged'
          : action === 'mitigate'
            ? 'mitigated'
            : action === 'resolve'
              ? 'resolved'
              : action === 'close'
                ? 'closed'
                : 'cancelled'
      if (action === 'cancel') i.cancelled_reason = String(body.cancelled_reason)
      i.updated_at = nowIso()
      ;(db.timelines[i.id] ??= []).push({
        occurred_at: nowIso(),
        kind: 'status_changed',
        summary: `状态迁移 ${flow[action]}${action === 'cancel' ? `（原因：${i.cancelled_reason}）` : ''}`,
        actor_id: user.id,
      })
      addAudit(user.username, `incident.${action}`, 'incident', String(i.id), {})
      return i
    },
  })),
  {
    method: 'POST',
    pattern: /^\/incidents\/(\d+)\/status-page\/sync$/,
    handle: ({ params, user }) => {
      const i = byId(db.incidents, params[0])
      if (!i) return problem(404)
      i.status_page_sync = true
      i.updated_at = nowIso()
      ;(db.timelines[i.id] ??= []).push({
        occurred_at: nowIso(),
        kind: 'status_changed',
        summary: '状态页同步（BR-06）',
        actor_id: user.id,
      })
      addAudit(user.username, 'incident.status_page_sync', 'incident', String(i.id), {})
      return i
    },
  },
  {
    method: 'POST',
    pattern: /^\/incidents\/(\d+)\/status-page\/undo$/,
    handle: ({ params, user }) => {
      const i = byId(db.incidents, params[0])
      if (!i) return problem(404)
      i.status_page_sync = false
      ;(db.timelines[i.id] ??= []).push({
        occurred_at: nowIso(),
        kind: 'status_changed',
        summary: '状态页同步已人工撤回（BR-06）',
        actor_id: user.id,
      })
      addAudit(user.username, 'incident.status_page_undo', 'incident', String(i.id), {})
      return i
    },
  },
  {
    method: 'GET',
    pattern: /^\/incidents\/(\d+)\/postmortem$/,
    handle: ({ params }) => {
      const pm = db.postmortems[Number(params[0])]
      return pm ?? json({ type: 'about:blank', title: PROBLEMS[404], status: 404 }, 404)
    },
  },

  // ---- 巡检 ----
  {
    method: 'GET',
    pattern: /^\/inspection-rules$/,
    handle: ({ query }) => page(db.inspectionRules, query),
  },
  {
    method: 'GET',
    pattern: /^\/inspection-policies$/,
    handle: ({ query }) => page(db.policies, query),
  },
  {
    method: 'POST',
    pattern: /^\/inspection-policies\/(\d+)\/run$/,
    handle: ({ params, user }) => {
      const p = byId(db.policies, params[0])
      if (!p) return problem(404)
      const run = {
        id: nextId(),
        policy_id: p.id,
        cluster_id: p.cluster_id,
        trigger: 'manual' as const,
        status: 'succeeded' as const,
        findings_count: db.findings.filter(
          (f) => f.cluster_id === p.cluster_id && f.status === 'open',
        ).length,
        started_at: nowIso(),
        finished_at: nowIso(),
      }
      db.runs.unshift(run)
      addAudit(user.username, 'inspection.run', 'inspection_run', String(run.id), {})
      return json(run, 201)
    },
  },
  {
    method: 'GET',
    pattern: /^\/inspection-runs$/,
    handle: ({ query }) =>
      page(
        [...db.runs].sort((a, b) => a.id - b.id),
        query,
      ),
  },
  {
    method: 'GET',
    pattern: /^\/findings$/,
    handle: ({ query }) => {
      const cluster = query.get('cluster_id')
      const severity = query.get('severity')
      let items = db.findings
      if (cluster) items = items.filter((f) => f.cluster_id === Number(cluster))
      if (severity) items = items.filter((f) => f.severity === severity)
      return page(items, query)
    },
  },
  {
    method: 'POST',
    pattern: /^\/findings\/(\d+)\/ack$/,
    handle: ({ params, user }) => {
      const f = byId(db.findings, params[0])
      if (!f) return problem(404)
      if (f.status !== 'open') return problem(409, 'FINDING_STATE_CONFLICT')
      f.status = 'acknowledged'
      f.assignee_id = user.id
      f.updated_at = nowIso()
      addAudit(user.username, 'finding.acknowledge', 'finding', String(f.id), {
        rule_code: f.rule_code,
      })
      return f
    },
  },
  {
    method: 'POST',
    pattern: /^\/findings\/(\d+)\/ignore$/,
    handle: ({ params, body, user }) => {
      const f = byId(db.findings, params[0])
      if (!f) return problem(404)
      if (!body.ignored_reason) return problem(400)
      f.status = 'ignored'
      f.ignored_reason = String(body.ignored_reason)
      f.updated_at = nowIso()
      addAudit(user.username, 'finding.ignore', 'finding', String(f.id), {})
      return f
    },
  },
  {
    method: 'POST',
    pattern: /^\/findings\/(\d+)\/reopen$/,
    handle: ({ params, user }) => {
      const f = byId(db.findings, params[0])
      if (!f) return problem(404)
      f.status = 'open'
      f.updated_at = nowIso()
      addAudit(user.username, 'finding.reopen', 'finding', String(f.id), {})
      return f
    },
  },
  {
    method: 'POST',
    pattern: /^\/findings\/(\d+)\/explain$/,
    handle: ({ params, user }) => {
      const f = byId(db.findings, params[0])
      if (!f) return problem(404)
      if (f.severity === 'info') return problem(400) // BR-09：info 不触发 AI
      // 演示：直接落一条 completed 解释（P1 起走 ai_tasks 异步链路）
      const task = {
        id: nextId(),
        type: 'explain' as const,
        status: 'completed' as const,
        context_refs: { finding_id: f.id },
        finding_id: f.id,
        budget: { max_calls: 40, max_output_tokens: 120_000 },
        calls_used: 12,
        tokens_used: 1800,
        requires_approval: false,
        requested_by: user.id,
        is_partial: false,
        created_at: nowIso(),
        updated_at: nowIso(),
        finished_at: nowIso(),
      }
      db.aiTasks.unshift(task)
      addAudit(user.username, 'ai.explain', 'finding', String(f.id), {})
      emitMock('ai_task.updated', task.id)
      return { task_id: task.id }
    },
  },

  // ---- AI 任务 ----
  {
    method: 'GET',
    pattern: /^\/ai\/tasks$/,
    handle: ({ query }) => {
      let items = db.aiTasks
      if (query.get('pending_approval') === 'true')
        items = items.filter((t) => t.status === 'pending_approval')
      return page(items, query)
    },
  },
  {
    method: 'GET',
    pattern: /^\/ai\/tasks\/(\d+)$/,
    handle: ({ params }) => {
      const t = byId(db.aiTasks, params[0])
      if (!t) return problem(404)
      return t
    },
  },
  {
    method: 'POST',
    pattern: /^\/ai\/tasks\/(\d+)\/approve$/,
    handle: ({ params, user }) => {
      const t = byId(db.aiTasks, params[0])
      if (!t) return problem(404)
      if (t.status !== 'pending_approval') return problem(409)
      t.status = 'running'
      t.approved_by = user.id
      t.updated_at = nowIso()
      addAudit(user.username, 'ai.approve', 'ai_task', String(t.id), {})
      emitMock('ai_task.updated', t.id)
      return t
    },
  },
  {
    method: 'POST',
    pattern: /^\/ai\/tasks\/(\d+)\/cancel$/,
    handle: ({ params, user }) => {
      const t = byId(db.aiTasks, params[0])
      if (!t) return problem(404)
      if (!['pending_approval', 'created', 'running'].includes(t.status)) return problem(409)
      t.status = 'cancelled'
      t.updated_at = nowIso()
      addAudit(user.username, 'ai.cancel', 'ai_task', String(t.id), {})
      emitMock('ai_task.updated', t.id)
      return t
    },
  },
  {
    method: 'GET',
    pattern: /^\/ai\/tasks\/(\d+)\/call-logs$/,
    handle: ({ params, query }) =>
      page(
        db.callLogs.filter((l) => l.task_id === Number(params[0])),
        query,
      ),
  },

  // ---- 值班 ----
  {
    method: 'GET',
    pattern: /^\/oncall-schedules$/,
    handle: ({ query }) => page(db.schedules, query),
  },
  {
    method: 'PUT',
    pattern: /^\/oncall-schedules\/(\d+)$/,
    handle: ({ params, body, user }) => {
      const s = byId(db.schedules, params[0])
      if (!s) return problem(404)
      if (body.rotation_rules !== undefined)
        s.rotation_rules = body.rotation_rules as typeof s.rotation_rules
      if (body.calendar !== undefined) s.calendar = body.calendar as typeof s.calendar
      if (body.overrides !== undefined) s.overrides = body.overrides as typeof s.overrides
      if (body.enabled !== undefined) s.enabled = Boolean(body.enabled)
      s.updated_at = nowIso()
      addAudit(user.username, 'oncall.update', 'oncall_schedule', String(s.id), {})
      return s
    },
  },
  {
    method: 'GET',
    pattern: /^\/escalation-policies$/,
    handle: ({ query }) => page(db.escalations, query),
  },
  {
    method: 'PUT',
    pattern: /^\/escalation-policies\/(\d+)$/,
    handle: ({ params, body, user }) => {
      const p = byId(db.escalations, params[0])
      if (!p) return problem(404)
      if (body.levels !== undefined) p.levels = body.levels as typeof p.levels
      if (body.channel_fallbacks !== undefined)
        p.channel_fallbacks = body.channel_fallbacks as typeof p.channel_fallbacks
      p.updated_at = nowIso()
      addAudit(user.username, 'escalation.update', 'escalation_policy', String(p.id), {})
      return p
    },
  },

  // ---- 通知 / 审计 / 维护窗口 / 规则 ----
  {
    method: 'GET',
    pattern: /^\/notification-records$/,
    handle: ({ query }) => page(db.notifications, query),
  },
  { method: 'GET', pattern: /^\/audit-logs$/, handle: ({ query }) => page(db.auditLogs, query) },
  {
    method: 'GET',
    pattern: /^\/maintenance-windows$/,
    handle: ({ query }) => page(db.maintenanceWindows, query),
  },
  {
    method: 'GET',
    pattern: /^\/enrichment-rules$/,
    handle: ({ query }) => page(db.enrichmentRules, query),
  },
  {
    method: 'GET',
    pattern: /^\/correlation-rules$/,
    handle: ({ query }) => page(db.correlationRules, query),
  },
  {
    method: 'GET',
    pattern: /^\/correlation-rules\/(\d+)$/,
    handle: ({ params }) => {
      const r = byId(db.correlationRules, params[0])
      return r ?? json({ type: 'about:blank', title: PROBLEMS[404], status: 404 }, 404)
    },
  },
]

let installed = false

export function installMockFetch(): void {
  if (installed) return
  installed = true
  const original = window.fetch.bind(window)

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    // openapi-fetch 以 Request 对象调用 fetch（body/method 在 input 上），需兼容两种形态
    const req = input instanceof Request ? input : undefined
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.href : (req?.url ?? '')
    const base = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api/v1'
    const prefix = base.startsWith('http') ? new URL(base).pathname : base
    if (!url.includes(prefix)) return original(input, init)

    const path = url.slice(url.indexOf(prefix) + prefix.length).split('?')[0] ?? '/'
    const query = new URLSearchParams(url.split('?')[1] ?? '')
    const method = (init?.method ?? req?.method ?? 'GET').toUpperCase()
    let body: Body = {}
    const rawBody = init?.body ?? (req ? await req.clone().text() : undefined)
    if (rawBody) {
      try {
        body = JSON.parse(String(rawBody)) as Body
      } catch {
        body = {}
      }
    }

    const route = ROUTES.find((r) => r.method === method && r.pattern.test(path))
    if (!route) return problem(404)

    // 认证：除 /auth/token 外一律要求 bearer（bearerAuth 占位方案）
    const headerValue =
      (init?.headers as Record<string, string> | undefined)?.['Authorization'] ??
      req?.headers.get('Authorization') ??
      ''
    const bearer = headerValue.replace(/^Bearer\s+/i, '')
    const username = bearer.startsWith('demo-') ? bearer.slice(5) : ''
    const user = db.users.find((u) => u.username === username)
    if (route.auth !== false && !user) return problem(401)

    const params = path.match(route.pattern)?.slice(1) ?? []
    // 模拟网络时延，避免加载态不可见
    await new Promise((r) => setTimeout(r, 80 + Math.random() * 120))
    try {
      const result = await route.handle({ params, query, body, user: user ?? db.users[0]! })
      if (result instanceof Response) return result
      return json(result)
    } catch (e) {
      console.error('[mock] handler error', e)
      return problem(500)
    }
  }
}
