/** 按钮族（hifi §4.2：btn / btn-p 主 / btn-ai AI / btn-d 危险 / btn-sm / ibtn / iconbtn）。
 *  层级规则：每屏主操作唯一 btn-p；AI 能力一律 btn-ai；终止/拒绝类 btn-d。 */
import type { ButtonHTMLAttributes, JSX } from 'react'
import { cn } from '../lib/cn'

type Variant = 'default' | 'primary' | 'ai' | 'danger'

const VARIANT: Record<Variant, string> = {
  default: '',
  primary: 'btn-p',
  ai: 'btn-ai',
  danger: 'btn-d',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  small?: boolean
}

export function Button({
  variant = 'default',
  small,
  className,
  type,
  ...rest
}: ButtonProps): JSX.Element {
  return (
    <button
      type={type ?? 'button'}
      className={cn('btn', VARIANT[variant], small && 'btn-sm', className)}
      {...rest}
    />
  )
}

/** 行内图标钮（26px 方，表格行操作用） */
export function Ibtn({
  className,
  type,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement>): JSX.Element {
  return <button type={type ?? 'button'} className={cn('ibtn', className)} {...rest} />
}

/** 顶栏图标钮（32px 方，可含 pip 角标） */
export function IconBtn({
  pip,
  className,
  type,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { pip?: number }): JSX.Element {
  return (
    <button type={type ?? 'button'} className={cn('iconbtn', className)} {...rest}>
      {children}
      {pip !== undefined && pip > 0 && <span className="pip num">{pip > 9 ? '9+' : pip}</span>}
    </button>
  )
}
