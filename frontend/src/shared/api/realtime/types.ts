/**
 * RealtimeClient 抽象与契约（03-frontend-design §1.2.7 / §4.3，通道无关）。
 * 通道协议（SSE vs WebSocket）[TBD-FE]（ADR-0006）；本文只定客户端接口与事件载荷形状。
 * 事件类型与载荷为 04-api 契约草案定义：载荷最小化（只通知变更，详情走 API 回拉）。
 */

export const REALTIME_EVENTS = [
  'alert.updated',
  'incident.timeline.updated',
  'ai_task.updated',
] as const
export type RealtimeEventName = (typeof REALTIME_EVENTS)[number]

/** SSE 事件 data 帧结构（docs/04-api openapi.yaml /realtime/stream 示例） */
export interface RealtimePayload {
  resource: string
  resource_id: number
  team?: string
  occurred_at: string
}

export interface RealtimeMessage {
  id: string
  event: RealtimeEventName
  payload: RealtimePayload
}

export type ConnectionState = 'connecting' | 'open' | 'closed'

export interface RealtimeClient {
  connect(): void
  disconnect(): void
  /** 返回取消订阅函数 */
  on(event: RealtimeEventName, handler: (msg: RealtimeMessage) => void): () => void
}

/** 订阅主题候选集（04-api /realtime/stream topics 参数，[ASSUMPTION]） */
export const REALTIME_TOPICS = ['alerts', 'incidents', 'candidates', 'ai-tasks', 'system'] as const
