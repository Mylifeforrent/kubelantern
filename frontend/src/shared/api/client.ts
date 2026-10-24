import createClient from 'openapi-fetch'
import type { paths } from './schema'
import { tokenStore } from './auth'
import { ApiError, toProblem } from './problem'

/**
 * API 客户端（03-frontend-design §4.1）：openapi-fetch 薄运行时 + 生成类型。
 * 所有请求收口于此（05-fe-be-boundary §6 AP-4：feature 内禁止私建 client / 手写 fetch）。
 * baseURL 默认同源 /api/v1；dev 经 Vite proxy 转 api 进程。
 * 注：fetch 以调用时委托（而非模块加载期快照），保证 mock 层（main.tsx 装配）可拦截。
 */
export const api = createClient<paths>({
  baseUrl: (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api/v1',
  fetch: (input: RequestInfo | URL, init?: RequestInit) => window.fetch(input, init),
})

const LOGIN_PATH = '/auth/token'

api.use({
  onRequest({ request }) {
    const value = tokenStore.get()
    if (value) request.headers.set('Authorization', `Bearer ${value}`)
    return request
  },
  onResponse({ request, response }) {
    if (response.status === 401 && !request.url.includes(LOGIN_PATH)) {
      // 会话失效：清凭据并跳登录（shared/api 统一处理，页面无感知）
      tokenStore.clear()
      const here = window.location.pathname + window.location.search
      window.location.assign(`/login?next=${encodeURIComponent(here)}`)
    }
    return response
  },
})

/**
 * openapi-fetch 返回 { data, error } 判别联合；mutation 场景统一 unwrap：
 * error（problem envelope）→ 抛 ApiError，由 query-client 全局 onError toast。
 */
export function unwrap<T>(result: { data?: T; error?: unknown }): T {
  if (result.error !== undefined && result.error !== null) {
    throw new ApiError(toProblem(result.error))
  }
  if (result.data === undefined) {
    throw new ApiError(toProblem({ title: '响应为空' }))
  }
  return result.data
}

/**
 * [ASSUMPTION] 契约待补端点的唯一逃生通道（AP-4 例外：仅限标注 [ASSUMPTION] 的端点，
 * 契约补录后必须迁回类型化 client）：走同一 baseURL 与认证头。
 */
export async function rawRequest<T>(
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<T> {
  const base = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api/v1'
  const headers: Record<string, string> = { 'content-type': 'application/json' }
  const bearer = tokenStore.get()
  if (bearer) headers.Authorization = `Bearer ${bearer}`
  const res = await fetch(`${base}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    throw new ApiError(toProblem(await res.json().catch(() => ({ status: res.status }))))
  }
  return (await res.json()) as T
}
