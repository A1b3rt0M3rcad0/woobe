import { type ReactNode, useState, useRef, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { ScrollArea } from '@/components/ui/ScrollArea'

interface TabItem {
  id: string
  label: string
  icon?: ReactNode
  content: ReactNode
}

interface InspectorTabsProps {
  tabs: TabItem[]
  defaultTab?: string
  onTabChange?: (id: string) => void
}

export function InspectorTabs({ tabs, defaultTab, onTabChange }: InspectorTabsProps) {
  const [active, setActive] = useState(defaultTab || tabs[0]?.id)
  const tabBarRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (defaultTab && defaultTab !== active) {
      setActive(defaultTab)
    }
  }, [defaultTab])

  const handleTabClick = (id: string) => {
    setActive(id)
    onTabChange?.(id)
  }

  return (
    <div className="flex flex-col h-full">
      <div
        ref={tabBarRef}
        className="flex border-b border-border bg-surface shrink-0 sticky top-0 z-10"
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTabClick(tab.id)}
            className={cn(
              'flex-1 flex items-center justify-center gap-1.5 px-2 py-2.5 text-xs font-medium transition-colors border-b-2 -mb-[1px]',
              active === tab.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted hover:text-white',
            )}
          >
            {tab.icon && <span className="shrink-0">{tab.icon}</span>}
            {tab.label}
          </button>
        ))}
      </div>
      <ScrollArea className="flex-1 min-h-0">
        {tabs.find((t) => t.id === active)?.content}
      </ScrollArea>
    </div>
  )
}
