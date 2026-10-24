/**
 * 错误规约（03-frontend-design §4.1 / 05-fe-be-boundary §1）：
 * 后端唯一权威结构 = RFC 7807 problem+json（含 code/trace_id 扩展，04-backend §4.4）。
 * `detail` 是面向开发者的诊断信息，禁止直接当 UI 文案（AP-2）；
 * 用户文案由前端按 code 映射（错误码清单位 [ASSUMPTION]，随 04-api 定稿固化）。
 */

export interface Problem {
  type?: string
  title?: string
  status?: number
  detail?: string
  instance?: string
  code?: string
  trace_id?: string
}

export class ApiError extends Error {
  readonly problem: Problem

  constructor(problem: Problem) {
    super(problem.title ?? `HTTP ${problem.status ?? ''}`)
    this.name = 'ApiError'
    this.problem = problem
  }

  get status(): number | undefined {
    return this.problem.status
  }
}

export function toProblem(input: unknown): Problem {
  if (input && typeof input === 'object' && !Array.isArray(input)) {
    const obj = input as Record<string, unknown>
    if ('status' in obj || 'title' in obj || 'code' in obj) {
      return {
        type: str(obj.type),
        title: str(obj.title),
        status: typeof obj.status === 'number' ? obj.status : undefined,
        detail: str(obj.detail),
        instance: str(obj.instance),
        code: str(obj.code),
        trace_id: str(obj.trace_id),
      }
    }
  }
  return { title: '请求失败', detail: typeof input === 'string' ? input : undefined }
}

function str(v: unknown): string | undefined {
  return typeof v === 'string' && v.length > 0 ? v : undefined
}

/** 错误码 → 用户文案映射（code 缺失时按状态码兜底；detail 不直出）。
 *  注：登录凭据类错误（401）由状态码兜底文案覆盖。 */
const CODE_MESSAGES: Record<string, string> = {
  ALERT_STATE_CONFLICT: '告警状态已变化，请刷新后重试',
  INCIDENT_STATE_CONFLICT: '事件状态已变化，请刷新后重试',
  FINDING_STATE_CONFLICT: '发现状态已变化，请刷新后重试',
  BUDGET_EXCEEDED: 'AI 预算已耗尽，任务被优雅终止',
  AI_UNAVAILABLE: 'AI 服务暂不可用，已进入 NoAI 降级模式',
}

const STATUS_MESSAGES: Record<number, string> = {
  400: '请求参数非法',
  401: '登录已失效，请重新登录',
  403: '当前角色没有执行该操作的权限',
  404: '目标资源不存在（或无权访问）',
  409: '状态冲突，请刷新后重试',
  429: '请求过于频繁，请稍后重试',
  500: '服务内部错误，请稍后重试',
}

export function describeProblem(error: unknown): string {
  const problem = error instanceof ApiError ? error.problem : toProblem(error)
  const byCode = problem.code ? CODE_MESSAGES[problem.code] : undefined
  if (byCode) return byCode
  const byStatus = problem.status ? STATUS_MESSAGES[problem.status] : undefined
  if (byStatus) return byStatus
  return problem.title ?? '请求失败'
}
