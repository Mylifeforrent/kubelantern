import type { QueryClient } from '@tanstack/react-query'
import { qk } from '../../lib/query-keys'
import type { RealtimeMessage } from './types'

/**
 * SSE 事件 → Query 缓存失效计划（03-frontend-design §4.3 合并策略矩阵）。
 * 契约载荷最小化（只带 resource/resource_id，04-api /realtime/stream），因此策略为
 * 「按事件精确失效 + 回拉」：列表失效广播、详情/时间线按 resource_id 定点失效。
 * planInvalidations 为纯函数（单测重点：幂等去重/未知事件忽略）。
 */

export type Invalidation = readonly unknown[] // query key 前缀

export function planInvalidations(msg: RealtimeMessage): Invalidation[] {
  switch (msg.event) {
    case 'alert.updated':
      return [
        qk.alerts.list({}), // 前缀匹配所有 filters 组合
        qk.alerts.detail(msg.payload.resource_id),
        ['nav-badge'],
      ]
    case 'incident.timeline.updated':
      return [
        qk.incidents.timeline(msg.payload.resource_id),
        qk.incidents.detail(msg.payload.resource_id),
        qk.incidents.list(),
        ['nav-badge'],
      ]
    case 'ai_task.updated':
      return [qk.aiTasks.list(), qk.aiTasks.detail(msg.payload.resource_id), ['nav-badge']]
    default:
      return []
  }
}

/** 多事件合并去重（同前缀只保留一条），rAF 批处理 flush 前调用 */
export function mergeInvalidations(plans: Invalidation[][]): Invalidation[] {
  const seen = new Set<string>()
  const out: Invalidation[] = []
  for (const plan of plans) {
    for (const key of plan) {
      const k = JSON.stringify(key)
      if (!seen.has(k)) {
        seen.add(k)
        out.push(key)
      }
    }
  }
  return out
}

export function keyStartsWith(queryKey: readonly unknown[], prefix: readonly unknown[]): boolean {
  if (prefix.length > queryKey.length) return false
  return prefix.every((p, i) => {
    if (i === queryKey.length - 1 && prefix.length === queryKey.length) {
      // list({}) 哨兵键 ['alerts','list',{}] 作为前缀时匹配任意 filters 对象
      if (p !== null && typeof p === 'object' && Object.keys(p).length === 0) {
        return typeof queryKey[i] === 'object' && queryKey[i] !== null
      }
    }
    return JSON.stringify(p) === JSON.stringify(queryKey[i])
  })
}

/**
 * Realtime 桥：订阅 client 事件 → rAF 批量失效 Query 缓存（告警风暴时同帧合并，§6）。
 */
export function startRealtimeBridge(
  queryClient: QueryClient,
  subscribe: (handler: (msg: RealtimeMessage) => void) => () => void,
): () => void {
  let pending: Invalidation[][] = []
  let frame: number | null = null

  function flush(): void {
    frame = null
    const plans = pending
    pending = []
    for (const key of mergeInvalidations(plans)) {
      void queryClient.invalidateQueries({
        predicate: (q) => keyStartsWith(q.queryKey, key),
      })
    }
  }

  return subscribe((msg) => {
    pending.push(planInvalidations(msg))
    if (frame === null) frame = requestAnimationFrame(flush)
  })
}
