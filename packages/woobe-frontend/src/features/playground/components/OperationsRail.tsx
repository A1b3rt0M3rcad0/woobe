import { Activity, History, Loader2, MessageSquarePlus } from 'lucide-react'
import type { RuntimeEnvironment } from '@/features/agents/types'
import { cn } from '@/lib/utils'

// `debug` remains an internal compatibility value while existing Playground state
// migrates to Runs. It is never rendered as a separate navigation destination.
export type LeftPanelTab = 'debug' | 'traces' | 'sessions'

interface OperationsRailProps {
  activeTab: LeftPanelTab | null
  environment: RuntimeEnvironment
  onTabChange: (tab: LeftPanelTab) => void
  onNewSession: () => void | Promise<void>
  newSessionDisabled?: boolean
  newSessionDisabledReason?: string
  newSessionPending?: boolean
}

const items: { id: Exclude<LeftPanelTab, 'debug'>; label: string; icon: typeof Activity }[] = [
  { id: 'traces', label: 'Runs', icon: Activity },
  { id: 'sessions', label: 'Sessions', icon: History },
]

export function OperationsRail({
  activeTab,
  onTabChange,
  onNewSession,
  newSessionDisabled = false,
  newSessionDisabledReason,
  newSessionPending = false,
}: OperationsRailProps) {
  const normalizedActiveTab = activeTab === 'debug' ? 'traces' : activeTab

  return (
    <div className="w-[58px] shrink-0 flex flex-col items-center border-r border-border/90 bg-surface/75 py-3 gap-1 shadow-sm shadow-black/5">
      <button
        type="button"
        onClick={() => void onNewSession()}
        disabled={newSessionDisabled || newSessionPending}
        title={newSessionDisabledReason ?? 'New Session'}
        aria-label="New Session"
        className="mb-1 flex w-12 flex-col items-center gap-0.5 rounded-lg border border-primary/40 bg-primary/10 py-2 text-primary-light shadow-sm shadow-primary/5 transition-colors hover:border-primary/60 hover:bg-primary/15 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/50 disabled:cursor-not-allowed disabled:opacity-45"
      >
        {newSessionPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageSquarePlus className="h-4 w-4" />}
        <span className="text-center text-[9px] leading-[10px]">New<br />Session</span>
      </button>

      <div className="my-0.5 h-px w-8 bg-border/80" aria-hidden="true" />

      {items.map((item) => {
        const Icon = item.icon
        const isActive = normalizedActiveTab === item.id
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
