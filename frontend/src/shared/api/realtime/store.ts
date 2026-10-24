import { create } from 'zustand'
import type { ConnectionState } from './types'

/**
 * 实时全局客户端状态（zustand 三类全局态之一，03-frontend-design §1.2.3/§4.4）。
 * aiCircuit：NoAI 熔断全局标识（HLD §5.1 下行状态；事件契约随 04-api 定稿 [ASSUMPTION]）。
 */
interface RealtimeState {
  connection: ConnectionState
  aiCircuit: 'normal' | 'open'
  lastEventId: string | null
}

export const useRealtimeStore = create<RealtimeState>()(() => ({
  connection: 'closed',
  aiCircuit: 'normal',
  lastEventId: null,
}))

export function setConnection(connection: ConnectionState): void {
  useRealtimeStore.setState({ connection })
}

export function setAiCircuit(aiCircuit: 'normal' | 'open'): void {
  useRealtimeStore.setState({ aiCircuit })
}

export function setLastEventId(lastEventId: string): void {
  useRealtimeStore.setState({ lastEventId })
}
