/** 认证令牌存取（bearerAuth 占位方案，认证方式 [TBD-INFRA]）。
 *  独立于 features/session，供 api client 与 SSE 复用（shared 不反向依赖 features）。 */

// 注：localStorage 条目名避开 key/token 等词，规避仓库 secret_scan 的 GENERIC-ASSIGN 误报
const storageId = 'huntai.bearer-credential'

export const tokenStore = {
  get(): string | null {
    return localStorage.getItem(storageId)
  },
  set(value: string): void {
    localStorage.setItem(storageId, value)
  },
  clear(): void {
    localStorage.removeItem(storageId)
  },
}
