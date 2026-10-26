/** KubeLantern 品牌标记（视觉唯一事实源：docs/assets/brand/kubelanter-logo.svg）。
 *  灯笼轮廓 + Kubernetes 轮辐光核；30px 下保留可辨识轮廓，不依赖 emoji 或位图。 */
import { useId, type JSX, type SVGProps } from 'react'

interface BrandLogoProps extends Omit<SVGProps<SVGSVGElement>, 'children'> {
  size?: number
  title?: string
}

export function BrandLogo({ size = 30, title, ...rest }: BrandLogoProps): JSX.Element {
  const uid = useId().replace(/:/g, '')
  const tile = `kl-tile-${uid}`
  const glow = `kl-glow-${uid}`

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      {...rest}
    >
      <defs>
        <linearGradient id={tile} x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#F0643C" />
          <stop offset="0.52" stopColor="#C53520" />
          <stop offset="1" stopColor="#8B1B0F" />
        </linearGradient>
        <radialGradient id={glow} cx="32" cy="34" r="23" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#FFE8A3" stopOpacity="0.9" />
          <stop offset="0.5" stopColor="#F2CC60" stopOpacity="0.3" />
          <stop offset="1" stopColor="#F2CC60" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="64" height="64" rx="15" fill={`url(#${tile})`} />
      <circle cx="32" cy="34" r="23" fill={`url(#${glow})`} />
      <path d="M25.5 14.5h13" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" />
      <path
        d="M27.8 14.5v-1.6a4.2 4.2 0 0 1 8.4 0v1.6"
        fill="none"
        stroke="#fff"
        strokeWidth="2.6"
        strokeLinecap="round"
      />
      <path d="M22.3 17.8h19.4l-2.1 4.8H24.4z" fill="#fff" />
      <path
        d="M24.4 22.6h15.2l-1.7 20.7a4.7 4.7 0 0 1-4.7 4.2h-2.4a4.7 4.7 0 0 1-4.7-4.2z"
        fill="#fff"
      />
      <path
        d="M27.7 26.2h8.6l-.9 15.1a2.35 2.35 0 0 1-2.35 2.2h-2.1a2.35 2.35 0 0 1-2.35-2.2z"
        fill="#8B1B0F"
      />
      <g stroke="#F2CC60" strokeWidth="1.6" strokeLinecap="round">
        <circle cx="32" cy="35" r="4.8" fill="none" />
        <circle cx="32" cy="35" r="1.35" fill="#F2CC60" stroke="none" />
        <path d="M32 30.2v2.6M32 37.2v2.6M27.2 35h2.6M34.2 35h2.6M28.6 31.6l1.85 1.85M33.55 36.55l1.85 1.85M35.4 31.6l-1.85 1.85M30.45 36.55l-1.85 1.85" />
      </g>
      <path d="M26.2 51.4h11.6" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  )
}
