import { forwardRef, type HTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export interface ScrollAreaProps extends HTMLAttributes<HTMLDivElement> {
  orientation?: 'vertical' | 'horizontal' | 'both'
}

const ScrollArea = forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ children, className, orientation = 'vertical', ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'scrollbar-thin',
        orientation === 'vertical' && 'overflow-y-auto overflow-x-hidden',
        orientation === 'horizontal' && 'overflow-x-auto overflow-y-hidden',
        orientation === 'both' && 'overflow-auto',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  ),
)

ScrollArea.displayName = 'ScrollArea'

export { ScrollArea }
