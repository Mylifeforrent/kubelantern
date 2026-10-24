/**
 * 角色与权限位（03-frontend-design §3.2）。
 * 映射表以领域文档 01-domain-model.md §3 权限矩阵为唯一事实源；
 * 前端权限只做展示控制（菜单隐藏/按钮禁用），后端权威（05-fe-be-boundary §0）。
 */

export const ROLES = ['admin', 'sre', 'oncall_manager', 'developer', 'viewer'] as const
export type Role = (typeof ROLES)[number]

export const ROLE_LABELS: Record<Role, string> = {
  admin: '平台管理员',
  sre: 'SRE 工程师',
  oncall_manager: '值班经理',
  developer: '研发工程师',
  viewer: '访客',
}

/** 权限位清单（动作级，源自领域 §3 矩阵 + 前端 §3.1 路由角色列） */
export type Permission =
  // 路由可见性
  | 'route.alerts'
  | 'route.candidates'
  | 'route.incidents'
  | 'route.inspections'
  | 'route.ai-tasks'
  | 'route.oncall'
  | 'route.admin'
  // 告警
  | 'alert.ack' // admin/sre/developer(T)
  | 'alert.close' // admin/sre
  | 'alert.convert' // admin/sre/developer(T)
  | 'alert.suppress' // admin/sre（抑制建议入降噪反馈池）
  | 'alert.explain' // admin/sre/developer(T)（P1 AI 解释查看）
  // 候选事件
  | 'candidate.decide' // admin/sre/developer(T)（确认/驳回）
  // 事件
  | 'incident.manage' // admin/sre/developer(T)（状态推进/处理记录）
  | 'incident.status-page' // admin/sre（同步/撤回）
  | 'incident.postmortem.edit' // admin/sre
  // 巡检
  | 'finding.ack' // admin/sre/developer(T)
  | 'finding.ignore' // admin/sre
  | 'finding.explain' // admin/sre（AI 解释触发；info 级 BR-09 禁用）
  | 'inspection.policy' // admin/sre
  // AI 任务
  | 'ai.approve' // admin/sre(T)
  // 排班
  | 'oncall.edit' // admin/oncall_manager；sre 只读 [ASSUMPTION]（前端 §3.1）
  // 管理后台
  | 'admin.config' // admin
  | 'admin.audit' // admin

/**
 * 权限矩阵：角色 → 权限位集合（逐资源对照领域 §3 矩阵核对）。
 */
const M: Record<Role, readonly Permission[]> = {
  admin: [
    'route.alerts',
    'route.candidates',
    'route.incidents',
    'route.inspections',
    'route.ai-tasks',
    'route.oncall',
    'route.admin',
    'alert.ack',
    'alert.close',
    'alert.convert',
    'alert.suppress',
    'alert.explain',
    'candidate.decide',
    'incident.manage',
    'incident.status-page',
    'incident.postmortem.edit',
    'finding.ack',
    'finding.ignore',
    'finding.explain',
    'inspection.policy',
    'ai.approve',
    'oncall.edit',
    'admin.config',
    'admin.audit',
  ],
  sre: [
    'route.alerts',
    'route.candidates',
    'route.incidents',
    'route.inspections',
    'route.ai-tasks',
    'route.oncall', // sre 排班只读 [ASSUMPTION]（前端 §3.1，生产开放与否待确认）
    'alert.ack',
    'alert.close',
    'alert.convert',
    'alert.suppress',
    'alert.explain',
    'candidate.decide',
    'incident.manage',
    'incident.status-page',
    'incident.postmortem.edit',
    'finding.ack',
    'finding.ignore',
    'finding.explain',
    'inspection.policy',
    'ai.approve', // AI 审批限本团队（T），行级由后端过滤
  ],
  oncall_manager: [
    'route.alerts', // 告警只读
    'route.incidents', // 事件只读
    'route.oncall',
    'oncall.edit',
  ],
  developer: [
    'route.alerts', // T 限本团队（后端行级过滤）
    'route.candidates',
    'route.incidents',
    'route.inspections',
    'alert.ack', // T
    'alert.convert', // T
    'alert.explain', // T
    'candidate.decide', // T
    'incident.manage', // T
    'finding.ack', // 认领 finding（领域 §3 唯一显式写权）
  ],
  viewer: [],
}

export { M as PERMISSION_MATRIX }

/** 动作级权限判定：命中即渲染入口，否则隐藏/禁用（后端仍会拒绝绕过前端的请求） */
export function can(role: Role | undefined, perm: Permission): boolean {
  if (!role) return false
  return M[role].includes(perm)
}
