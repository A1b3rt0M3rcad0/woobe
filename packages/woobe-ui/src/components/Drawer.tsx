import { useEffect, useId, useRef, type ReactNode } from 'react'
import { cn } from '../lib/cn'
import { focusableElements, isTopOverlay, registerOverlay, unregisterOverlay } from '../lib/overlay-focus'
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
  const drawerRef = useRef<HTMLDivElement>(null)
  const previouslyFocusedRef = useRef<HTMLElement | null>(null)
  const overlayId = useId()
  const titleId = useId()

  useEffect(() => {
    if (!open) return

    previouslyFocusedRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    registerOverlay(overlayId)

    const focusFrame = window.requestAnimationFrame(() => {
      if (!isTopOverlay(overlayId)) return
      const root = drawerRef.current
      if (!root) return
      const [first] = focusableElements(root)
      ;(first ?? root).focus()
    })

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!isTopOverlay(overlayId)) return

      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        onClose()
        return
      }

      if (event.key !== 'Tab') return
      const root = drawerRef.current
      if (!root) return
      const focusable = focusableElements(root)
      if (focusable.length === 0) {
        event.preventDefault()
        root.focus()
        return
      }

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement
      const activeInside = active instanceof Node && root.contains(active)

      if (event.shiftKey && (!activeInside || active === first)) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && (!activeInside || active === last)) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)

    return () => {
      window.cancelAnimationFrame(focusFrame)
      document.removeEventListener('keydown', handleKeyDown)
      unregisterOverlay(overlayId)

      const previouslyFocused = previouslyFocusedRef.current
      if (previouslyFocused?.isConnected) {
        window.requestAnimationFrame(() => {
          if (previouslyFocused.isConnected) previouslyFocused.focus()
        })
      }
    }
  }, [onClose, open, overlayId])

  if (!open) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-modal flex bg-background/80 backdrop-blur-sm"
      onClick={(event) => {
        if (event.target === overlayRef.current && isTopOverlay(overlayId)) onClose()
      }}
    >
      <div className="flex-1" />
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        tabIndex={-1}
        className={cn(
          'flex w-full max-w-dialog-compact flex-col overflow-hidden rounded-l-container border-l border-border bg-surface shadow-overlay',
          'animate-in slide-in-from-right',
          className,
        )}
      >
        <div className="flex h-dialog-header shrink-0 items-center justify-between border-b border-border px-ui-xl">
          {title ? <h2 id={titleId} className="font-mono text-system-heading font-bold text-accent-foreground">{title}</h2> : <span />}
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