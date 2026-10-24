/**
 * 阶段一 mock 内存数据库（05-fe-be-boundary §3.2：mock 数据责任归前端，
 * mock 语义归契约——字段名/枚举/时间格式一律来自 docs/04-api/openapi.yaml；
 * 时间串一律带时区后缀 Z，AP-9）。
 */
import type {
  AIExplanation,
  AICallLog,
  AITask,
  Alert,
  AuditLog,
  Cluster,
  CorrelationRule,
  EnrichmentRule,
  EscalationPolicy,
  Finding,
  Incident,
  IncidentCandidate,
  IncidentTimelineItem,
  InspectionPolicy,
  InspectionRule,
  InspectionRun,
  MaintenanceWindow,
  NotificationRecord,
  OnCallSchedule,
  Postmortem,
  Provider,
  Role,
  User,
} from '../types'

export function nowIso(): string {
  return new Date().toISOString()
}

export function isoAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString()
}

let seq = 900
export function nextId(): number {
  seq += 1
  return seq
}

export interface MockUser extends User {
  pass: string
}

export interface Db {
  users: MockUser[]
  roles: Role[]
  clusters: Cluster[]
  providers: Provider[]
  enrichmentRules: EnrichmentRule[]
  correlationRules: CorrelationRule[]
  maintenanceWindows: MaintenanceWindow[]
  alerts: Alert[]
  explanations: AIExplanation[]
  candidates: IncidentCandidate[]
  incidents: Incident[]
  timelines: Record<number, IncidentTimelineItem[]>
  postmortems: Record<number, Postmortem>
  inspectionRules: InspectionRule[]
  policies: InspectionPolicy[]
  runs: InspectionRun[]
  findings: Finding[]
  aiTasks: AITask[]
  callLogs: AICallLog[]
  schedules: OnCallSchedule[]
  escalations: EscalationPolicy[]
  notifications: NotificationRecord[]
  auditLogs: AuditLog[]
}

export const db: Db = {
  users: [],
  roles: [],
  clusters: [],
  providers: [],
  enrichmentRules: [],
  correlationRules: [],
  maintenanceWindows: [],
  alerts: [],
  explanations: [],
  candidates: [],
  incidents: [],
  timelines: {},
  postmortems: {},
  inspectionRules: [],
  policies: [],
  runs: [],
  findings: [],
  aiTasks: [],
  callLogs: [],
  schedules: [],
  escalations: [],
  notifications: [],
  auditLogs: [],
}

export function addAudit(
  actorName: string,
  action: string,
  resourceType: string,
  resourceId: string,
  detail: Record<string, unknown> = {},
): void {
  db.auditLogs.unshift({
    id: nextId(),
    actor_user_id: db.users.find((u) => u.username === actorName)?.id,
    actor_type: actorName === 'system' ? 'system' : 'user',
    action,
    resource_type: resourceType,
    resource_id: resourceId,
    detail,
    created_at: nowIso(),
  })
}
