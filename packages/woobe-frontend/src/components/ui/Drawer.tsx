import { type ReactNode, useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { X } from 'lucide-react'

interface DrawerProps {
  open: boolean
  onClose: () => void
  children: ReactNode
  title?: string
  className?: string
}

export function Drawer({ open, onClose, children, title, className }: DrawerProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    if (open) {
      document.addEventListener('keydown', handleEsc)
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.removeEventListener('keydown', handleEsc)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div className="flex-1" />
      <div
        className={cn(
          'w-full max-w-lg rounded-l-xl border-l border-border bg-surface shadow-2xl',
          'flex flex-col overflow-hidden',
          'animate-in slide-in-from-right',
          className,
        )}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4 shrink-0">
          {title && <h2 className="text-lg font-semibold">{title}</h2>}
          <button
            onClick={onClose}
            className="ml-auto rounded-lg p-1 hover:bg-accent transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <ScrollArea className="flex-1 p-6">
          {children}
        </ScrollArea>
      </div>
    </div>
  )
}
