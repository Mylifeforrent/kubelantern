/** 输入与筛选（hifi §4.3）：inp / seg 分段器 / radios 单选卡组 / switch 开关。 */
import type { ChangeEvent, JSX, ReactNode } from 'react'
import { cn } from '../lib/cn'

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>): JSX.Element {
  return <input {...props} className={cn('inp', props.className)} />
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>): JSX.Element {
  return <textarea {...props} className={cn('inp', props.className)} />
}

export function Select({
  value,
  onChange,
  options,
  placeholder,
  className,
  ariaLabel,
}: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
  placeholder?: string
  className?: string
  ariaLabel?: string
}): JSX.Element {
  return (
    <select
      className={cn('inp', className)}
      value={value}
      aria-label={ariaLabel}
      onChange={(e: ChangeEvent<HTMLSelectElement>) => onChange(e.target.value)}
    >
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

/** 分段器：options 全部受控展示，激活项高亮 */
export function Seg<T extends string>({
  value,
  onChange,
  options,
  ariaLabel,
}: {
  value: T
  onChange: (v: T) => void
  options: { value: T; label: string }[]
  ariaLabel?: string
}): JSX.Element {
  return (
    <div className="seg" role="group" aria-label={ariaLabel}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          className={cn(value === o.value && 'on')}
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

/** 单选卡组（驳回原因等 modal 表单用） */
export function RadioCards({
  name,
  value,
  onChange,
  options,
  ariaLabel,
}: {
  name: string
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string; description: string }[]
  ariaLabel?: string
}): JSX.Element {
  return (
    <div className="radios" role="radiogroup" aria-label={ariaLabel}>
      {options.map((o) => (
        <label key={o.value}>
          <input
            type="radio"
            name={name}
            value={o.value}
            checked={value === o.value}
            onChange={() => onChange(o.value)}
          />
          <span>
            <b className="block">{o.label}</b>
            <span className="text-tx2 text-[11.5px]">{o.description}</span>
          </span>
        </label>
      ))}
    </div>
  )
}

/** 开关（34×19 轨道） */
export function Switch({
  on,
  onChange,
  ariaLabel,
}: {
  on: boolean
  onChange: (v: boolean) => void
  ariaLabel?: string
}): JSX.Element {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={ariaLabel}
      className={cn('switch', on && 'on')}
      onClick={() => onChange(!on)}
    />
  )
}

export function Label({
  children,
  htmlFor,
}: {
  children: ReactNode
  htmlFor?: string
}): JSX.Element {
  return (
    <label htmlFor={htmlFor} className="text-[12.5px] text-tx2 mb-1 block">
      {children}
    </label>
  )
}
