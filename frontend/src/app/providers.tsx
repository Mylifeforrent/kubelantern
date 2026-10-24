/** 应用装配层（03-frontend-design §2.1）：QueryClient + Toast + Realtime 桥。 */
import { useState, type JSX } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { createAppQueryClient } from '../shared/lib/query-client'
import { Toaster } from '../shared/ui/toast'
import { useRealtimeBridge } from '../shared/api/realtime/use-realtime'

/** Realtime 桥必须在 QueryClientProvider 内部（依赖 useQueryClient） */
function RealtimeBridge(): null {
  useRealtimeBridge()
  return null
}

export function Providers({ children }: { children: React.ReactNode }): JSX.Element {
  const [queryClient] = useState(createAppQueryClient)
  return (
    <QueryClientProvider client={queryClient}>
      <RealtimeBridge />
      {children}
      <Toaster />
    </QueryClientProvider>
  )
}
