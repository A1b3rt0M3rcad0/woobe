import { createContext, type ReactNode, useContext, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'
import { UI_LAYER_CLASS, type DialogLayer } from '@/lib/ui-layers'
import { X } from 'lucide-react'
import './dialog-typography.css'

type DialogPresentation = 'modal' | 'embedded'
type DialogScrollMode = 'overlay' | 'content'

const DialogPresentationContext = createContext<DialogPresentation>('modal')

export function DialogPresentationProvider({
  presentation,
  children,
}: {
  presentation: DialogPresentation
  children: ReactNode
}) {
  return (
    <DialogPresentationContext.Provider value={presentation}>
      {children}
    </DialogPresentationContext.Provider>
  )
}

interface DialogProps {
  open: boolean
  onClose: () => void
  children: ReactNode
  title?: string
  className?: string
  contentClassName?: string
  layer?: DialogLayer
  scrollMode?: DialogScrollMode
}

const INTERNAL_SCROLLBAR = 'scrollbar-thin'

export const dialogTypographyClass = [
  'font-sans',
  '[&_h1]:font-mono [&_h2]:font-mono [&_h3]:font-mono [&_h4]:font-mono [&_h5]:font-mono [&_h6]:font-mono',
  '[&_label]:font-mono [&_legend]:font-mono [&_button]:font-mono [&_input]:font-mono [&_select]:font-mono',
  '[&_th]:font-mono [&_dt]:font-mono [&_code]:font-mono [&_pre]:font-mono',
  '[&_.uppercase]:font-mono [&_.tabular-nums]:font-mono [&_aside]:font-mono',
].join(' ')

export function Dialog({
  open,
  onClose,
  children,
  title,
  className,
  contentClassName,
  layer = 'modal',
  scrollMode = 'overlay',
}: DialogProps) {
  const presentation = useContext(DialogPresentationContext)
  const overlayRef = useRef<HTMLDivElement>(null)
  const contentScroll = scrollMode === 'content'

  useEffect(() => {
    if (!open || presentation !== 'modal') return

    const handleEsc = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }

    document.addEventListener('keydown', handleEsc)
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', handleEsc)
      document.body.style.overflow = ''
    }
  }, [open, onClose, presentation])

  if (!open) return null

  const dialogContent = (
    <div
      role={presentation === 'modal' ? 'dialog' : undefined}
      aria-modal={presentation === 'modal' ? true : undefined}
      className={cn(
        'dialog-scrollbars relative w-full max-w-lg rounded-container border border-border bg-surface text-accent-foreground shadow-[0_12px_40px_rgba(0,0,0,0.24)]',
        dialogTypographyClass,
        '[&_.rounded-xl]:rounded-container [&_.rounded-lg]:rounded-control [&_.rounded-md]:rounded-technical',
        '[&_.shadow-sm]:shadow-none [&_.shadow-lg]:shadow-none [&_.shadow-xl]:shadow-none [&_.shadow-2xl]:shadow-none',
        contentScroll && 'flex max-h-[calc(100svh-2rem)] flex-col overflow-hidden',
        className,
      )}
    >
      <div className="flex h-[52px] shrink-0 items-center justify-between border-b border-border px-5">
        {title ? <h2 className="font-mono text-xs font-bold tracking-[0.015em] text-slate-50">{title}</h2> : <span />}
        <button
          type="button"
          onClick={onClose}
          className="ml-auto flex h-7 w-7 items-center justify-center rounded-technical border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
          aria-label="Close dialog"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <div
        className={cn(
          'p-5',
          contentClassName,
          contentScroll && `min-h-0 flex-1 overflow-y-auto overscroll-contain ${INTERNAL_SCROLLBAR}`,
        )}
      >
        {children}
      </div>
    </div>
  )

  if (presentation === 'embedded') {
    return dialogContent
  }

  return createPortal(
    <div
      ref={overlayRef}
      className={cn(
        'fixed inset-0 flex min-h-svh w-screen items-center justify-center bg-background/80 p-4 backdrop-blur-sm',
        contentScroll ? 'overflow-hidden' : 'overflow-y-auto',
        UI_LAYER_CLASS[layer],
      )}
      onClick={(event) => {
        if (event.target === overlayRef.current) onClose()
      }}
    >
      {dialogContent}
    </div>,
    document.body,
  )
}
