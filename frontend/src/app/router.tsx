/** 路由表（03-frontend-design §3.1）：全部路由 React.lazy 路由级代码分割（§6）；
 *  workflows 域 P3 才合入构建，此处不注册。 */
import { lazy, Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Navigate } from 'react-router'
import { AppShell } from '../widgets/app-shell'
import { RequireAuth, RequireRole } from './guards/guards'
import { refreshSession } from '../features/session/api'
import { LoginForm } from '../features/session'
import { ForbiddenPage, NotFoundPage } from './error-pages'

const AlertsPage = lazy(() => import('../features/alerts').then((m) => ({ default: m.AlertsPage })))
const CandidatesPage = lazy(() =>
  import('../features/alerts').then((m) => ({ default: m.CandidatesPage })),
)
const IncidentsPage = lazy(() =>
  import('../features/incidents').then((m) => ({ default: m.IncidentsPage })),
)
const IncidentDetailPage = lazy(() =>
  import('../features/incidents').then((m) => ({ default: m.IncidentDetailPage })),
)
const InspectionsPage = lazy(() =>
  import('../features/inspections').then((m) => ({ default: m.InspectionsPage })),
)
const AiTasksPage = lazy(() =>
  import('../features/ai-tasks').then((m) => ({ default: m.AiTasksPage })),
)
const OncallPage = lazy(() => import('../features/oncall').then((m) => ({ default: m.OncallPage })))
const AdminPage = lazy(() => import('../features/admin').then((m) => ({ default: m.AdminPage })))

/** 登录态恢复：刷新后先回填会话用户再渲染（守卫依赖 session store） */
async function bootstrap(): Promise<void> {
  await refreshSession()
}

export const router = createBrowserRouter([
  { path: '/login', element: <LoginForm /> },
  {
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    hydrateFallbackElement: <div className="h-full grid place-items-center text-dim">加载中…</div>,
    loader: bootstrap,
    children: [
      { path: '/', element: <Navigate to="/alerts" replace /> },
      guard('/alerts', 'route.alerts', <AlertsPage />),
      guard('/candidates', 'route.candidates', <CandidatesPage />),
      guard('/incidents', 'route.incidents', <IncidentsPage />),
      guard('/incidents/:incidentId', 'route.incidents', <IncidentDetailPage />),
      guard('/inspections', 'route.inspections', <InspectionsPage />),
      guard('/ai/tasks', 'route.ai-tasks', <AiTasksPage />),
      guard('/oncall', 'route.oncall', <OncallPage />),
      guard('/admin', 'route.admin', <AdminPage />),
    ],
  },
  { path: '/403', element: <ForbiddenPage /> },
  { path: '*', element: <NotFoundPage /> },
])

/** 路由级守卫 + Suspense 包裹（路由级代码分割 §6） */
function guard(path: string, perm: Parameters<typeof RequireRole>[0]['perm'], el: ReactNode) {
  return {
    path,
    element: (
      <Suspense fallback={<div className="p-6 text-dim text-[13px]">页面加载中…</div>}>
        <RequireRole perm={perm}>{el}</RequireRole>
      </Suspense>
    ),
  }
}
