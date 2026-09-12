import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface MathSurfaceProps extends Omit<HTMLAttributes<HTMLDivElement>, 'children'> {
  children: ReactNode
  display?: boolean
  inlineClassName?: string
}

export function MathSurface({
  children,
  display = false,
  className,
  inlineClassName,
  ...props
}: MathSurfaceProps) {
  if (!display) {
    return (
      <span
        className={cn(
          'whitespace-nowrap font-mono text-[0.94em] leading-none text-primary-light',
          inlineClassName,
        )}
      >
        {children}
      </span>
    )
  }

  return (
    <div
      className={cn(
        'my-ui-sm overflow-x-auto rounded-container border border-border bg-control px-ui-md py-ui-sm font-mono text-product-body leading-relaxed text-slate-100',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}
