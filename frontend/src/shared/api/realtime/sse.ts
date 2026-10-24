import { fetchEventSource } from '@microsoft/fetch-event-source'
import { tokenStore } from '../auth'
import { setConnection, setLastEventId } from './store'
import type { RealtimeClient, RealtimeEventName, RealtimeMessage, RealtimePayload } from './types'
import { REALTIME_TOPICS } from './types'

/**
 * SSE 实现类（默认实现，03-frontend-design §1.2.7 推荐 @microsoft/fetch-event-source）：
 * 自定义 header（Bearer）、断连退避重连、Last-Event-ID 恢复（04-api /realtime/stream）。
 * 若 ADR-0006 结论为 WebSocket，仅替换本实现类，上层接口不变。
 */
export function createSseClient(baseUrl: string): RealtimeClient {
  const handlers = new Map<RealtimeEventName, Set<(msg: RealtimeMessage) => void>>()
  let ctrl: AbortController | null = null
  let closedByUser = false
  let retry = 0
  let lastEventId: string | null = null

  function dispatch(event: string, data: string, eventId: string | null): void {
    if (eventId) {
      lastEventId = eventId
      setLastEventId(eventId)
    }
    let payload: RealtimePayload
    try {
      payload = JSON.parse(data) as RealtimePayload
    } catch {
      return
    }
    const set = handlers.get(event as RealtimeEventName)
    if (!set) return
    const msg: RealtimeMessage = {
      id: eventId ?? '',
      event: event as RealtimeEventName,
      payload,
    }
    for (const h of set) h(msg)
  }

  function open(): void {
    if (closedByUser || ctrl) return
    ctrl = new AbortController()
    setConnection('connecting')
    const topics = REALTIME_TOPICS.join(',')
    const base = lastEventId ? `${baseUrl}?topics=${topics}` : `${baseUrl}?topics=${topics}`
    void fetchEventSource(base, {
      signal: ctrl.signal,
      openWhenHidden: true, // 内部 SRE 工具：页面隐藏时保持连接，状态不落后
      headers: {
        ...(tokenStore.get() ? { Authorization: `Bearer ${tokenStore.get() ?? ''}` } : {}),
        ...(lastEventId ? { 'Last-Event-ID': lastEventId } : {}),
      },
      onopen(res): Promise<void> {
        if (!res.ok) throw new Error(`sse http ${res.status}`)
        retry = 0
        setConnection('open')
        return Promise.resolve()
      },
      onmessage(m) {
        dispatch(m.event, m.data, m.id ?? null)
      },
      onclose() {
        setConnection('closed')
        ctrl = null
        if (!closedByUser) scheduleRetry()
      },
      onerror() {
        setConnection('closed')
        ctrl = null
        if (!closedByUser) scheduleRetry()
        throw new Error('sse retry gate') // 阻止库默认立即重连，走自管退避
      },
    })
  }

  function scheduleRetry(): void {
    // 指数退避 1s → 15s 封顶；断连期间活跃列表由 hooks 兜底轮询（§4.3）
    const delay = Math.min(1000 * 2 ** retry, 15_000)
    retry += 1
    window.setTimeout(open, delay)
  }

  return {
    connect: open,
    disconnect() {
      closedByUser = true
      ctrl?.abort()
      ctrl = null
      setConnection('closed')
    },
    on(event, handler) {
      let set = handlers.get(event)
      if (!set) {
        set = new Set()
        handlers.set(event, set)
      }
      set.add(handler)
      return () => set?.delete(handler)
    },
  }
}
