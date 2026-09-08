import type { ReactNode } from 'react'
import { Activity, History, Loader2, MessageSquarePlus } from 'lucide-react'
import { cn } from '@/lib/utils'

export type PanelTab = 'traces' | 'sessions'

export function Badge({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'draft' | 'staging' | 'production' | 'warning' | 'danger' }) {
  const styles = {
    default: 'border-border bg-background/50 text-muted',
    draft: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
    staging: 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300',
    production: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    warning: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
    danger: 'border-red-500/30 bg-red-500/10 text-red-300',
  }
  return <span className={cn('rounded-md border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide', styles[tone])}>{children}</span>
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
    <nav className="relative z-40 flex w-14 shrink-0 flex-col items-center gap-1 border-r border-border bg-surface/75 py-3">
      <button
        type="button"
        onClick={() => void onNewSession()}
        disabled={newSessionDisabled || newSessionPending}
        title={newSessionDisabledReason ?? 'New Session'}
        aria-label="New Session"
        className="mb-1 flex w-11 flex-col items-center gap-0.5 rounded-lg border border-primary/40 bg-primary/10 py-2 text-primary-light shadow-sm shadow-primary/5 transition-colors hover:border-primary/60 hover:bg-primary/15 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/50 disabled:cursor-not-allowed disabled:opacity-45"
      >
        {newSessionPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageSquarePlus className="h-4 w-4" />}
        <span className="text-center text-[9px] leading-[10px]">New<br />Session</span>
      </button>

      <div className="my-0.5 h-px w-8 bg-border/80" aria-hidden="true" />

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
              'flex w-11 flex-col items-center gap-1 rounded-lg border py-2 text-[9px] transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/50',
              active
                ? 'border-primary/35 bg-primary/10 text-primary-light'
                : 'border-transparent text-muted hover:border-border/80 hover:bg-background/60 hover:text-white',
            )}
          >
            <Icon className="h-4 w-4" />
            <span>{item.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
