import { createPortal } from 'react-dom'
import { useEffect, useId, useRef, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface DialogProps {
  open: boolean
  onClose: () => void
  title?: ReactNode
  children: ReactNode
  className?: string
  contentClassName?: string
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className="h-3.5 w-3.5" fill="none">
      <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

const DIALOG_TYPOGRAPHY = [
  'font-sans',
  '[&_h1]:font-mono [&_h2]:font-mono [&_h3]:font-mono [&_h4]:font-mono [&_h5]:font-mono [&_h6]:font-mono',
  '[&_label]:font-mono [&_legend]:font-mono [&_button]:font-mono [&_input]:font-mono [&_select]:font-mono',
  '[&_th]:font-mono [&_dt]:font-mono [&_code]:font-mono [&_pre]:font-mono',
  '[&_.uppercase]:font-mono [&_.tabular-nums]:font-mono [&_aside]:font-mono',
  '[&_textarea]:font-sans',
].join(' ')

export function Dialog({ open, onClose, title, children, className, contentClassName }: DialogProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const titleId = useId()

  useEffect(() => {
    if (!open) return

    const previousOverflow = document.body.style.overflow
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }

    document.addEventListener('keydown', handleEscape)
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = previousOverflow
    }
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div
      ref={overlayRef}
      className="fixed inset-0 z-[100] flex min-h-svh w-screen items-center justify-center overflow-y-auto bg-background/80 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === overlayRef.current) onClose()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        className={cn(
          'w-full max-w-lg rounded-container border border-border bg-surface text-accent-foreground shadow-[0_12px_40px_rgba(0,0,0,0.24)]',
          DIALOG_TYPOGRAPHY,
          className,
        )}
      >
        <div className="flex h-[52px] items-center justify-between border-b border-border px-5">
          {title ? (
            <h2 id={titleId} className="font-mono text-xs font-bold tracking-[0.015em] text-slate-50">
              {title}
            </h2>
          ) : <span />}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="flex h-7 w-7 items-center justify-center rounded-technical border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
          >
            <CloseIcon />
          </button>
        </div>
        <div className={cn('p-5', contentClassName)}>{children}</div>
      </div>
    </div>,
    document.body,
  )
}
