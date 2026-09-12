import { useEffect, useRef, type ReactNode } from 'react'
import { cn } from '../lib/cn'
import { Button } from './Button'
import { ScrollArea } from './ScrollArea'

export interface DrawerProps {
  open: boolean
  onClose: () => void
  children: ReactNode
  title?: string
  className?: string
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className="h-icon w-icon" fill="none">
      <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

export function Drawer({ open, onClose, children, title, className }: DrawerProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }

    if (open) {
      document.addEventListener('keydown', handleEscape)
      document.body.style.overflow = 'hidden'
    }

    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-modal flex bg-background/80 backdrop-blur-sm"
      onClick={(event) => { if (event.target === overlayRef.current) onClose() }}
    >
      <div className="flex-1" />
      <div
        className={cn(
          'flex w-full max-w-dialog-compact flex-col overflow-hidden rounded-l-container border-l border-border bg-surface shadow-overlay',
          'animate-in slide-in-from-right',
          className,
        )}
      >
        <div className="flex h-dialog-header shrink-0 items-center justify-between border-b border-border px-ui-xl">
          {title ? <h2 className="font-mono text-system-heading font-bold text-slate-50">{title}</h2> : <span />}
          <Button type="button" variant="ghost" size="iconSm" onClick={onClose} className="ml-auto text-muted-foreground" aria-label="Close drawer">
            <CloseIcon />
          </Button>
        </div>
        <ScrollArea className="min-h-0 flex-1 p-ui-xl">
          {children}
        </ScrollArea>
      </div>
    </div>
  )
}
