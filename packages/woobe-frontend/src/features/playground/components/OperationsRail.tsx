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
    <div className="flex w-playground-rail shrink-0 flex-col items-center gap-ui-xs border-r border-border bg-surface/[0.78] py-ui-sm">
      <button
        type="button"
        onClick={() => void onNewSession()}
        disabled={newSessionDisabled || newSessionPending}
        title={newSessionDisabledReason ?? 'New Session'}
        aria-label="New Session"
        className="mb-ui-xs flex h-control-row w-control-row flex-col items-center justify-center gap-ui-hairline rounded-control border border-primary/35 bg-primary/[0.08] font-mono text-system-meta text-primary-light transition-colors hover:bg-primary/[0.13] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40 disabled:cursor-not-allowed disabled:opacity-45"
      >
        {newSessionPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <MessageSquarePlus className="h-3.5 w-3.5" />}
        <span>New</span>
      </button>

      <div className="my-ui-xs h-px w-7 bg-border" aria-hidden="true" />

      {items.map((item) => {
        const Icon = item.icon
        const isActive = normalizedActiveTab === item.id
        return (
          <button
            type="button"
            key={item.id}
            onClick={() => onTabChange(item.id)}
            className={cn(
              'flex h-control-row w-control-row flex-col items-center justify-center gap-ui-hairline rounded-control border font-mono text-system-meta transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40',
              isActive
                ? 'border-primary/35 bg-primary/[0.10] text-primary-light'
                : 'border-transparent text-muted-foreground hover:border-border hover:bg-control/60 hover:text-slate-50',
            )}
            title={item.label}
          >
            <Icon className="h-3.5 w-3.5" />
            <span>{item.label}</span>
          </button>
        )
      })}
      <div className="flex-1" />
    </div>
  )
}
