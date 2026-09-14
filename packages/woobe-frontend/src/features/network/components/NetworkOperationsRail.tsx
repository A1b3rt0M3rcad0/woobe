import type { ReactNode } from 'react'
import { Activity, History, Loader2, MessageSquarePlus } from 'lucide-react'
import { Badge as WoobeBadge, type BadgeVariant } from '@woobe/ui'
import { cn } from '@/lib/utils'

export type PanelTab = 'traces' | 'sessions'
type NetworkBadgeTone = 'default' | 'draft' | 'staging' | 'production' | 'warning' | 'danger'

const badgeVariants: Record<NetworkBadgeTone, BadgeVariant> = {
  default: 'outline',
  draft: 'default',
  staging: 'network',
  production: 'success',
  warning: 'warning',
  danger: 'destructive',
}

export function Badge({ children, tone = 'default' }: { children: ReactNode; tone?: NetworkBadgeTone }) {
  return <WoobeBadge size="compact" variant={badgeVariants[tone]} className="uppercase tracking-ui-label">{children}</WoobeBadge>
}

const items = [
  { id: 'traces' as const, label: 'Runs', icon: Activity },
  { id: 'sessions' as const, label: 'Sessions', icon: History },
]

export function NetworkOperationsRail({
  activeTab,
  onTabChange,
  onNewSession,
  newSessionDisabled = false,
  newSessionDisabledReason,
  newSessionPending = false,
}: {
  activeTab: PanelTab | null
  onTabChange: (tab: PanelTab) => void
  onNewSession: () => void | Promise<void>
  newSessionDisabled?: boolean
  newSessionDisabledReason?: string
  newSessionPending?: boolean
}) {
  return (
    <nav className="relative z-playground-chrome flex w-playground-rail shrink-0 flex-col items-center gap-ui-xs border-r border-border bg-surface/75 py-ui-md">
      <button
        type="button"
        onClick={() => void onNewSession()}
        disabled={newSessionDisabled || newSessionPending}
        title={newSessionDisabledReason ?? 'New Session'}
        aria-label="New Session"
        className="mb-ui-xs flex w-control-row flex-col items-center gap-ui-hairline rounded-control border border-primary/40 bg-primary/[0.08] py-ui-sm font-mono text-system-nano text-primary-light transition-colors hover:border-primary/60 hover:bg-primary/[0.12] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/50 disabled:cursor-not-allowed disabled:opacity-45"
      >
        {newSessionPending ? <Loader2 className="h-icon-lg w-icon-lg animate-spin" /> : <MessageSquarePlus className="h-icon-lg w-icon-lg" />}
        <span className="text-center leading-3">New<br />Session</span>
      </button>

      <div className="my-ui-hairline h-px w-control-sm bg-border/80" aria-hidden="true" />

      {items.map((item) => {
        const Icon = item.icon
        const active = activeTab === item.id
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onTabChange(item.id)}
            title={item.label}
            className={cn(
              'flex w-control-row flex-col items-center gap-ui-xs rounded-control border py-ui-sm font-mono text-system-nano transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/50',
              active
                ? 'border-primary/35 bg-primary/[0.08] text-primary-light'
                : 'border-transparent text-muted-foreground hover:border-border hover:bg-background/60 hover:text-accent-foreground',
            )}
          >
            <Icon className="h-icon-lg w-icon-lg" />
            <span>{item.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
