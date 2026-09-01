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
      <ScrollArea orientation="horizontal" className="flex border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            className={cn(
              'px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-[1px] whitespace-nowrap',
              active === tab.id
                ? 'border-primary text-primary border-b-2'
                : 'border-transparent text-muted hover:text-white',
            )}
          >
            {tab.label}
          </button>
        ))}
      </ScrollArea>
      <div className="mt-4">
        {tabs.find((t) => t.id === active)?.content}
      </div>
    </div>
  )
}
