import { format, formatDistanceToNow, parseISO } from 'date-fns'
import { zhCN } from 'date-fns/locale'

/**
 * 时间工具（05-fe-be-boundary §6 AP-9）：契约时间一律 UTC ISO 8601（Z 后缀）。
 * 禁止手工解析/拼接时间字符串——一律经本模块（date-fns parseISO 正确处理时区），
 * 展示本地化（领域 §5.2）。
 */
export function parseTime(iso: string): Date {
  return parseISO(iso)
}

/** 绝对时间：MM-dd HH:mm（当年内）；跨年带年份 */
export function formatDateTime(iso: string): string {
  const d = parseISO(iso)
  return d.getFullYear() === new Date().getFullYear()
    ? format(d, 'MM-dd HH:mm')
    : format(d, 'yyyy-MM-dd HH:mm')
}

/** 相对时间：x 分钟前 / x 小时前 … */
export function formatRelative(iso: string): string {
  return formatDistanceToNow(parseISO(iso), { addSuffix: true, locale: zhCN })
}

/** 时间戳：HH:mm:ss（时间线用） */
export function formatClock(iso: string): string {
  return format(parseISO(iso), 'HH:mm:ss')
}

export function formatNumber(n: number): string {
  return n.toLocaleString('zh-CN')
}

export function formatPercent(ratio: number): string {
  return `${Math.round(ratio * 100)}%`
}
