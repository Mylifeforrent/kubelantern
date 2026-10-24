import { QueryClient } from '@tanstack/react-query'
import { toast } from '../ui/toast'
import { describeProblem } from '../api/problem'

/**
 * QueryClient 约定（03-frontend-design §4.2）：
 * staleTime 列表 30s / 配置类 60s；mutation 统一 onError toast（错误文案按 problem.code 映射）。
 */
export function createAppQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
      mutations: {
        onError: (error) => {
          toast.show({
            title: '操作失败',
            description: describeProblem(error),
            variant: 'err',
          })
        },
      },
    },
  })
}
