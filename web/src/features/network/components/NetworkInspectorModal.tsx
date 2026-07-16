import type { ReactNode } from 'react'
import { X } from 'lucide-react'

export const networkInspectorInput = 'mt-1.5 w-full rounded-xl border border-border bg-background/50 px-3 py-2.5 text-xs text-white outline-none focus:border-primary/40 disabled:cursor-not-allowed disabled:opacity-50'
export const networkInspectorAction = 'shrink-0 rounded-lg border border-border bg-background/45 px-2.5 py-1.5 text-[9px] font-medium text-muted hover:border-primary/30 hover:text-white disabled:cursor-not-allowed disabled:opacity-45'

export function NetworkInspectorModal({ title, description, children, footer, onClose }: {
  title: string
  description?: string
  children: ReactNode
  footer: ReactNode
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl">
        <header className="flex items-start gap-3 border-b border-border px-4 py-3.5">
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-semibold text-white">{title}</h3>
            {description ? <p className="mt-1 text-[10px] leading-4 text-muted">{description}</p> : null}
          </div>
          <button type="button" onClick={onClose} className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted hover:text-white" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="p-4">{children}</div>
        <footer className="flex justify-end gap-2 border-t border-border px-4 py-3">{footer}</footer>
      </div>
    </div>
  )
}
