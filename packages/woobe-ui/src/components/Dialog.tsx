import { createContext, type ReactNode, useContext, useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../lib/cn'
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
  '[&_h1]:font-mono [&_h2]:font-mono [&_h3]:font-mono [&_h4]:font-mono [&_h5]:font-mono [&_h6]:font-mono',
  '[&_label]:font-mono [&_legend]:font-mono [&_button]:font-mono [&_input]:font-mono [&_input]:text-system-control [&_select]:font-mono',
  '[&_select]:h-control [&_select]:rounded-control [&_select]:border-border [&_select]:bg-control [&_select]:text-system-control [&_select]:text-accent-foreground',
  '[&_th]:font-mono [&_dt]:font-mono [&_code]:font-mono [&_pre]:font-mono',
  '[&_.uppercase]:font-mono [&_.tabular-nums]:font-mono [&_aside]:font-mono',
].join(' ')

export function Dialog({ open, onClose, title, children, className, contentClassName, layer = 'modal', scrollMode = 'overlay' }: DialogProps) {
  const presentation = useContext(DialogPresentationContext)
  const overlayRef = useRef<HTMLDivElement>(null)
  const titleId = useId()
  const contentScroll = scrollMode === 'content'

  useEffect(() => {
    if (!open || presentation !== 'modal') return
    const previousOverflow = document.body.style.overflow
    const handleEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleEscape)
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', handleEscape); document.body.style.overflow = previousOverflow }
  }, [open, onClose, presentation])

  if (!open) return null

  const dialogContent = (
    <div
      role={presentation === 'modal' ? 'dialog' : undefined}
      aria-modal={presentation === 'modal' ? true : undefined}
      aria-labelledby={presentation === 'modal' && title ? titleId : undefined}
      className={cn(
        'dialog-scrollbars relative w-full max-w-dialog-compact rounded-container border border-border bg-surface text-accent-foreground shadow-overlay',
        dialogTypographyClass,
        '[&_.rounded-2xl]:rounded-container [&_.rounded-xl]:rounded-container [&_.rounded-lg]:rounded-control [&_.rounded-md]:rounded-technical',
        '[&_.shadow-sm]:shadow-none [&_.shadow-lg]:shadow-none [&_.shadow-xl]:shadow-none [&_.shadow-2xl]:shadow-none',
        contentScroll && 'flex max-h-dialog flex-col overflow-hidden',
        className,
      )}
    >
      <div className="flex h-dialog-header shrink-0 items-center justify-between border-b border-border px-ui-xl">
        {title ? <h2 id={presentation === 'modal' ? titleId : undefined} className="min-w-0 truncate font-mono text-system-heading font-bold text-accent-foreground">{title}</h2> : <span />}
        <Button type="button" variant="ghost" size="iconSm" onClick={onClose} className="ml-auto shrink-0 text-muted-foreground" aria-label="Close dialog">
          <svg viewBox="0 0 16 16" aria-hidden="true" className="h-icon w-icon" fill="none"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg>
        </Button>
      </div>
      <div className={cn('p-ui-xl', contentClassName, contentScroll && 'scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain')}>{children}</div>
    </div>
  )

  if (presentation === 'embedded') return dialogContent

  return createPortal(
    <div ref={overlayRef} className={cn('fixed inset-0 flex min-h-svh w-screen items-center justify-center bg-background/80 p-ui-lg backdrop-blur-sm', contentScroll ? 'overflow-hidden' : 'overflow-y-auto', LAYER_CLASS[layer])} onClick={(event) => { if (event.target === overlayRef.current) onClose() }}>
      {dialogContent}
    </div>,
    document.body,
  )
}
