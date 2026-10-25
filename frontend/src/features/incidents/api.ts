import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '../../shared/api/client'
import { qk } from '../../shared/lib/query-keys'
import type { Incident, IncidentDetail, Postmortem } from '../../shared/api/types'
import { toast } from '../../shared/ui/toast'

export function useIncidents() {
  return useQuery({
    queryKey: qk.incidents.list({ limit: 200 }),
    queryFn: async () => {
      const res = await api.GET('/incidents', { params: { query: { limit: 200 } } })
      return unwrap(res)
    },
  })
}

export function useIncident(id: number | null) {
  return useQuery({
    queryKey: qk.incidents.detail(id ?? 0),
    queryFn: async () => {
      if (id === null) throw new Error('unreachable')
      const res = await api.GET('/incidents/{id}', { params: { path: { id: id } } })
      return unwrap<IncidentDetail>(res)
    },
    enabled: id !== null,
  })
}

export function usePostmortem(id: number | null, enabled: boolean) {
  return useQuery({
    queryKey: qk.incidents.postmortem(id ?? 0),
    queryFn: async () => {
      if (id === null) throw new Error('unreachable')
      const res = await api.GET('/incidents/{id}/postmortem', { params: { path: { id: id } } })
      return unwrap<Postmortem>(res)
    },
    enabled: id !== null && enabled,
    retry: false,
  })
}

function useInvalidate() {
  const qc = useQueryClient()
  return () => {
    void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'incidents' })
    void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'nav-badge' })
  }
}

/** 事件状态推进（领域 §6 状态机；非法迁移由后端 409，前端不预判） */
export type IncidentAction = 'acknowledge' | 'mitigate' | 'resolve' | 'close' | 'cancel'

export function useIncidentAction() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: async ({
      id,
      action,
      body,
    }: {
      id: number
      action: IncidentAction
      body?: { cancelled_reason?: string }
    }) => {
      const res = await api.POST(`/incidents/{id}/${action}`, {
        params: { path: { id } },
        body: action === 'cancel' ? { cancelled_reason: body?.cancelled_reason ?? '' } : undefined,
      })
      return unwrap(res)
    },
    onSuccess: (_incident, vars) => {
      invalidate()
      const labels: Record<IncidentAction, string> = {
        acknowledge: '已确认处理',
        mitigate: '止血完成',
        resolve: '根因恢复',
        close: '事件已关闭',
        cancel: '已误报关闭',
      }
      const isClose = vars.action === 'close' && ['P1', 'P2'].includes(_incident.severity)
      toast.show({
        title: labels[vars.action],
        description: isClose
          ? 'P1/P2 事件关闭将生成复盘模板（L3 链路）；操作已留痕'
          : '操作已留痕（BR-10）',
        variant: 'ok',
      })
    },
  })
}

/** 处理记录（人工时间线条目追加，FR-32；契约 POST /incidents/{id}/notes） */
export function useAddTimelineNote() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, note }: { id: number; note: string }) => {
      const res = await api.POST('/incidents/{id}/notes', {
        params: { path: { id } },
        body: { note },
      })
      return unwrap<Incident>(res)
    },
    onSuccess: (_r, vars) => {
      void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'incidents' })
      toast.show({
        title: '处理记录已提交',
        description: `「${vars.note.slice(0, 24)}…」已计入时间线`,
        variant: 'ok',
      })
    },
  })
}

/** 状态页同步/撤回（BR-06）；契约响应为 StatusPageEntry，这里只消费副作用 */
export function useStatusPageSync() {
  const invalidate = useInvalidate()
  const sync = useMutation({
    mutationFn: async ({ id, undo }: { id: number; undo?: boolean }) => {
      const res = undo
        ? await api.POST('/incidents/{id}/status-page/undo', { params: { path: { id } } })
        : await api.POST('/incidents/{id}/status-page/sync', { params: { path: { id } } })
      return unwrap<unknown>(res)
    },
    onSuccess: (_result, vars) => {
      invalidate()
      toast.show({
        title: vars.undo ? '状态页同步已撤回' : '已同步状态页',
        description: 'P1/P2 事件状态变更自动同步状态页，同步可人工撤回（BR-06）',
        variant: 'ok',
      })
    },
  })
  return { sync }
}
