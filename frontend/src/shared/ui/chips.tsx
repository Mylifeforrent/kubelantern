/** 徽章族（hifi §4.1）：severity chip / 状态 chip / ai-chip / ok-chip / tag / bdg。 */
import type { JSX } from 'react'
import { cn } from '../lib/cn'

export function Chip({
  variant,
  label,
  className,
}: {
  variant: string
  label: string
  className?: string
}): JSX.Element {
  return (
    <span className={cn('chip', variant, className)}>
      <i className="dot" />
      {label}
    </span>
  )
}

/** 告警严重度（01-data-model §3 alert_severity：info/warning/critical → P4/P3/P1 视觉档） */
export function SevChip({ severity }: { severity: string }): JSX.Element {
  const map: Record<string, { v: string; l: string }> = {
    critical: { v: 'sev-p1', l: 'P1 · 严重' },
    warning: { v: 'sev-p3', l: 'P3 · 中' },
    info: { v: 'sev-p4', l: 'P4 · 低' },
  }
  const m = map[severity] ?? { v: 'st-unknown', l: severity }
  return <Chip variant={m.v} label={m.l} />
}

/** 事件严重度（P1-P4） */
export function IncidentSevChip({ severity }: { severity: string }): JSX.Element {
  const map: Record<string, string> = {
    P1: 'sev-p1',
    P2: 'sev-p2',
    P3: 'sev-p3',
    P4: 'sev-p4',
  }
  return <Chip variant={map[severity] ?? 'st-unknown'} label={severity} />
}

/** 告警状态 chip（领域 §6 Alert 8 态） */
export function AlertStatusChip({ status }: { status: string }): JSX.Element {
  const map: Record<string, { v: string; l: string }> = {
    received: { v: 'st-unknown', l: '已接收' },
    deduplicated: { v: 'st-supp', l: '已去重' },
    enriched: { v: 'st-unknown', l: '已富化' },
    correlated: { v: 'st-corr', l: '已关联' },
    standalone: { v: 'st-unknown', l: '独立告警' },
    suppressed: { v: 'st-supp', l: '已抑制' },
    notified: { v: 'st-notified', l: '已通知' },
    resolved: { v: 'st-closed', l: '已关闭' },
  }
  const m = map[status] ?? { v: 'st-unknown', l: status }
  return <Chip variant={m.v} label={m.l} />
}

/** 事件状态 chip（领域 §6 Incident 6 态） */
export function IncidentStatusChip({ status }: { status: string }): JSX.Element {
  const map: Record<string, { v: string; l: string }> = {
    open: { v: 'st-open', l: '已立项' },
    acknowledged: { v: 'st-ack', l: '已确认' },
    mitigated: { v: 'st-mit', l: '已止血' },
    resolved: { v: 'st-res', l: '已恢复' },
    closed: { v: 'st-closed', l: '已关闭' },
    cancelled: { v: 'st-cancelled', l: '误报关闭' },
  }
  const m = map[status] ?? { v: 'st-unknown', l: status }
  return <Chip variant={m.v} label={m.l} />
}

/** 发现状态 chip（领域 §6 Finding 6 态） */
export function FindingStatusChip({ status }: { status: string }): JSX.Element {
  const map: Record<string, { v: string; l: string }> = {
    open: { v: 'st-open', l: '待处理' },
    acknowledged: { v: 'st-ack', l: '已认领' },
    in_progress: { v: 'st-running', l: '处置中' },
    resolved: { v: 'st-res', l: '已修复' },
    ignored: { v: 'st-closed', l: '已忽略' },
    converted_to_alert: { v: 'st-corr', l: '已转告警' },
  }
  const m = map[status] ?? { v: 'st-unknown', l: status }
  return <Chip variant={m.v} label={m.l} />
}

/** AI 任务状态 chip（领域 §6 AITask 8 态） */
export function AiTaskStatusChip({ status }: { status: string }): JSX.Element {
  const map: Record<string, { v: string; l: string }> = {
    created: { v: 'st-unknown', l: '已创建' },
    sanitizing: { v: 'st-running', l: '脱敏中' },
    running: { v: 'st-running', l: '执行中' },
    pending_approval: { v: 'st-cand', l: '待审批' },
    completed: { v: 'st-res', l: '已完成' },
    cancelled: { v: 'st-cancelled', l: '已取消' },
    budget_exceeded: { v: 'st-budget', l: '超预算' },
    failed: { v: 'st-failed', l: '失败' },
  }
  const m = map[status] ?? { v: 'st-unknown', l: status }
  return <Chip variant={m.v} label={m.l} />
}

/** 集群状态 chip */
export function ClusterStatusChip({ status }: { status: string }): JSX.Element {
  const map: Record<string, { v: string; l: string }> = {
    connected: { v: 'ok-chip', l: '已连接' },
    degraded: { v: 'st-degraded', l: '降级' },
    disconnected: { v: 'st-disconnected', l: '断连' },
    unknown: { v: 'st-unknown', l: '未知' },
  }
  const m = map[status] ?? { v: 'st-unknown', l: status }
  return <Chip variant={m.v} label={m.l} />
}

export function AiChip({ label }: { label: string }): JSX.Element {
  return (
    <span className="chip ai-chip">
      <i className="dot" />
      {label}
    </span>
  )
}

export function OkChip({ label }: { label: string }): JSX.Element {
  return (
    <span className="chip ok-chip">
      <i className="dot" />
      {label}
    </span>
  )
}

export function Tag({
  children,
  variant,
}: {
  children: string
  variant?: 'pu' | 'br' | 'gd'
}): JSX.Element {
  return <span className={cn('tag', variant)}>{children}</span>
}

export function Bdg({ count, purple }: { count: number; purple?: boolean }): JSX.Element | null {
  if (count <= 0) return null
  return <span className={cn('bdg', purple && 'pu')}>{count > 99 ? '99+' : count}</span>
}
