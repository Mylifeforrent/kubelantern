import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '../../shared/api/client'
import { qk } from '../../shared/lib/query-keys'
import type { Cluster } from '../../shared/api/types'
import { toast } from '../../shared/ui/toast'

export function useClusters() {
  return useQuery({
    queryKey: qk.inspections.clusters(),
    queryFn: async () => {
      const res = await api.GET('/clusters', { params: { query: { limit: 100 } } })
      return unwrap(res)
    },
  })
}

export function useFindings(clusterId: number, severity?: string) {
  return useQuery({
    queryKey: qk.inspections.findings(clusterId, { limit: 200, severity }),
    queryFn: async () => {
      const res = await api.GET('/findings', {
        params: {
          query: {
            cluster_id: clusterId,
            severity: severity as 'info' | 'warning' | 'critical' | undefined,
            limit: 200,
          },
        },
      })
      return unwrap(res)
    },
  })
}

export function useRuns(clusterId: number) {
  return useQuery({
    queryKey: qk.inspections.runs(clusterId),
    queryFn: async () => {
      const res = await api.GET('/inspection-runs', {
        params: { query: { cluster_id: clusterId, limit: 50 } },
      })
      return unwrap(res)
    },
  })
}

export function usePolicies(clusterId?: number) {
  return useQuery({
    queryKey: qk.inspections.policies(clusterId),
    queryFn: async () => {
      const res = await api.GET('/inspection-policies', {
        params: { query: { cluster_id: clusterId, limit: 100 } },
      })
      return unwrap(res)
    },
  })
}

export function useInspectionRules() {
  return useQuery({
    queryKey: qk.inspections.rules(),
    queryFn: async () => {
      const res = await api.GET('/inspection-rules', { params: { query: { limit: 200 } } })
      return unwrap(res)
    },
  })
}

function useInvalidateFindings() {
  const qc = useQueryClient()
  return () => {
    void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'findings' })
    void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'inspection-runs' })
    void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'nav-badge' })
  }
}

export function useFindingActions() {
  const invalidate = useInvalidateFindings()
  const ack = useMutation({
    mutationFn: async (id: number) => {
      const res = await api.POST('/findings/{id}/ack', { params: { path: { id } } })
      return unwrap(res)
    },
    onSuccess: () => {
      invalidate()
      toast.show({ title: '已认领发现', description: '操作已留痕（BR-10）', variant: 'ok' })
    },
  })
  const ignore = useMutation({
    mutationFn: async ({ id, reason }: { id: number; reason: string }) => {
      const res = await api.POST('/findings/{id}/ignore', {
        params: { path: { id } },
        body: { ignored_reason: reason },
      })
      return unwrap(res)
    },
    onSuccess: () => {
      invalidate()
      toast.show({ title: '发现已忽略', description: '忽略原因已记录（D-10）', variant: 'ok' })
    },
  })
  const reopen = useMutation({
    mutationFn: async (id: number) => {
      const res = await api.POST('/findings/{id}/reopen', { params: { path: { id } } })
      return unwrap(res)
    },
    onSuccess: () => {
      invalidate()
      toast.show({ title: '发现已重新打开', variant: 'ok' })
    },
  })
  const explain = useMutation({
    mutationFn: async (id: number) => {
      const res = await api.POST('/findings/{id}/explain', { params: { path: { id } } })
      return unwrap<{ task_id?: number; id: number }>(res)
    },
    onSuccess: () => {
      invalidate()
      toast.show({
        title: 'AI 解释已触发',
        description: 'A1 链路：脱敏（BR-01）→ 模型路由（BR-12）→ 预算（BR-03）',
        variant: 'ai',
        action: { label: '前往 AI 任务中心', onClick: () => window.location.assign('/ai/tasks') },
      })
    },
  })
  return { ack, ignore, reopen, explain }
}

export type ClusterItem = Cluster
