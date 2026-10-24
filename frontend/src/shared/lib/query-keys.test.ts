import { describe, expect, it } from 'vitest'
import { qk } from './query-keys'

/** queryKey 工厂稳定性（03-frontend-design §7.1）：同参数生成同引用形状，缓存命中稳定 */
describe('query key 工厂', () => {
  it('同参数生成等价 key', () => {
    expect(qk.alerts.detail(1)).toEqual(qk.alerts.detail(1))
    expect(qk.alerts.list({ severity: 'critical' })).toEqual(
      qk.alerts.list({ severity: 'critical' }),
    )
  })

  it('不同参数生成不同 key', () => {
    expect(qk.alerts.detail(1)).not.toEqual(qk.alerts.detail(2))
    expect(qk.alerts.list({ severity: 'critical' })).not.toEqual(
      qk.alerts.list({ severity: 'info' }),
    )
  })

  it('key 层级以资源域为前缀（SSE 精确失效依赖）', () => {
    expect(qk.alerts.list({})[0]).toBe('alerts')
    expect(qk.incidents.timeline(1)[0]).toBe('incidents')
    expect(qk.aiTasks.list({})[0]).toBe('ai-tasks')
  })
})
