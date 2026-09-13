import { createContext, type ReactNode, useContext, useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../lib/cn'
import { focusableElements, isTopOverlay, registerOverlay, unregisterOverlay } from '../lib/overlay-focus'
import { Button } from './Button'
import '../styles/dialog-compatibility.css'

export type DialogPresentation = 'modal' | 'embedded'
export type DialogScrollMode = 'overlay' | 'content'
export type DialogLayer = 'modal' | 'nestedModal'

const DialogPresentationContext = createContext<DialogPresentation>('modal')

export interface DialogPresentationProviderProps {
  presentation: DialogPresentation
  children: ReactNode
}

export function DialogPresentationProvider({ presentation, children }: DialogPresentationProviderProps) {
  return <DialogPresentationContext.Provider value={presentation}>{children}</DialogPresentationContext.Provider>
}

export interface DialogProps {
  open: boolean
  onClose: () => void
  title?: ReactNode
  children: ReactNode
  className?: string
  contentClassName?: string
  layer?: DialogLayer
  scrollMode?: DialogScrollMode
}

const LAYER_CLASS: Record<DialogLayer, string> = { modal: 'z-modal', nestedModal: 'z-nested-modal' }

export const dialogTypographyClass = [
  'font-sans',
  '[&_h1]:text-heading-sm [&_h2]:text-section-title [&_h3]:text-section-title [&_h4]:text-system-control',
  '[&_label]:font-mono [&_legend]:font-mono [&_button]:font-mono [&_input]:font-mono [&_input]:text-system-control [&_select]:font-mono',
  '[&_select]:h-control [&_select]:rounded-control [&_select]:border-border [&_select]:bg-control [&_select]:text-system-control [&_select]:text-accent-foreground',
  '[&_th]:font-mono [&_dt]:font-mono [&_code]:font-mono [&_pre]:font-mono',
  '[&_.uppercase]:font-mono [&_.tabular-nums]:font-mono [&_aside]:font-mono',
  '[&_.text-lg]:text-heading-sm [&_.text-base]:text-product-body [&_.text-sm]:text-product-small [&_.text-xs]:text-product-caption',
].join(' ')

export function Dialog({ open, onClose, title, children, className, contentClassName, layer = 'modal', scrollMode = 'overlay' }: DialogProps) {
  const presentation = useContext(DialogPresentationContext)
  const overlayRef = useRef<HTMLDivElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
  const previouslyFocusedRef = useRef<HTMLElement | null>(null)
  const titleId = useId()
  const overlayId = useId()
  const contentScroll = scrollMode === 'content'

  useEffect(() => {
    if (!open || presentation !== 'modal') return

    previouslyFocusedRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    registerOverlay(overlayId)

    const focusFrame = window.requestAnimationFrame(() => {
      if (!isTopOverlay(overlayId)) return
      const root = dialogRef.current
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
      const root = dialogRef.current
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
  }, [onClose, open, overlayId, presentation])

  if (!open) return null

  const dialogContent = (
    <div
      ref={dialogRef}
      role={presentation === 'modal' ? 'dialog' : undefined}
      aria-modal={presentation === 'modal' ? true : undefined}
      aria-labelledby={presentation === 'modal' && title ? titleId : undefined}
      tabIndex={presentation === 'modal' ? -1 : undefined}
      className={cn(
        'dialog-scrollbars relative w-full max-w-dialog-compact rounded-container border border-border bg-surface text-accent-foreground shadow-popup',
        dialogTypographyClass,
        '[&_.rounded-2xl]:rounded-container [&_.rounded-xl]:rounded-container [&_.rounded-lg]:rounded-control [&_.rounded-md]:rounded-technical',
        '[&_.shadow-sm]:shadow-none [&_.shadow-lg]:shadow-none [&_.shadow-xl]:shadow-none [&_.shadow-2xl]:shadow-none',
        contentScroll && 'flex max-h-dialog flex-col overflow-hidden',
        className,
      )}
    >
      <div className="flex h-panel-header shrink-0 items-center justify-between border-b border-border px-ui-panel-inset">
        {title ? (
          <h2 id={presentation === 'modal' ? titleId : undefined} className="min-w-0 truncate font-mono text-section-title font-bold text-accent-foreground">
            {title}
          </h2>
        ) : <span />}
        <Button type="button" variant="ghost" size="iconSm" onClick={onClose} className="ml-auto shrink-0 text-muted-foreground" aria-label="Close dialog">
          <svg viewBox="0 0 16 16" aria-hidden="true" className="h-icon w-icon" fill="none">
            <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
        </Button>
      </div>
      <div className={cn('p-ui-panel-inset', contentClassName, contentScroll && 'scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain')}>{children}</div>
    </div>
  )

  if (presentation === 'embedded') return dialogContent

  return createPortal(
    <div
      ref={overlayRef}
      className={cn(
        'fixed inset-0 flex min-h-svh w-screen items-center justify-center bg-background/80 p-ui-content-gutter backdrop-blur-sm',
        contentScroll ? 'overflow-hidden' : 'overflow-y-auto',
        LAYER_CLASS[layer],
      )}
      onClick={(event) => {
        if (event.target === overlayRef.current && isTopOverlay(overlayId)) onClose()
      }}
    >
      {dialogContent}
    </div>,
    document.body,
  )
}