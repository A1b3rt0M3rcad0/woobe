import { type ReactNode, useEffect, useId, useState } from 'react'
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
  const id = useId()
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
      <div className="shrink-0 overflow-x-auto border-b border-border pb-ui-sm">
        <div role="tablist" className="inline-flex min-w-max gap-ui-hairline rounded-control border border-border bg-control p-ui-control-inset">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`${id}-tab-${tab.id}`}
              aria-controls={`${id}-panel-${tab.id}`}
              tabIndex={active === tab.id ? 0 : -1}
              aria-selected={active === tab.id}
              onClick={() => setActive(tab.id)}
              onKeyDown={(event) => {
                const index = tabs.findIndex(item => item.id === tab.id)
                const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length
                  : event.key === 'ArrowLeft' ? (index - 1 + tabs.length) % tabs.length
                  : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null
                if (next === null) return
                event.preventDefault()
                setActive(tabs[next].id)
                document.getElementById(`${id}-tab-${tabs[next].id}`)?.focus()
              }}
              className={cn(
                'flex h-control-xs items-center whitespace-nowrap rounded-technical border px-ui-sm font-mono text-chrome-label font-normal transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40',
                active === tab.id
                  ? 'border-border bg-accent text-accent-foreground'
                  : 'border-transparent text-muted-foreground hover:text-accent-foreground',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      <div role="tabpanel" id={`${id}-panel-${active}`} aria-labelledby={`${id}-tab-${active}`} tabIndex={0} className={cn('mt-ui-md', contentClassName)}>
        {tabs.find((tab) => tab.id === active)?.content}
      </div>
    </div>
  )
}
