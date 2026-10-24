import { create } from 'zustand'
import type { User } from '../../shared/api/types'
import type { Role } from '../../shared/types/permissions'

/**
 * 当前会话用户（zustand 三类全局态之一，03-frontend-design §1.2.3）。
 * 角色获取方式随认证 [TBD-INFRA]；登录页的演示角色选择为原型演示装置（hifi §4.9，生产不保留）。
 */
interface SessionState {
  user: User | null
  setUser: (u: User) => void
  clear: () => void
}

export const useSessionStore = create<SessionState>()((set) => ({
  user: null,
  setUser: (user) => set({ user }),
  clear: () => set({ user: null }),
}))

/** 当前角色（UserRoleGrant.role_code → 权限位 Role）；契约字段为 role_code */
export function useRole(): Role | undefined {
  return useSessionStore((s) => s.user?.roles?.[0]?.role_code)
}
