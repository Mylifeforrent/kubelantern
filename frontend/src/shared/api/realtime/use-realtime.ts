import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { createSseClient } from './sse'
import { startRealtimeBridge } from './handlers'
import { useSessionStore } from '../../../features/session/session-store'
import type { RealtimeClient, RealtimeEventName } from './types'
import { createMockRealtimeClient } from '../mock/realtime'

/** 创建通道客户端：mock 模式用内置模拟实现（阶段一 S2），否则 SSE 实现 */
export function createRealtimeClient(): RealtimeClient {
  if (import.meta.env.VITE_USE_MOCK === '1') return createMockRealtimeClient()
  const base = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api/v1'
  return createSseClient(`${base}/realtime/stream`)
}

let client: RealtimeClient | null = null

export function getRealtimeClient(): RealtimeClient {
  client ??= createRealtimeClient()
  return client
}

const EVENTS: RealtimeEventName[] = [
  'alert.updated',
  'incident.timeline.updated',
  'ai_task.updated',
]

/**
 * 应用装配 hook（providers 挂载）：登录后建立连接并桥接缓存失效；
 * 断连兜底轮询由各列表 hooks 的 refetchInterval 动态函数实现（§4.3）。
 */
export function useRealtimeBridge(): void {
  const queryClient = useQueryClient()
  const hasSession = useSessionStore((s) => s.user !== null)

  useEffect(() => {
    if (!hasSession) return
    const c = getRealtimeClient()
    const stops = EVENTS.map((e) => startRealtimeBridge(queryClient, (h) => c.on(e, h)))
    c.connect()
    return () => {
      for (const stop of stops) stop()
      c.disconnect()
    }
  }, [queryClient, hasSession])
}
