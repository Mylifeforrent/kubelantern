import { db, nextId, nowIso, isoAgo } from './state'
import type { RealtimeClient, RealtimeEventName, RealtimeMessage } from '../realtime/types'
import { setConnection } from '../realtime/store'

/**
 * mock 实时通道（阶段一 S2 替代 SSE）：内存事件总线 + 演示定时器。
 * 演示定时器周期性对活跃告警合并计数 +1 并发 alert.updated（§4.3 行级更新演示）；
 * NoAI 熔断为全局下行状态（HLD §5.1），mock 通过订阅 system 主题模拟。
 */
type Listener = (msg: RealtimeMessage) => void

const listeners = new Map<RealtimeEventName, Set<Listener>>()
let timer: number | null = null
let aiTimer: number | null = null

export function emitMock(event: RealtimeEventName, resourceId: number, team?: string): void {
  const set = listeners.get(event)
  if (!set || set.size === 0) return
  const msg: RealtimeMessage = {
    id: `${Date.now()}-${Math.floor(Math.random() * 1000)}`,
    event,
    payload: {
      resource: event.split('.')[0] ?? 'alert',
      resource_id: resourceId,
      team,
      occurred_at: nowIso(),
    },
  }
  for (const l of set) l(msg)
}

export function createMockRealtimeClient(): RealtimeClient {
  return {
    connect() {
      setConnection('open')
      timer ??= window.setInterval(() => {
        const active = db.alerts.filter(
          (a) => ['notified', 'correlated'].includes(a.status) && a.severity !== 'info',
        )
        const target = active[Math.floor(Math.random() * active.length)]
        if (!target) return
        target.occurrence_count += 1
        target.last_occurred_at = nowIso()
        emitMock('alert.updated', target.id, target.enrichments?.team as string | undefined)
      }, 20_000)
      // 演示：60s 后模拟一次 AI 熔断开路 → 90s 后恢复（HLD §5.1 显著标识）
      aiTimer ??= window.setTimeout(() => {
        window.dispatchEvent(new CustomEvent('huntai:ai-circuit', { detail: 'open' }))
        window.setTimeout(() => {
          window.dispatchEvent(new CustomEvent('huntai:ai-circuit', { detail: 'normal' }))
        }, 30_000)
      }, 60_000)
    },
    disconnect() {
      if (timer !== null) {
        window.clearInterval(timer)
        timer = null
      }
      if (aiTimer !== null) {
        window.clearTimeout(aiTimer)
        aiTimer = null
      }
      setConnection('closed')
    },
    on(event, handler) {
      let set = listeners.get(event)
      if (!set) {
        set = new Set()
        listeners.set(event, set)
      }
      set.add(handler)
      return () => set?.delete(handler)
    },
  }
}

/** 确保演示数据持续推进：新告警周期落库（演示接入管道 + 实时新增行） */
export function startMockDemoFeed(): void {
  window.setInterval(() => {
    const names = ['LatencyP99High', 'QueueBacklog', 'CacheMissRatioHigh'] as const
    const name = names[Math.floor(Math.random() * names.length)] ?? 'LatencyP99High'
    const id = nextId()
    db.alerts.unshift({
      id,
      fingerprint: `${name}-pay`,
      provider_id: 21,
      title: `${name}（演示数据流）`,
      severity: Math.random() > 0.5 ? 'warning' : 'critical',
      status: 'notified',
      labels: { alertname: name, team: 'pay' },
      enrichments: { team: 'pay', service: 'demo' },
      occurrence_count: 1,
      first_occurred_at: nowIso(),
      last_occurred_at: nowIso(),
      created_at: nowIso(),
      updated_at: nowIso(),
    })
    emitMock('alert.updated', id, 'pay')
  }, 45_000)
  void isoAgo // 保持导入（未用警告规避：演示数据不回溯时间）
}
