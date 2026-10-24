import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '../../shared/api/client'
import { qk } from '../../shared/lib/query-keys'
import type { AICallLog, AITask } from '../../shared/api/types'
import { toast } from '../../shared/ui/toast'
import { useRealtimeStore } from '../../shared/api/realtime/store'

/** AI 任务列表 + 动态轮询（§4.3）：存在 pending_approval 时 5s、否则 30s；
 *  页面不可见（visibilitychange）时暂停；推送通道并存兜底。 */
export function useAiTasks() {
  const disconnected = useRealtimeStore((s) => s.connection !== 'open')
  return useQuery({
    queryKey: qk.aiTasks.list({ limit: 200 }),
    queryFn: async () => {
      const res = await api.GET('/ai/tasks', { params: { query: { limit: 200 } } })
      return unwrap(res)
    },
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? []
      const hasPending = items.some((t) => t.status === 'pending_approval')
      return hasPending ? 5_000 : 30_000
    },
    refetchIntervalInBackground: false,
    enabled: true,
    // 断连降级：由 refetchInterval 兜底（[ASSUMPTION] 断连时缩短轮询由 P0 弱网演练校准）
    ...{ staleTime: disconnected ? 5_000 : 30_000 },
  })
}

export function useCallLogs(taskId: number | null) {
  return useQuery({
    queryKey: qk.aiTasks.callLogs(taskId ?? 0),
    queryFn: async () => {
      if (taskId === null) throw new Error('unreachable')
      const res = await api.GET('/ai/tasks/{id}/call-logs', { params: { path: { id: taskId } } })
      return unwrap(res)
    },
    enabled: taskId !== null,
  })
}

function useInvalidateAi() {
  const qc = useQueryClient()
  return () => {
    void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'ai-tasks' })
    void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'nav-badge' })
  }
}

export function useAiTaskActions() {
  const invalidate = useInvalidateAi()
  const approve = useMutation({
    mutationFn: async (id: number) => {
      const res = await api.POST('/ai/tasks/{id}/approve', { params: { path: { id } } })
      return unwrap<AITask>(res)
    },
    onSuccess: (t) => {
      invalidate()
      toast.show({
        title: `任务 #${t.id} 已批准`,
        description: '任务继续执行；操作已留痕（BR-02/BR-10）',
        variant: 'ai',
      })
    },
  })
  const cancel = useMutation({
    mutationFn: async (id: number) => {
      const res = await api.POST('/ai/tasks/{id}/cancel', { params: { path: { id } } })
      return unwrap<AITask>(res)
    },
    onSuccess: (t) => {
      invalidate()
      toast.show({
        title: `任务 #${t.id} 已取消`,
        description: '任务终止，上下文留存可重发',
        variant: 'warn',
      })
    },
  })
  return { approve, cancel }
}

export type CallLog = AICallLog
