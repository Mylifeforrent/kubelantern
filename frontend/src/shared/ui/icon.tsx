/**
 * 内联 SVG 图标（视觉唯一事实源 = 可点击原型 §1.6 的 27 个 symbol，
 * viewBox 0 0 24 24 / stroke currentColor / fill none / stroke-width 1.8 / round cap+join）。
 */
import type { JSX, SVGProps } from 'react'

export type IconName =
  | 'eye2'
  | 'siren'
  | 'layers'
  | 'zap'
  | 'cal'
  | 'radar'
  | 'spark'
  | 'branch'
  | 'gear'
  | 'search'
  | 'bell'
  | 'x'
  | 'check'
  | 'warn'
  | 'shield'
  | 'clock'
  | 'chl'
  | 'chr'
  | 'arr'
  | 'file'
  | 'term'
  | 'inbox'
  | 'filter'
  | 'plus'
  | 'user'
  | 'link'
  | 'refresh'

const PATHS: Record<IconName, JSX.Element> = {
  eye2: (
    <>
      <path d="M12 12h.01" />
      <path d="M9 3.5c4.6-.9 9.2 1.6 10.7 6a10.6 10.6 0 0 1-2.3 3.7M6.6 5.4A10 10 0 0 0 1.3 9.5c1.5 4.4 6.1 6.9 10.7 6a10 10 0 0 0 1.6-.4" />
      <circle cx="12" cy="10" r="2.6" />
    </>
  ),
  siren: (
    <>
      <path d="M6 8.5a6 6 0 0 1 12 0c0 6.3 2.5 7.5 2.5 7.5h-17S6 14.8 6 8.5" />
      <path d="M10 20a2.2 2.2 0 0 0 4 0" />
    </>
  ),
  layers: (
    <>
      <path d="M12 2 2 7.5l10 5 10-5L12 2z" />
      <path d="m2 12.5 10 5 10-5" />
      <path d="m2 17.5 10 5 10-5" />
    </>
  ),
  zap: <path d="M13 2 3 14h7l-1 8 12-14h-8l0-6z" />,
  cal: (
    <>
      <rect x="3" y="4" width="18" height="17" rx="2" />
      <path d="M16 2v4M8 2v4M3 9.5h18" />
    </>
  ),
  radar: (
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="4.5" />
      <path d="M12 12l6.4-6.4" />
    </>
  ),
  spark: (
    <>
      <path d="M12 3l1.9 5.2L19 10l-5.1 1.8L12 17l-1.9-5.2L5 10l5.1-1.8L12 3z" />
      <path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15z" />
    </>
  ),
  branch: (
    <>
      <circle cx="6" cy="5" r="2.4" />
      <circle cx="6" cy="19" r="2.4" />
      <circle cx="18" cy="7" r="2.4" />
      <path d="M6 7.4v9.2" />
      <path d="M18 9.4a9 9 0 0 1-9 7.3" />
    </>
  ),
  gear: (
    <>
      <path d="M4 21v-6M4 9V3M12 21v-9M12 6V3M20 21v-4M20 11V3" />
      <path d="M1.5 15h5M9.5 6h5M17.5 17h5" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </>
  ),
  bell: (
    <>
      <path d="M6 8.5a6 6 0 0 1 12 0c0 6.3 2.5 7.5 2.5 7.5h-17S6 14.8 6 8.5" />
      <path d="M10 20a2.2 2.2 0 0 0 4 0" />
    </>
  ),
  x: <path d="M18 6 6 18M6 6l12 12" />,
  check: <path d="M20 6 9 17l-5-5" />,
  warn: (
    <>
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
      <path d="M12 9v4.5M12 17.5h.01" />
    </>
  ),
  shield: (
    <>
      <path d="M12 22s8-3.6 8-10V5l-8-3-8 3v7c0 6.4 8 10 8 10z" />
      <path d="m9 11.5 2 2 4-4.5" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.2 1.9" />
    </>
  ),
  chl: <path d="m15 18-6-6 6-6" />,
  chr: <path d="m9 18 6-6-6-6" />,
  arr: <path d="M4 12h15M13 6l6 6-6 6" />,
  file: (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6M9 13h6M9 17h4" />
    </>
  ),
  term: <path d="m4 17 6-6-6-6M12 19h8" />,
  inbox: (
    <>
      <path d="M22 12h-5.5l-2 3h-5l-2-3H2" />
      <path d="M5.5 5h13L22 12v5a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-5z" />
    </>
  ),
  filter: <path d="M22 3.5H2l8 9.5v6.5l4 2v-8.5z" />,
  plus: <path d="M12 5v14M5 12h14" />,
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4.5 21a7.5 7.5 0 0 1 15 0" />
    </>
  ),
  link: (
    <>
      <path d="M10 13a5 5 0 0 0 7.5.5l2.5-2.5a5 5 0 0 0-7-7L11.5 5.5" />
      <path d="M14 11a5 5 0 0 0-7.5-.5L4 13a5 5 0 0 0 7 7l1.5-1.5" />
    </>
  ),
  refresh: (
    <>
      <path d="M21 12a9 9 0 1 1-2.6-6.3L21 8" />
      <path d="M21 3v5h-5" />
    </>
  ),
}

interface IconProps extends SVGProps<SVGSVGElement> {
  name: IconName
  size?: number
}

export function Icon({ name, size = 16, className, ...rest }: IconProps): JSX.Element {
  return (
    <svg
      className={`ic ${className ?? ''}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      stroke="currentColor"
      fill="none"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {PATHS[name]}
    </svg>
  )
}
