/** Toast（hifi §2.6）：右下角纵列、3px 语义色边条、可选动作链接、aria-live=polite。
 *  时序：入场 → 停留 4200ms → 淡出移除。 */
import { create } from 'zustand'
import type { JSX } from 'react'
import { Icon } from './icon'

export type ToastVariant = 'info' | 'ok' | 'err' | 'ai' | 'warn'

export interface ToastItem {
  id: number
  title: string
  description?: string
  variant: ToastVariant
  action?: { label: string; onClick: () => void }
}

interface ToastState {
  items: ToastItem[]
  show: (t: Omit<ToastItem, 'id'>) => void
  dismiss: (id: number) => void
}

let seq = 0

export const useToastStore = create<ToastState>()((set, get) => ({
  items: [],
  show: (t) => {
    const id = ++seq
    set((s) => ({ items: [...s.items, { ...t, id }] }))
    window.setTimeout(() => get().dismiss(id), 4200)
  },
  dismiss: (id) => set((s) => ({ items: s.items.filter((x) => x.id !== id) })),
}))

export const toast = {
  show: (t: Omit<ToastItem, 'id'>): void => useToastStore.getState().show(t),
}

export function Toaster(): JSX.Element {
  const items = useToastStore((s) => s.items)
  const dismiss = useToastStore((s) => s.dismiss)
  return (
    <div className="toasts" aria-live="polite">
      {items.map((t) => (
        <div key={t.id} className={`toast ${t.variant}`} role="status">
          <b>{t.title}</b>
          {t.description && <p>{t.description}</p>}
          <div className="flex items-center gap-3">
            {t.action && (
              <button
                className="ta"
                onClick={() => {
                  t.action?.onClick()
                  dismiss(t.id)
                }}
              >
                {t.action.label}
                <Icon name="arr" size={12} />
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
