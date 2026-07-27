import { Activity, CircleDot, History } from 'lucide-react'
import type { RuntimeEnvironment } from '@/features/agents/types'
import { cn } from '@/lib/utils'

export type LeftPanelTab = 'debug' | 'traces' | 'sessions'

interface OperationsRailProps {
  activeTab: LeftPanelTab | null
  environment: RuntimeEnvironment
  onTabChange: (tab: LeftPanelTab) => void
}

const draftItems: { id: LeftPanelTab; label: string; icon: typeof Activity }[] = [
  { id: 'debug', label: 'Current Run', icon: CircleDot },
  { id: 'traces', label: 'Runs', icon: Activity },
  { id: 'sessions', label: 'Sessions', icon: History },
]

const immutableItems: { id: LeftPanelTab; label: string; icon: typeof Activity }[] = [
  { id: 'traces', label: 'Runs', icon: Activity },
  { id: 'debug', label: 'Debug', icon: CircleDot },
  { id: 'sessions', label: 'Sessions', icon: History },
]

export function OperationsRail({ activeTab, environment, onTabChange }: OperationsRailProps) {
  const items = environment === 'draft' ? draftItems : immutableItems

  return (
    <div className="w-[58px] shrink-0 flex flex-col items-center border-r border-border/90 bg-surface/75 py-3 gap-1 shadow-sm shadow-black/5">
      {items.map((item) => {
        const Icon = item.icon
        const isActive = activeTab === item.id
        return (
          <button
            type="button"
            key={item.id}
            onClick={() => onTabChange(item.id)}
            className={cn(
              'flex w-12 flex-col items-center gap-0.5 rounded-lg border py-2 text-xs transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/50',
              isActive
                ? 'border-primary/35 bg-primary/10 text-primary-light shadow-sm shadow-primary/5'
                : 'border-transparent text-muted hover:border-border/80 hover:bg-background/60 hover:text-white',
            )}
            title={item.label}
          >
            <Icon className="h-4 w-4" />
            <span className="text-[9px] leading-tight">{item.label}</span>
          </button>
        )
      })}
      <div className="flex-1" />
    </div>
  )
}
