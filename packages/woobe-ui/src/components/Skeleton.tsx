import { forwardRef, type HTMLAttributes } from 'react'
import { cn } from '../lib/cn'

const Skeleton = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('animate-pulse rounded-technical bg-border/70', className)} {...props} />
  ),
)

Skeleton.displayName = 'Skeleton'

export { Skeleton }
