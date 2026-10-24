/** 路由守卫（03-frontend-design §3.2）：RequireAuth → RequireRole，不命中跳 403/登录。
 *  前端权限只做展示控制，后端权威。 */
import type { JSX, ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { useSessionStore, useRole } from '../../features/session'
import { can, type Permission } from '../../shared/types/permissions'

export function RequireAuth({ children }: { children: JSX.Element }): JSX.Element {
  const user = useSessionStore((s) => s.user)
  const location = useLocation()
  if (!user) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />
  }
  return children
}

export function RequireRole({
  perm,
  children,
}: {
  perm: Permission
  children: ReactNode
}): JSX.Element {
  const role = useRole()
  if (!can(role, perm)) {
    return <Navigate to="/403" replace />
  }
  return children as JSX.Element
}
