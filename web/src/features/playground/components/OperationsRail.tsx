import { Bug, Activity, History, PanelLeftClose } from 'lucide-react'
import { cn } from '@/lib/utils'

export type LeftPanelTab = 'debug' | 'traces' | 'sessions'

interface OperationsRailProps {
  activeTab: LeftPanelTab | null
  onTabChange: (tab: LeftPanelTab) => void
  onCollapse: () => void
}

const items: { id: LeftPanelTab; label: string; icon: typeof Bug }[] = [
  { id: 'debug', label: 'Debug', icon: Bug },
  { id: 'traces', label: 'Traces', icon: Activity },
  { id: 'sessions', label: 'Sessions', icon: History },
]

export function OperationsRail({ activeTab, onTabChange, onCollapse }: OperationsRailProps) {
  return (
    <div className="w-[52px] shrink-0 flex flex-col items-center border-r border-border bg-surface py-3 gap-1">
      {items.map((item) => {
        const Icon = item.icon
        const isActive = activeTab === item.id
        return (
          <button
            key={item.id}
            onClick={() => onTabChange(item.id)}
            className={cn(
              'flex flex-col items-center gap-0.5 w-10 py-2 rounded-lg text-xs transition-colors',
              isActive
                ? 'bg-primary/10 text-primary'
                : 'text-muted hover:text-white hover:bg-accent',
            )}
            title={item.label}
          >
            <Icon className="h-4 w-4" />
            <span className="text-[10px] leading-tight">{item.label}</span>
          </button>
        )
      })}
      <div className="flex-1" />
      <button
        onClick={onCollapse}
        className="flex flex-col items-center gap-0.5 w-10 py-2 rounded-lg text-xs text-muted hover:text-white hover:bg-accent transition-colors"
        title="Collapse panel"
      >
        <PanelLeftClose className="h-4 w-4" />
      </button>
    </div>
  )
}
