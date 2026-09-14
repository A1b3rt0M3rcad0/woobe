import { createContext, type HTMLAttributes, type ReactNode, useContext, useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../lib/cn'
import { focusableElements, isTopOverlay, registerOverlay, unregisterOverlay } from '../lib/overlay-focus'
import { Button } from './Button'
import '../styles/dialog-compatibility.css'

export type DialogPresentation = 'modal' | 'embedded'
export type DialogScrollMode = 'overlay' | 'content'
export type DialogLayer = 'modal' | 'nestedModal'
export type DialogVariant = 'standard' | 'workspace'
export type DialogBodyTone = 'default' | 'subtle'

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
  variant?: DialogVariant
  height?: 'content' | 'workspace'
}

export interface DialogContextBarProps extends HTMLAttributes<HTMLDivElement> {}

export function DialogContextBar({ className, ...props }: DialogContextBarProps) {
  return <div className={cn('shrink-0 border-b border-border bg-background/20 px-ui-panel-inset py-ui-md', className)} {...props} />
}

export interface DialogBodyProps extends HTMLAttributes<HTMLDivElement> {
  padded?: boolean
  tone?: DialogBodyTone
  spacing?: 'panel' | 'workspace'
}

export function DialogBody({ className, padded = true, tone = 'default', spacing = 'panel', ...props }: DialogBodyProps) {
  return (
    <div
      className={cn(
        'scrollbar-thin min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain',
        padded && (spacing === 'workspace' ? 'woobe-dialog-body-workspace p-ui-lg sm:p-ui-xl lg:p-ui-xxl' : 'p-ui-panel-inset'),
        tone === 'subtle' && 'bg-surface/25',
        className,
      )}
      {...props}
    />
  )
}

export interface DialogFooterProps extends Omit<HTMLAttributes<HTMLDivElement>, 'children'> {
  meta?: ReactNode
  actions: ReactNode
}

export function DialogFooter({ className, meta, actions, ...props }: DialogFooterProps) {
  return (
    <div
      className={cn(
        'flex shrink-0 flex-col-reverse gap-ui-sm border-t border-border bg-surface/95 px-ui-lg py-ui-md backdrop-blur lg:px-ui-xxl sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
      {...props}
    >
      <div className="min-w-0 flex-1">{meta}</div>
      <div className="flex shrink-0 flex-wrap justify-end gap-ui-sm">{actions}</div>
    </div>
  )
}

const LAYER_CLASS: Record<DialogLayer, string> = { modal: 'z-modal', nestedModal: 'z-nested-modal' }

export const dialogTypographyClass = [
  'font-sans',
  '[&_h1]:text-heading-sm [&_h2]:text-section-title [&_h3]:text-section-title [&_h4]:text-system-control',
  '[&_label]:font-mono [&_legend]:font-mono [&_button]:font-mono',
  '[&_input]:font-sans [&_input]:text-system-control',
  '[&_select]:font-mono [&_select]:h-control [&_select]:rounded-control [&_select]:border-border [&_select]:bg-control [&_select]:text-system-control [&_select]:font-normal [&_select]:text-accent-foreground',
  '[&_option]:font-mono [&_option]:text-system-control',
  '[&_textarea]:font-sans [&_textarea]:text-system-control',
  '[&_th]:font-mono [&_dt]:font-mono [&_code]:font-mono [&_pre]:font-mono',
  '[&_.uppercase]:font-mono [&_.tabular-nums]:font-mono [&_aside]:font-mono',
  '[&_.text-lg]:text-heading-sm [&_.text-base]:text-product-body [&_.text-sm]:text-product-small [&_.text-xs]:text-product-caption',
].join(' ')

export function Dialog({ open, onClose, title, children, className, contentClassName, layer = 'modal', scrollMode = 'overlay', variant = 'standard', height = 'content' }: DialogProps) {
  const presentation = useContext(DialogPresentationContext)
  const overlayRef = useRef<HTMLDivElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
  const previouslyFocusedRef = useRef<HTMLElement | null>(null)
  const titleId = useId()
  const overlayId = useId()
  const contentScroll = scrollMode === 'content'
  const workspace = variant === 'workspace'

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
      data-dialog-variant={variant}
      className={cn(
        'dialog-scrollbars relative w-full max-w-dialog-compact rounded-container border border-border bg-surface text-accent-foreground shadow-popup',
        workspace && 'flex max-h-dialog max-w-dialog-wide flex-col overflow-hidden',
        workspace && height === 'workspace' && 'h-dialog-workspace',
        dialogTypographyClass,
        '[&_.rounded-2xl]:rounded-container [&_.rounded-xl]:rounded-container [&_.rounded-lg]:rounded-control [&_.rounded-md]:rounded-technical',
        '[&_.shadow-sm]:shadow-none [&_.shadow-lg]:shadow-none [&_.shadow-xl]:shadow-none [&_.shadow-2xl]:shadow-none',
        contentScroll && 'flex max-h-dialog flex-col overflow-hidden',
        className,
      )}
    >
      <div className="flex h-panel-header shrink-0 items-center justify-between border-b border-border bg-control/20 px-ui-panel-inset">
        {title ? (
          <h2 id={presentation === 'modal' ? titleId : undefined} className="min-w-0 truncate font-sans text-entity-title font-semibold text-accent-foreground">
            {title}
          </h2>
        ) : <span />}
        <Button type="button" variant="ghost" size="iconSm" onClick={onClose} className="ml-auto shrink-0 text-muted-foreground" aria-label="Close dialog">
          <svg viewBox="0 0 16 16" aria-hidden="true" className="h-icon w-icon" fill="none">
            <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
        </Button>
      </div>
      <div
        className={cn(
          workspace ? 'min-h-0 flex-1 p-0' : 'p-ui-panel-inset',
          workspace && height === 'workspace' && 'flex flex-col overflow-hidden',
          contentClassName,
          contentScroll && 'scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain',
        )}
      >
        {children}
      </div>
    </div>
  )

  if (presentation === 'embedded') return dialogContent

  return createPortal(
    <div
      ref={overlayRef}
      className={cn(
        'fixed inset-0 flex min-h-svh w-screen items-center justify-center bg-background/80 backdrop-blur-sm',
        workspace && height === 'workspace' ? 'p-ui-lg' : 'p-ui-content-gutter',
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
