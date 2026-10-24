import type { Alert } from '../../shared/api/types'

/**
 * 告警工作台统计派生（03-frontend-design §5.1 / hifi §3.1）。
 * [ASSUMPTION]：契约草案未提供统计端点，以下为对当页列表的**展示聚合**（非 BR 语义计算，
 * AP-1 禁止的是降噪率等业务结论——降噪率由后端统计资源落地后替换）。
 */

const ACTIVE: Alert['status'][] = [
  'notified',
  'correlated',
  'deduplicated',
  'enriched',
  'standalone',
]

export interface AlertStats {
  /** 管道四步计数：①接入 ②去重 ③富化 ④关联 */
  pipeline: { received: number; dedup: number; enrich: number; correlate: number }
  /** 统计卡：待处理 / 去重抑制次数 / P1·P2 活跃 / 维护窗口抑制 */
  pending: number
  dedupSaved: number
  p12Active: number
  suppressed: number
}

export function deriveAlertStats(alerts: Alert[]): AlertStats {
  return {
    pipeline: {
      received: alerts.filter((a) => a.status === 'received').length,
      dedup: alerts.filter((a) =>
        ['deduplicated', 'enriched', 'notified', 'correlated', 'standalone'].includes(a.status),
      ).length,
      enrich: alerts.filter((a) =>
        ['enriched', 'notified', 'correlated', 'standalone'].includes(a.status),
      ).length,
      correlate: alerts.filter((a) => a.status === 'correlated').length,
    },
    pending: alerts.filter((a) => ACTIVE.includes(a.status)).length,
    dedupSaved: alerts.reduce((n, a) => n + Math.max(0, a.occurrence_count - 1), 0),
    p12Active: alerts.filter((a) => a.severity === 'critical' && ACTIVE.includes(a.status)).length,
    suppressed: alerts.filter((a) => a.status === 'suppressed').length,
  }
}

/** 降噪归因摘要（行内展示；归因数据由 status/occurrence_count/enrichments 派生 [ASSUMPTION]） */
export function dedupSummary(a: Alert): string {
  if (a.status === 'suppressed') return `维护窗口抑制（窗口 #${a.suppressed_by_window_id ?? '-'}）`
  if (a.occurrence_count > 1) return `同指纹合并 ×${a.occurrence_count}`
  if (a.status === 'correlated') return '关联规则命中，并入候选事件'
  if (a.status === 'deduplicated') return '命中活跃指纹，合并计数'
  return '—'
}
