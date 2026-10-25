/** 应用骨架（widgets/app-shell）：侧栏 228px + 顶栏 52px + 内容区唯一滚动。
 *  导航五组与徽标计数对齐原型 §2.2；计数为展示优化，权限数据过滤以后端为准。 */
import { useQuery } from '@tanstack/react-query'
import type { JSX } from 'react'
import { Link, Outlet, useLocation } from 'react-router'
import { api } from '../../shared/api/client'
import { can, ROLE_LABELS } from '../../shared/types/permissions'
import { useSessionStore, useRole } from '../../features/session'
import { GlobalSearch } from '../global-search'
import { AiStatusBanner } from '../ai-status-banner'
import { Icon, type IconName } from '../../shared/ui/icon'
import { Bdg } from '../../shared/ui/chips'
import { logout } from '../../features/session/api'

interface NavItem {
  to: string
  label: string
  icon: IconName
  perm: Parameters<typeof can>[1]
  badge?: 'alerts' | 'candidates' | 'incidents' | 'aiPending'
  tag?: string
  purpleBadge?: boolean
}

const GROUPS: { title: string; items: NavItem[] }[] = [
  {
    title: '数据面',
    items: [
      { to: '/alerts', label: '告警工作台', icon: 'siren', perm: 'route.alerts', badge: 'alerts' },
      {
        to: '/candidates',
        label: '候选事件',
        icon: 'layers',
        perm: 'route.candidates',
        badge: 'candidates',
      },
    ],
  },
  {
    title: '控制面',
    items: [
      {
        to: '/incidents',
        label: '事件响应',
        icon: 'zap',
        perm: 'route.incidents',
        badge: 'incidents',
      },
      { to: '/oncall', label: '排班与升级', icon: 'cal', perm: 'route.oncall' },
    ],
  },
  {
    title: '运营面',
    items: [
      { to: '/inspections', label: '巡检看板', icon: 'radar', perm: 'route.inspections' },
      { to: '/workflows', label: 'Workflow 编排', icon: 'branch', perm: 'route.admin', tag: 'P3' },
    ],
  },
  {
    title: '智能面',
    items: [
      {
        to: '/ai/tasks',
        label: 'AI 任务中心',
        icon: 'spark',
        perm: 'route.ai-tasks',
        badge: 'aiPending',
        purpleBadge: true,
      },
    ],
  },
  {
    title: '系统',
    items: [{ to: '/admin', label: '管理后台', icon: 'gear', perm: 'route.admin' }],
  },
]

/** 侧栏徽标计数（轻量查询；SSE 事件失效后自动刷新） */
function useNavBadges(): Record<string, number> {
  const role = useRole()
  const { data: alertsData } = useQuery({
    queryKey: ['nav-badge', 'alerts'],
    queryFn: async () => {
      const res = await api.GET('/alerts', {
        params: {
          query: { limit: 200, severity: undefined as 'info' | 'warning' | 'critical' | undefined },
        },
      })
      const items = res.data?.items ?? []
      return items.filter((a) => ['notified', 'correlated'].includes(a.status)).length
    },
    enabled: can(role, 'route.alerts'),
    refetchInterval: false,
  })
  const { data: candData } = useQuery({
    queryKey: ['nav-badge', 'candidates'],
    queryFn: async () => {
      const res = await api.GET('/incident-candidates', { params: { query: { limit: 200 } } })
      const items = res.data?.items ?? []
      return items.filter((c) => c.status === 'pending').length
    },
    enabled: can(role, 'route.candidates'),
  })
  const { data: incData } = useQuery({
    queryKey: ['nav-badge', 'incidents'],
    queryFn: async () => {
      const res = await api.GET('/incidents', { params: { query: { limit: 200 } } })
      const items = res.data?.items ?? []
      return items.filter((i) => ['open', 'acknowledged'].includes(i.status)).length
    },
    enabled: can(role, 'route.incidents'),
  })
  const { data: aiData } = useQuery({
    queryKey: ['nav-badge', 'ai-pending'],
    queryFn: async () => {
      const res = await api.GET('/ai/tasks', {
        params: { query: { status: 'pending_approval', limit: 1 } },
      })
      return res.data?.total ?? 0
    },
    enabled: can(role, 'route.ai-tasks'),
  })
  return {
    alerts: alertsData ?? 0,
    candidates: candData ?? 0,
    incidents: incData ?? 0,
    aiPending: aiData ?? 0,
  }
}

export function AppShell(): JSX.Element {
  const user = useSessionStore((s) => s.user)
  const role = useRole()
  const location = useLocation()
  const badges = useNavBadges()

  return (
    <div className="h-full flex" style={{ position: 'relative' }}>
      <aside className="side">
        <div className="logo">
          <span className="logo-mark">
            <Icon name="eye2" size={17} />
          </span>
          <div>
            <b>HuntAI SRE</b>
            <small>Kubernetes 智能运维平台</small>
          </div>
        </div>
        {GROUPS.map((g) => {
          const items = g.items.filter((it) => can(role, it.perm))
          if (items.length === 0) return null
          return (
            <div key={g.title}>
              <div className="navgrp">{g.title}</div>
              {items.map((it) => {
                const active =
                  location.pathname === it.to || location.pathname.startsWith(`${it.to}/`)
                return (
                  <Link
                    key={it.to}
                    to={it.to}
                    className={active ? 'nav on' : 'nav'}
                    aria-current={active ? 'page' : undefined}
                  >
                    <Icon name={it.icon} size={16} className="ic" />
                    <span>{it.label}</span>
                    {it.tag && <span className="tag pu">{it.tag}</span>}
                    {it.badge && <Bdg count={badges[it.badge] ?? 0} purple={it.purpleBadge} />}
                  </Link>
                )
              })}
            </div>
          )
        })}
        <div className="side-foot">
          <span className="dot-ok" />
          告警接入层正常 · {import.meta.env.VITE_USE_MOCK === '1' ? '演示数据' : '生产数据'}
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="topbar">
          <span className="env">
            <Icon name="shield" size={12} />
            内网
          </span>
          <GlobalSearch />
          <div className="flex-1" />
          {role && (
            <span className="rolebox" aria-label="当前角色">
              <Icon name="user" size={13} />
              <b>{ROLE_LABELS[role]}</b>
            </span>
          )}
          <button className="iconbtn" aria-label="通知">
            <Icon name="bell" size={16} />
            <span className="pip num">2</span>
          </button>
          <span className="avatar" aria-label={user?.display_name}>
            {(user?.display_name ?? '?').slice(0, 1)}
          </span>
          <button className="ibtn" aria-label="退出登录" title="退出登录" onClick={() => logout()}>
            <Icon name="chl" size={14} />
          </button>
        </header>
        <AiStatusBanner />
        <main className="flex-1 overflow-y-auto px-6 pt-6 pb-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
