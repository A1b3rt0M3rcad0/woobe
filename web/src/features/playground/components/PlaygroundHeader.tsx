import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { Code2, Settings, Plus, PanelRight, PanelLeft, Bot } from 'lucide-react'
import type { Agent } from '@/features/agents/types'
import type { SessionListItem } from '@/features/playground/types'

interface PlaygroundHeaderProps {
  agent: Agent
  sessions: SessionListItem[]
  sessionId: string | null
  showLeftPanel: boolean
  showRightPanel: boolean
  onToggleLeftPanel: () => void
  onToggleRightPanel: () => void
  onNewSession: () => void
  onSessionSelect: (id: string) => void
  onApiClick: () => void
  onSettingsClick: () => void
}

function formatSessionLabel(s: SessionListItem): string {
  const date = s.last_message_at
    ? new Date(s.last_message_at)
    : s.created_at
      ? new Date(s.created_at)
      : null
  const dateStr = date
    ? date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'Unknown'
  const msgCount = s.message_count ?? 0
  return `${dateStr} (${msgCount} msg${msgCount !== 1 ? 's' : ''})`
}

export function PlaygroundHeader({
  agent,
  sessions,
  sessionId,
  showLeftPanel,
  showRightPanel,
  onToggleLeftPanel,
  onToggleRightPanel,
  onNewSession,
  onSessionSelect,
  onApiClick,
  onSettingsClick,
}: PlaygroundHeaderProps) {
  const sessionOptions = sessions.map((s) => ({
    value: s.id,
    label: formatSessionLabel(s),
  }))

  return (
    <header className="h-[72px] shrink-0 flex items-center justify-between border-b border-border bg-surface px-4">
      <div className="flex items-center gap-4 min-w-0">
        <div className="flex items-center gap-2 shrink-0">
          <Bot className="h-5 w-5 text-primary" />
          <span className="text-sm font-semibold text-white">ProjectRAI</span>
        </div>
        <div className="flex items-center gap-2">
          <h1 className="text-sm font-medium text-white truncate max-w-[200px]">{agent.name}</h1>
          <StatusBadge status={agent.status} />
        </div>
        <span className="text-xs text-muted hidden md:inline">
          {agent.provider}/{agent.model}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onToggleLeftPanel}
          className="flex items-center justify-center w-8 h-8 rounded-lg text-muted hover:text-white hover:bg-accent transition-colors"
          title={showLeftPanel ? 'Hide operations' : 'Show operations'}
        >
          <PanelLeft className={`h-4 w-4 transition-opacity ${showLeftPanel ? 'opacity-100' : 'opacity-50'}`} />
        </button>

        <div className="flex items-center gap-1.5">
          <Button variant="outline" size="sm" onClick={onNewSession}>
            <Plus className="mr-1 h-4 w-4" />
            New Session
          </Button>
          <Select
            value={sessionId ?? ''}
            onChange={(e) => {
              const val = e.target.value
              if (val === '__new__') {
                onNewSession()
              } else {
                onSessionSelect(val)
              }
            }}
            options={[
              { value: '__new__', label: '+ New Session' },
              ...sessionOptions,
            ]}
            className="min-w-[180px]"
          />
        </div>

        <Button variant="outline" size="sm" onClick={onApiClick}>
          <Code2 className="mr-1 h-4 w-4" />
          API
        </Button>
        <Button variant="outline" size="sm" onClick={onSettingsClick}>
          <Settings className="mr-1 h-4 w-4" />
          Settings
        </Button>

        <button
          onClick={onToggleRightPanel}
          className="flex items-center justify-center w-8 h-8 rounded-lg text-muted hover:text-white hover:bg-accent transition-colors"
          title={showRightPanel ? 'Hide inspector' : 'Show inspector'}
        >
          <PanelRight className={`h-4 w-4 transition-opacity ${showRightPanel ? 'opacity-100' : 'opacity-50'}`} />
        </button>
      </div>
    </header>
  )
}
