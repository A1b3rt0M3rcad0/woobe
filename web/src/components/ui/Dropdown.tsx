import { useState, useRef, useEffect, forwardRef, useImperativeHandle, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { ScrollArea } from './ScrollArea'

export interface DropdownHandle {
  close: () => void
}

interface DropdownProps {
  trigger: ReactNode
  children: ReactNode
  align?: 'start' | 'end'
  className?: string
}

export const Dropdown = forwardRef<DropdownHandle, DropdownProps>(
  ({ trigger, children, align = 'end', className }, ref) => {
    const [open, setOpen] = useState(false)
    const containerRef = useRef<HTMLDivElement>(null)

    useImperativeHandle(ref, () => ({
      close: () => setOpen(false),
    }))

    useEffect(() => {
      if (!open) return
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') setOpen(false)
      }
      document.addEventListener('keydown', handleKeyDown)
      return () => document.removeEventListener('keydown', handleKeyDown)
    }, [open])

    useEffect(() => {
      const el = containerRef.current
      if (!el || !open) return
      const handleClickOutside = (e: MouseEvent) => {
        if (!el.contains(e.target as Node)) setOpen(false)
      }
      requestAnimationFrame(() => document.addEventListener('mousedown', handleClickOutside))
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [open])

    return (
      <div ref={containerRef} className={cn('relative', className)}>
        <div onClick={() => setOpen((prev) => !prev)}>
          {trigger}
        </div>
        {open && (
          <div
            className={cn(
              'absolute z-50 mt-1 min-w-[200px] rounded-lg border border-border bg-surface shadow-xl',
              align === 'end' ? 'right-0' : 'left-0',
            )}
          >
            <ScrollArea className="max-h-[280px]">
              {children}
            </ScrollArea>
          </div>
        )}
      </div>
    )
  },
)

Dropdown.displayName = 'Dropdown'
