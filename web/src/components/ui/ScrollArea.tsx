import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

interface ScrollAreaProps extends React.HTMLAttributes<HTMLDivElement> {
  orientation?: 'vertical' | 'horizontal' | 'both'
}

export const ScrollArea = forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ children, className, orientation = 'vertical', ...props }, ref) => {
    return (
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
    )
  },
)

ScrollArea.displayName = 'ScrollArea'
