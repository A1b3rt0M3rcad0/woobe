import { type ReactNode, useState } from 'react'
import { cn } from '@/lib/utils'
import { ScrollArea } from '@/components/ui/ScrollArea'

interface Tab {
  id: string
  label: ReactNode
  content: ReactNode
}

interface TabsProps {
  tabs: Tab[]
  defaultTab?: string
  className?: string
}

export function Tabs({ tabs, defaultTab, className }: TabsProps) {
  const [active, setActive] = useState(defaultTab || tabs[0]?.id)

  return (
    <div className={cn('w-full', className)}>
      <ScrollArea orientation="horizontal" className="border-b border-border pb-3">
        <div className="inline-flex min-w-max rounded-control border border-border bg-control p-[3px]">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActive(tab.id)}
              className={cn(
                'flex h-[27px] items-center whitespace-nowrap rounded-technical border px-2.5 font-mono text-[9px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40',
                active === tab.id
                  ? 'border-primary/35 bg-primary/[0.12] text-slate-50'
                  : 'border-transparent text-muted-foreground hover:bg-accent/45 hover:text-slate-200',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </ScrollArea>
      <div className="mt-4">
        {tabs.find((tab) => tab.id === active)?.content}
      </div>
    </div>
  )
}
