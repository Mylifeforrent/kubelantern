import { useMutation, useQuery, keepPreviousData } from '@tanstack/react-query'
import { useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '../../shared/api/client'
import { qk, type AlertFilters } from '../../shared/lib/query-keys'
import type { Alert, SuppressSuggestionRequest } from '../../shared/api/types'
import { toast } from '../../shared/ui/toast'

/** 告警列表（URL filters 直接进 key，§4.2「URL 即状态」） */
export function useAlerts(filters: AlertFilters) {
  return useQuery({
    queryKey: qk.alerts.list(filters),
    queryFn: async () => {
      const res = await api.GET('/alerts', {
        params: {
          query: {
            ...filters,
            severity: filters.severity as 'info' | 'warning' | 'critical' | undefined,
            status: filters.status as Alert['status'] | undefined,
          },
        },
      })
      return unwrap(res)
    },
    placeholderData: keepPreviousData,
  })
}

export function useAlert(id: number | null) {
  return useQuery({
    queryKey: qk.alerts.detail(id ?? 0),
    queryFn: async () => {
      if (id === null) throw new Error('unreachable')
      const res = await api.GET('/alerts/{id}', { params: { path: { id: id } } })
      return unwrap(res)
    },
    enabled: id !== null,
  })
}

/** 告警级 AI 解释（P1；无权限/未生成时后端 404/空集 → 空态） */
export function useAlertExplanations(id: number | null, enabled: boolean) {
  return useQuery({
    queryKey: qk.alerts.explanations(id ?? 0),
    queryFn: async () => {
      if (id === null) throw new Error('unreachable')
      const res = await api.GET('/alerts/{id}/explanations', { params: { path: { id: id } } })
      return unwrap(res)
    },
    enabled: id !== null && enabled,
  })
}

function useInvalidates() {
  const qc = useQueryClient()
  return () => {
    void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'alerts' })
    void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'nav-badge' })
  }
}

export function useAckAlert() {
  const invalidate = useInvalidates()
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await api.POST('/alerts/{id}/ack', { params: { path: { id } } })
      return unwrap(res)
    },
    onSuccess: () => {
      invalidate()
      toast.show({
        title: '已认领告警',
        description: '升级链已停止；操作已留痕（BR-08/BR-10）',
        variant: 'ok',
      })
    },
  })
}

export function useCloseAlert() {
  const invalidate = useInvalidates()
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await api.POST('/alerts/{id}/close', { params: { path: { id } } })
      return unwrap(res)
    },
    onSuccess: () => {
      invalidate()
      toast.show({
        title: '告警已关闭',
        description: '状态已记录为 resolved；操作已留痕（BR-10）',
        variant: 'ok',
      })
    },
  })
}

export function useConvertAlert() {
  const qc = useQueryClient()
  const invalidate = useInvalidates()
  return useMutation({
    mutationFn: async ({
      id,
      body,
    }: {
      id: number
      body?: { title: string; severity: 'P1' | 'P2' | 'P3' | 'P4' }
    }) => {
      const res = await api.POST('/alerts/{id}/convert-to-incident', {
        params: { path: { id } },
        body,
      })
      return unwrap(res)
    },
    onSuccess: (incident) => {
      invalidate()
      void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'incidents' })
      toast.show({
        title: '已立项事件',
        description: `事件 #${incident.id} 已创建并关联本告警`,
        variant: 'ok',
        action: {
          label: '前往事件',
          onClick: () => window.location.assign(`/incidents/${incident.id}`),
        },
      })
    },
  })
}

/** 抑制建议提交（降噪反馈池；契约 /alerts/{id}/suppress-suggestion） */
export function useSuppressSuggestion() {
  const invalidate = useInvalidates()
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: SuppressSuggestionRequest }) => {
      const res = await api.POST('/alerts/{id}/suppress-suggestion', {
        params: { path: { id } },
        body,
      })
      return unwrap(res)
    },
    onSuccess: () => {
      invalidate()
      toast.show({
        title: '抑制建议已提交',
        description: '已进入降噪反馈池，规则调优时复核；操作已留痕（BR-10）',
        variant: 'ok',
      })
    },
  })
}
