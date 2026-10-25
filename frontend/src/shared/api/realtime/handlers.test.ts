import { describe, expect, it } from 'vitest'
import { planInvalidations, mergeInvalidations, keyStartsWith } from './handlers'
import { qk } from '../../lib/query-keys'
import type { RealtimeMessage } from './types'

function msg(event: RealtimeMessage['event'], resourceId: number): RealtimeMessage {
  return {
    id: `${event}-${resourceId}`,
    event,
    payload: { resource: 'x', resource_id: resourceId, occurred_at: '2026-10-24T08:00:00Z' },
  }
}

describe('SSE 事件 → 失效计划（纯函数）', () => {
  it('alert.updated 失效列表广播 + 详情定点', () => {
    const plan = planInvalidations(msg('alert.updated', 7))
    expect(plan).toContainEqual(qk.alerts.list({}))
    expect(plan).toContainEqual(qk.alerts.detail(7))
  })

  it('incident.timeline.updated 失效时间线 + 详情 + 列表', () => {
    const plan = planInvalidations(msg('incident.timeline.updated', 801))
    expect(plan).toContainEqual(qk.incidents.timeline(801))
    expect(plan).toContainEqual(qk.incidents.detail(801))
    expect(plan).toContainEqual(qk.incidents.list())
  })

  it('ai_task.updated 失效任务列表 + 详情', () => {
    const plan = planInvalidations(msg('ai_task.updated', 403))
    expect(plan).toContainEqual(qk.aiTasks.list())
    expect(plan).toContainEqual(qk.aiTasks.detail(403))
  })

  it('未知事件返回空计划（幂等，不抛错）', () => {
    const unknown = {
      ...msg('alert.updated', 1),
      event: 'system.unknown',
    } as unknown as RealtimeMessage
    expect(planInvalidations(unknown)).toEqual([])
  })

  it('mergeInvalidations 去重跨事件重复键', () => {
    const merged = mergeInvalidations([
      planInvalidations(msg('ai_task.updated', 403)),
      planInvalidations(msg('ai_task.updated', 403)),
    ])
    expect(merged).toHaveLength(3)
  })
})

describe('keyStartsWith 前缀匹配', () => {
  it('list({}) 哨兵匹配任意 filters 组合（告警风暴广播）', () => {
    const sentinel = qk.alerts.list({})
    expect(keyStartsWith([...qk.alerts.list({ severity: 'critical', limit: 50 })], sentinel)).toBe(
      true,
    )
    expect(keyStartsWith([...qk.alerts.list({})], sentinel)).toBe(true)
  })

  it('detail 键只精确命中同 id', () => {
    expect(keyStartsWith([...qk.alerts.detail(7)], qk.alerts.detail(7))).toBe(true)
    expect(keyStartsWith([...qk.alerts.detail(8)], qk.alerts.detail(7))).toBe(false)
  })

  it('前缀长于 query key 时返回 false', () => {
    expect(keyStartsWith(['alerts'], qk.alerts.detail(7))).toBe(false)
  })
})
