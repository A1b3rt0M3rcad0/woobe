import { forwardRef, useEffect, useImperativeHandle, useRef, useState, type ReactNode } from 'react'
import { cn } from '../lib/cn'
import { woobeLayout } from '../tokens'
import { ScrollArea } from './ScrollArea'

export interface DropdownHandle {
  close: () => void
}

export interface DropdownProps {
  trigger: ReactNode
  children: ReactNode
  align?: 'start' | 'end'
  className?: string
}

const Dropdown = forwardRef<DropdownHandle, DropdownProps>(
  ({ trigger, children, align = 'end', className }, ref) => {
    const [open, setOpen] = useState(false)
    const containerRef = useRef<HTMLDivElement>(null)

    useImperativeHandle(ref, () => ({ close: () => setOpen(false) }))

    useEffect(() => {
      if (!open) return
      const handleKeyDown = (event: KeyboardEvent) => {
        if (event.key === 'Escape') setOpen(false)
      }
      document.addEventListener('keydown', handleKeyDown)
      return () => document.removeEventListener('keydown', handleKeyDown)
    }, [open])

    useEffect(() => {
      const element = containerRef.current
      if (!element || !open) return
      const handleClickOutside = (event: MouseEvent) => {
        if (!element.contains(event.target as Node)) setOpen(false)
      }
      requestAnimationFrame(() => document.addEventListener('mousedown', handleClickOutside))
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [open])

    return (
      <div ref={containerRef} className={cn('relative', className)}>
        <div onClick={() => setOpen((current) => !current)}>{trigger}</div>
        {open ? (
          <div
            className={cn(
              'absolute z-popover mt-ui-xs min-w-popover overflow-hidden rounded-container border border-border bg-surface shadow-popup',
              align === 'end' ? 'right-0' : 'left-0',
            )}
          >
            <ScrollArea style={{ maxHeight: woobeLayout.popoverMaxHeight }}>
              {children}
            </ScrollArea>
          </div>
        ) : null}
      </div>
    )
  },
)

Dropdown.displayName = 'Dropdown'

export { Dropdown }
