import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface InputGroupProps extends HTMLAttributes<HTMLDivElement> {
  start?: ReactNode
  end?: ReactNode
}

const InputGroup = forwardRef<HTMLDivElement, InputGroupProps>(
  ({ className, start, end, children, ...props }, ref) => (
    <div ref={ref} className={cn('relative w-full', className)} {...props}>
      <div className={cn(Boolean(start) && '[&_input]:pl-9', Boolean(end) && '[&_input]:pr-10')}>
        {children}
      </div>
      {start ? (
        <span className="pointer-events-none absolute left-ui-md top-1/2 flex -translate-y-1/2 items-center justify-center text-muted-foreground [&_svg]:h-icon [&_svg]:w-icon">
          {start}
        </span>
      ) : null}
      {end ? (
        <span className="absolute right-ui-xs top-1/2 flex -translate-y-1/2 items-center justify-center">
          {end}
        </span>
      ) : null}
    </div>
  ),
)
InputGroup.displayName = 'InputGroup'

export { InputGroup }
