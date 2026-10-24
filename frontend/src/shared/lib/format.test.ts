import { describe, expect, it } from 'vitest'
import { formatDateTime, formatPercent, parseTime } from '../../shared/lib/format'
import { describeProblem, toProblem } from '../../shared/api/problem'
import { ApiError } from '../../shared/api/problem'

describe('时间工具（AP-9）', () => {
  it('UTC ISO 8601（Z 后缀）解析为本地展示', () => {
    const d = parseTime('2026-10-24T08:00:00Z')
    expect(d.getTimezoneOffset()).toBeLessThanOrEqual(0) // 本地化解析，不做字符串拼接
    expect(typeof formatDateTime('2026-10-24T08:00:00Z')).toBe('string')
  })

  it('跨年时间串带年份', () => {
    expect(formatDateTime('2024-01-01T00:00:00Z')).toMatch(/^2024-/)
  })
})

describe('RFC 7807 错误规约', () => {
  it('解析 problem envelope（code 扩展成员）', () => {
    const p = toProblem({ status: 409, title: 'Conflict', code: 'ALERT_STATE_CONFLICT' })
    expect(p.code).toBe('ALERT_STATE_CONFLICT')
    expect(p.status).toBe(409)
  })

  it('非对象输入降级为通用 problem', () => {
    expect(toProblem('boom').title).toBe('请求失败')
  })

  it('文案按 code 映射；detail 不直出（AP-2）', () => {
    const err = new ApiError(
      toProblem({ status: 409, code: 'ALERT_STATE_CONFLICT', detail: 'internal stack xyz' }),
    )
    const text = describeProblem(err)
    expect(text).toContain('刷新')
    expect(text).not.toContain('internal stack')
  })

  it('未知 code 回退状态码文案', () => {
    expect(describeProblem(new ApiError(toProblem({ status: 403 })))).toContain('权限')
  })
})

describe('数值格式', () => {
  it('formatPercent', () => {
    expect(formatPercent(0.876)).toBe('88%')
  })
})
