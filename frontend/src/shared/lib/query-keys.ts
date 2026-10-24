/**
 * queryKey 注册表（03-frontend-design §4.2）：只有 key 工厂，不含请求逻辑。
 * 供 feature hooks 与 SSE 全局分发层共同引用；列表 key 的 filters 直接取自 URL。
 */

export interface ListQuery {
  offset?: number
  limit?: number
  [k: string]: unknown
}

export interface AlertFilters extends ListQuery {
  severity?: string
  status?: string
  team?: string
  fingerprint?: string
}

export const qk = {
  alerts: {
    list: (f: AlertFilters) => ['alerts', 'list', f] as const,
    detail: (id: number) => ['alerts', 'detail', id] as const,
    explanations: (id: number) => ['alerts', 'explanations', id] as const,
  },
  candidates: {
    list: (f: ListQuery = {}) => ['candidates', 'list', f] as const,
  },
  incidents: {
    list: (f: ListQuery = {}) => ['incidents', 'list', f] as const,
    detail: (id: number) => ['incidents', 'detail', id] as const,
    timeline: (id: number) => ['incidents', 'timeline', id] as const,
    postmortem: (id: number) => ['incidents', 'postmortem', id] as const,
  },
  inspections: {
    clusters: () => ['inspections', 'clusters'] as const,
    findings: (clusterId: number, f: ListQuery = {}) => ['findings', clusterId, f] as const,
    runs: (clusterId: number) => ['inspection-runs', clusterId] as const,
    policies: (clusterId?: number) => ['inspection-policies', clusterId ?? 'all'] as const,
    rules: () => ['inspection-rules'] as const,
  },
  aiTasks: {
    list: (f: ListQuery = {}) => ['ai-tasks', 'list', f] as const,
    detail: (id: number) => ['ai-tasks', 'detail', id] as const,
    callLogs: (id: number) => ['ai-tasks', 'call-logs', id] as const,
  },
  oncall: {
    schedules: () => ['oncall-schedules'] as const,
    escalationPolicies: () => ['escalation-policies'] as const,
  },
  admin: {
    users: (f: ListQuery = {}) => ['users', f] as const,
    roles: () => ['roles'] as const,
    clusters: () => ['admin', 'clusters'] as const,
    providers: () => ['admin', 'providers'] as const,
    enrichmentRules: () => ['enrichment-rules'] as const,
    auditLogs: (f: ListQuery = {}) => ['audit-logs', f] as const,
  },
} as const

/** 告警域所有 key（SSE alert.updated 时失效） */
export const alertKeys = {
  all: (f: AlertFilters) => [qk.alerts.list(f), qk.alerts.detail(0)] as const, // 精确失效见 handlers
}
