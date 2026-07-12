import { createContext, type ReactNode, useContext, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'
import { UI_LAYER_CLASS, type DialogLayer } from '@/lib/ui-layers'
import { X } from 'lucide-react'

type DialogPresentation = 'modal' | 'embedded'

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
  layer?: DialogLayer
}

export function Dialog({
  open,
  onClose,
  children,
  title,
  className,
  layer = 'modal',
}: DialogProps) {
  const presentation = useContext(DialogPresentationContext)
  const overlayRef = useRef<HTMLDivElement>(null)

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
      className={cn(
        'relative w-full max-w-lg rounded-xl border border-border bg-surface shadow-2xl',
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        {title && <h2 className="text-lg font-semibold">{title}</h2>}
        <button
          type="button"
          onClick={onClose}
          className="ml-auto rounded-lg p-1 transition-colors hover:bg-accent"
          aria-label="Close dialog"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="p-6">{children}</div>
    </div>
  )

  if (presentation === 'embedded') {
    return dialogContent
  }

  return createPortal(
    <div
      ref={overlayRef}
      className={cn(
        'fixed inset-0 flex min-h-svh w-screen items-center justify-center overflow-y-auto bg-black/70 p-4 backdrop-blur-md',
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
