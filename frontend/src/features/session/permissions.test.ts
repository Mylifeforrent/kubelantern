import { describe, expect, it } from 'vitest'
import { can, PERMISSION_MATRIX, ROLES, type Permission } from '../../shared/types/permissions'
import type { Role } from '../../shared/types/permissions'

/**
 * 权限位矩阵全组合单测（03-frontend-design §7.1）。
 * 期望值逐条对照领域文档 01-domain-model.md §3 权限矩阵。
 */
const EXPECTED: Record<Role, Partial<Record<Permission, boolean>>> = {
  admin: {
    'route.alerts': true,
    'route.candidates': true,
    'route.incidents': true,
    'route.inspections': true,
    'route.ai-tasks': true,
    'route.oncall': true,
    'route.admin': true,
    'alert.ack': true,
    'alert.close': true,
    'alert.suppress': true,
    'candidate.decide': true,
    'incident.manage': true,
    'incident.status-page': true,
    'finding.ack': true,
    'finding.ignore': true,
    'finding.explain': true,
    'ai.approve': true,
    'oncall.edit': true,
    'admin.config': true,
    'admin.audit': true,
  },
  sre: {
    'route.alerts': true,
    'route.candidates': true,
    'route.incidents': true,
    'route.inspections': true,
    'route.ai-tasks': true,
    'route.oncall': true, // 只读 [ASSUMPTION]（入口可见，编辑位独立控制）
    'alert.ack': true,
    'alert.close': true,
    'alert.suppress': true,
    'candidate.decide': true,
    'incident.manage': true,
    'incident.status-page': true,
    'finding.ack': true,
    'finding.ignore': true,
    'finding.explain': true,
    'ai.approve': true, // 限本团队（T），行级过滤由后端执行
    'oncall.edit': false,
    'admin.config': false,
    'admin.audit': false,
  },
  oncall_manager: {
    'route.alerts': true, // 只读
    'route.incidents': true, // 只读
    'route.oncall': true,
    'oncall.edit': true,
    'alert.ack': false, // 矩阵：告警认领 N
    'alert.close': false,
    'candidate.decide': false,
    'incident.manage': false, // 事件处置 N（只读）
    'route.inspections': false,
    'route.ai-tasks': false,
    'route.admin': false,
  },
  developer: {
    'route.alerts': true, // T 限本团队
    'route.candidates': true, // T
    'route.incidents': true, // T
    'route.inspections': true,
    'alert.ack': true, // T
    'alert.close': false, // 矩阵：关闭 N
    'alert.suppress': true, // T（契约 x-roles：developer(T)）
    'candidate.decide': true, // T
    'incident.manage': true, // T
    'incident.status-page': false,
    'finding.ack': true, // 认领 finding（唯一显式写权）
    'finding.ignore': false,
    'finding.explain': false, // 无 AI 权
    'ai.approve': false, // 无 AI 审批权
    'oncall.edit': false,
    'route.admin': false,
  },
  viewer: {
    'route.alerts': false, // 矩阵：告警查看 N
    'route.incidents': false,
    'route.admin': false,
    'alert.ack': false,
    'oncall.edit': false,
  },
}

describe('权限位 can()（领域 §3 矩阵全组合）', () => {
  it('每个角色的期望权限逐条命中', () => {
    for (const role of ROLES) {
      const expected = EXPECTED[role]
      for (const [perm, allowed] of Object.entries(expected)) {
        expect({
          role,
          perm,
          got: can(role, perm as Permission),
          want: allowed,
        }).toEqual({ role, perm, got: allowed, want: allowed })
      }
    }
  })

  it('未登录（undefined 角色）一律拒绝', () => {
    expect(can(undefined, 'route.alerts')).toBe(false)
    expect(can(undefined, 'admin.config')).toBe(false)
  })

  it('矩阵覆盖五个角色且 admin 全量', () => {
    expect(Object.keys(PERMISSION_MATRIX)).toEqual([...ROLES])
    expect(PERMISSION_MATRIX.admin.length).toBeGreaterThan(PERMISSION_MATRIX.viewer.length)
  })
})
