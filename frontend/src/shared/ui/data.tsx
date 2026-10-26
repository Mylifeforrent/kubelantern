/** 数据展示件（hifi §4.5/§4.6）：统计卡、管道步骤卡、kv、代码块、链接行、空态、
 *  aibox、rulebox+simbar、步进条、时间线、迷你柱状图、预算条、tabs。 */
import type { JSX, ReactNode } from 'react'
import { cn } from '../lib/cn'
import { Icon, type IconName } from './icon'

/* ------------------------------ 统计卡（§4.5 stat） ------------------------------ */
export function StatCard({
  label,
  icon,
  value,
  sub,
  iconClass,
}: {
  label: string
  icon?: IconName
  value: ReactNode
  sub?: ReactNode
  iconClass?: string
}): JSX.Element {
  return (
    <div className="stat">
      <div className="l">
        {icon && <Icon name={icon} size={13} className={iconClass} />}
        {label}
      </div>
      <div className="v num">{value}</div>
      {sub !== undefined && <div className="s">{sub}</div>}
    </div>
  )
}

/* ------------------------------ 管道步骤卡（§4.5 pstep） ------------------------------ */
export function PStepCard({
  label,
  icon,
  value,
  sub,
  active,
  arrow,
}: {
  label: string
  icon: IconName
  value: ReactNode
  sub: string
  active?: boolean
  arrow?: boolean
}): JSX.Element {
  return (
    <div className={cn('pstep', active && 'on')}>
      <div className="pl">
        <Icon name={icon} size={12} />
        {label}
      </div>
      <div className="pv num">{value}</div>
      <div className="ps">{sub}</div>
      {arrow && <Icon name="chr" size={12} className="pstep-arrow" />}
    </div>
  )
}

/* ------------------------------ kv 键值网格 ------------------------------ */
export function Kv({ rows }: { rows: [string, ReactNode][] }): JSX.Element {
  return (
    <dl className="kv">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  )
}

/* ------------------------------ 代码块（pre.code） ------------------------------ */
export function CodeBlock({
  lines,
  text,
  ariaLabel,
}: {
  lines?: { kind: 'add' | 'del' | 'ctx'; content: string }[]
  text?: string
  ariaLabel?: string
}): JSX.Element {
  return (
    <pre className="code" aria-label={ariaLabel}>
      {lines
        ? lines.map((l, i) => (
            <span key={i} className={l.kind === 'ctx' ? undefined : l.kind}>
              {l.kind === 'add' ? '+ ' : l.kind === 'del' ? '- ' : ''}
              {l.content}
              {'\n'}
            </span>
          ))
        : text}
    </pre>
  )
}

/* ------------------------------ 链接行（linklist） ------------------------------ */
export function LinkList({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}): JSX.Element {
  return <div className={cn('linklist', className)}>{children}</div>
}

export function LinkItem({
  icon,
  children,
  right,
  onClick,
  readOnly,
}: {
  icon?: IconName
  children: ReactNode
  right?: ReactNode
  onClick?: () => void
  readOnly?: boolean
}): JSX.Element {
  if (readOnly || onClick === undefined) {
    return (
      <div className={cn('linkitem', readOnly && 'ro')}>
        {icon && <Icon name={icon} size={13} className="text-tx2" />}
        <span className="flex-1 min-w-0">{children}</span>
        {right}
      </div>
    )
  }
  return (
    <button type="button" className="linkitem" onClick={onClick}>
      {icon && <Icon name={icon} size={13} className="text-tx2" />}
      <span className="flex-1 min-w-0">{children}</span>
      {right}
    </button>
  )
}

/* ------------------------------ 空态 ------------------------------ */
export function Empty({
  text,
  sub,
  icon,
}: {
  text: string
  sub?: string
  icon?: IconName
}): JSX.Element {
  return (
    <div className="empty">
      {icon && (
        <div className="mb-2 flex justify-center text-dim">
          <Icon name={icon} size={20} />
        </div>
      )}
      {text}
      {sub && <div className="sub">{sub}</div>}
    </div>
  )
}

/* ------------------------------ aibox（§4.5） ------------------------------ */
export function Aibox({
  title,
  children,
  footnote,
  variant,
  tag,
}: {
  title: ReactNode
  children: ReactNode
  footnote?: ReactNode
  variant?: 'ai' | 'warn' | 'info'
  tag?: ReactNode
}): JSX.Element {
  return (
    <div className={cn('aibox', variant !== 'ai' && variant)}>
      <div className="aibox-h">
        {variant === 'warn' ? <Icon name="warn" size={14} /> : <Icon name="spark" size={14} />}
        {title}
        {tag}
      </div>
      <div className="aibox-b">{children}</div>
      {footnote !== undefined && <div className="aibox-f">{footnote}</div>}
    </div>
  )
}

/* ------------------------------ rulebox + simbar ------------------------------ */
export function RuleBox({
  ruleCode,
  description,
  window_,
  similarity,
  children,
}: {
  ruleCode: string
  description: string
  window_: string
  similarity?: number | null
  children?: ReactNode
}): JSX.Element {
  return (
    <div className="rulebox">
      <div>
        命中规则 <b>{ruleCode}</b> · {description} · 时间窗 {window_}
      </div>
      {similarity != null && (
        <div className="flex items-center gap-2 mt-2">
          <span
            className="simbar"
            role="img"
            aria-label={`相似度 ${Math.round(similarity * 100)}%`}
          >
            <i style={{ width: `${Math.round(similarity * 100)}%` }} />
          </span>
          <span className="tiny text-tx2 num">相似度 {Math.round(similarity * 100)}%</span>
        </div>
      )}
      {children}
    </div>
  )
}

/* ------------------------------ 步进条（§4.6 steps） ------------------------------ */
export function Stepper({
  steps,
  current,
}: {
  steps: { key: string; label: string }[]
  current: string
}): JSX.Element {
  const idx = steps.findIndex((s) => s.key === current)
  return (
    <div className="steps" aria-label="状态机步进条">
      {steps.map((s, i) => (
        <div
          key={s.key}
          className={cn('s', i < idx && 'done', i === idx && 'cur')}
          aria-current={i === idx ? 'step' : undefined}
        >
          <div className="bar" />
          <div className="lab">{s.label}</div>
        </div>
      ))}
    </div>
  )
}

/* ------------------------------ 时间线（§4.6 tl） ------------------------------ */
export type TimelineKind = 'auto' | 'man' | 'esc' | 'ai'

export function Timeline({
  items,
}: {
  items: { key: string; kind: TimelineKind; time: string; text: ReactNode }[]
}): JSX.Element {
  return (
    <div className="tl">
      {items.map((it) => (
        <div key={it.key} className={cn('tl-item', it.kind)}>
          <div className="tt">{it.time}</div>
          <div className="tx">{it.text}</div>
        </div>
      ))}
    </div>
  )
}

/* ------------------------------ 迷你柱状图（§4.5 bars） ------------------------------ */
export function Bars({
  data,
  ariaLabel,
}: {
  data: { label: string; warn: number; info: number; max: number }[]
  ariaLabel: string
}): JSX.Element {
  return (
    <div role="img" aria-label={ariaLabel}>
      <div className="bars">
        {data.map((d) => (
          <div key={d.label} className="bcol">
            <div className="bwarn" style={{ height: `${(d.warn / d.max) * 100}%` }} />
            <div className="binfo" style={{ height: `${(d.info / d.max) * 100}%` }} />
          </div>
        ))}
      </div>
      <div className="flex gap-1 mt-1">
        {data.map((d) => (
          <div key={d.label} className="blab flex-1">
            {d.label}
          </div>
        ))}
      </div>
    </div>
  )
}

/* ------------------------------ 预算进度条（§4.4） ------------------------------ */
export function BudgetBar({ ratio }: { ratio: number }): JSX.Element {
  return (
    <span
      className={cn('budget', ratio > 0.9 && 'hot')}
      role="img"
      aria-label={`预算已用 ${Math.round(ratio * 100)}%`}
    >
      <i style={{ width: `${Math.min(100, Math.round(ratio * 100))}%` }} />
    </span>
  )
}

/* ------------------------------ tabs（§4.8） ------------------------------ */
export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: string; label: string }[]
  active: string
  onChange: (k: string) => void
}): JSX.Element {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={active === t.key}
          className={cn('tab', active === t.key && 'on')}
          onClick={() => onChange(t.key)}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

/* ------------------------------ 卡片 ------------------------------ */
export function Card({
  header,
  icon,
  right,
  children,
  className,
  bodyClass,
}: {
  header?: ReactNode
  icon?: IconName
  right?: ReactNode
  children: ReactNode
  className?: string
  bodyClass?: string
}): JSX.Element {
  return (
    <section className={cn('card', className)}>
      {header !== undefined && (
        <div className="card-h">
          {icon && <Icon name={icon} size={13} />}
          {header}
          {right !== undefined && <div className="ml-auto flex items-center gap-2">{right}</div>}
        </div>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  )
}

export function PageHeader({
  title,
  sub,
  actions,
}: {
  title: string
  sub?: ReactNode
  actions?: ReactNode
}): JSX.Element {
  return (
    <div className="ph">
      <div>
        <h1>{title}</h1>
        {sub && <p>{sub}</p>}
      </div>
      <div className="flex-1" />
      {actions !== undefined && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}
