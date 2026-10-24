/** 浮层体系（hifi §2.5）：scrim + drawer（500px 右抽屉）/ modal（居中弹窗）。
 *  Esc 与 scrim 点击关闭；aria-modal 标注；z-index 40/41 与原型一致。 */
import { useEffect, type JSX, type ReactNode } from 'react'

function useEscape(onClose: () => void): void {
  useEffect(() => {
    const h = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])
}

function Scrim({ onClose }: { onClose: () => void }): JSX.Element {
  return <div className="scrim" onClick={onClose} aria-hidden="true" />
}

interface DrawerProps {
  open: boolean
  onClose: () => void
  label: string
  header: ReactNode
  tabs?: ReactNode
  children: ReactNode
  footer?: ReactNode
}

/** 右侧抽屉：头部标题区 + 可选 tabs + 滚动体 + 底部操作条 */
export function Drawer({
  open,
  onClose,
  label,
  header,
  tabs,
  children,
  footer,
}: DrawerProps): JSX.Element | null {
  useEscape(onClose)
  if (!open) return null
  return (
    <>
      <Scrim onClose={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={label}>
        <div className="flex items-start justify-between p-4 border-b border-border">{header}</div>
        {tabs}
        <div className="flex-1 overflow-y-auto">{children}</div>
        {footer !== undefined && (
          <div className="flex items-center gap-2 p-3 border-t border-border">{footer}</div>
        )}
      </aside>
    </>
  )
}

interface ModalProps {
  open: boolean
  onClose: () => void
  label: string
  title: ReactNode
  children: ReactNode
  footer?: ReactNode
  width?: number
}

export function Modal({
  open,
  onClose,
  label,
  title,
  children,
  footer,
  width,
}: ModalProps): JSX.Element | null {
  useEscape(onClose)
  if (!open) return null
  return (
    <>
      <Scrim onClose={onClose} />
      <div className="modal-wrap">
        <div
          className="modal"
          role="dialog"
          aria-modal="true"
          aria-label={label}
          style={width ? { width: `min(${width}px, 94%)` } : undefined}
        >
          <div className="modal-h">
            {title}
            <button className="ibtn" aria-label="关闭" onClick={onClose}>
              <svg
                className="ic"
                viewBox="0 0 24 24"
                width="16"
                height="16"
                stroke="currentColor"
                fill="none"
                strokeWidth={1.8}
                strokeLinecap="round"
              >
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="modal-b">{children}</div>
          {footer !== undefined && <div className="modal-f">{footer}</div>}
        </div>
      </div>
    </>
  )
}
