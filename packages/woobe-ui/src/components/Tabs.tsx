import { type ReactNode, useEffect, useState } from 'react'
import { cn } from '../lib/cn'

export interface TabItem {
  id: string
  label: ReactNode
  content: ReactNode
}

export interface TabsProps {
  tabs: TabItem[]
  defaultTab?: string
  value?: string
  onValueChange?: (value: string) => void
  className?: string
  contentClassName?: string
}

export function Tabs({ tabs, defaultTab, value, onValueChange, className, contentClassName }: TabsProps) {
  const [internalActive, setInternalActive] = useState(defaultTab || tabs[0]?.id)
  const active = value ?? internalActive

  useEffect(() => {
    if (value === undefined && active && !tabs.some((tab) => tab.id === active)) {
      setInternalActive(defaultTab || tabs[0]?.id)
    }
  }, [active, defaultTab, tabs, value])

  const setActive = (next: string) => {
    if (value === undefined) setInternalActive(next)
    onValueChange?.(next)
  }

  return (
    <div className={cn('w-full', className)}>
      <div className="shrink-0 overflow-x-auto border-b border-border pb-ui-md">
        <div role="tablist" className="inline-flex min-w-max rounded-control border border-border bg-control p-ui-control-inset">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={active === tab.id}
              onClick={() => setActive(tab.id)}
              className={cn(
                'flex h-control-segment items-center whitespace-nowrap rounded-technical border px-ui-sm font-mono text-system-label font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40',
                active === tab.id
                  ? 'border-primary/35 bg-primary/[0.12] text-accent-foreground'
                  : 'border-transparent text-muted-foreground hover:bg-accent/45 hover:text-accent-foreground/90',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      <div className={cn('mt-ui-lg', contentClassName)}>
        {tabs.find((tab) => tab.id === active)?.content}
      </div>
    </div>
  )
}
