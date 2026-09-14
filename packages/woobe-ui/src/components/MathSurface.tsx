import type { ReactNode } from 'react'
import { cn } from '../lib/cn'

export interface MathSurfaceProps {
  children: ReactNode
  display?: boolean
  className?: string
  title?: string
}

export function MathSurface({ children, display = false, className, title }: MathSurfaceProps) {
  if (!display) {
    return (
      <span
        className={cn(
          'mx-ui-hairline inline-flex max-w-full align-middle [&_math]:max-w-full [&_math]:font-serif [&_math]:text-[1.05em] [&_math]:text-accent-foreground',
          className,
        )}
        data-math-inline="true"
        title={title}
      >
        {children}
      </span>
    )
  }

  return (
    <div
      className={cn(
        'my-ui-md max-w-full overflow-x-auto rounded-container border border-border bg-control/70 px-ui-md py-ui-sm text-center [&_math]:min-w-max [&_math]:max-w-full [&_math]:font-serif [&_math]:text-[1.08em] [&_math]:text-accent-foreground',
        className,
      )}
      data-math-display="true"
      title={title}
    >
      {children}
    </div>
  )
}
