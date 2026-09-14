import { type HTMLAttributes } from 'react'
import { cn } from '../lib/cn'

export interface SeparatorProps extends HTMLAttributes<HTMLDivElement> {
  orientation?: 'horizontal' | 'vertical'
}

export function Separator({ className, orientation = 'horizontal', ...props }: SeparatorProps) {
  return (
    <div
      aria-orientation={orientation}
      className={cn(orientation === 'horizontal' ? 'h-px w-full bg-border' : 'h-full w-px bg-border', className)}
      {...props}
    />
  )
}
