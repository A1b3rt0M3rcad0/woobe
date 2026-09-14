import { type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../lib/cn'

export type StepperState = 'pending' | 'current' | 'complete'

export interface StepperItem {
  id: string
  label: ReactNode
  description?: ReactNode
  state?: StepperState
}

export interface StepperProps extends Omit<HTMLAttributes<HTMLDivElement>, 'children'> {
  items: StepperItem[]
}

function CompleteMark() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className="h-icon-sm w-icon-sm shrink-0 text-success" fill="none">
      <path d="m3.5 8.25 2.75 2.75 6.25-6.25" stroke="currentColor" strokeWidth="1.45" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function Stepper({ items, className, ...props }: StepperProps) {
  return (
    <div className={cn('grid gap-ui-xs sm:grid-flow-col sm:auto-cols-fr', className)} {...props}>
      {items.map((item, index) => {
        const state = item.state ?? 'pending'
        const current = state === 'current'
        const complete = state === 'complete'

        return (
          <div
            key={item.id}
            aria-current={current ? 'step' : undefined}
            className={cn(
              'min-w-0 rounded-container border px-ui-md py-ui-sm',
              current ? 'border-primary/35 bg-primary/[0.08]' : 'border-border/75 bg-background/25',
            )}
          >
            <div className="flex min-w-0 items-start justify-between gap-ui-sm">
              <div className="min-w-0">
                <p className="break-words font-mono text-system-control font-medium text-accent-foreground">
                  {index + 1} · {item.label}
                </p>
                {item.description ? (
                  <p className="mt-ui-hairline break-words font-mono text-system-meta text-muted-foreground">
                    {item.description}
                  </p>
                ) : null}
                <p className="mt-ui-xs font-mono text-system-meta uppercase tracking-ui-label text-muted-foreground/80">
                  {complete ? 'Complete' : current ? 'Current' : 'Pending'}
                </p>
              </div>
              {complete ? <CompleteMark /> : null}
            </div>
          </div>
        )
      })}
    </div>
  )
}
