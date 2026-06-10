import { useRef } from 'react'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dropdown, type DropdownHandle } from '@/components/ui/Dropdown'
import { Code2, Settings, Plus, PanelRight, PanelLeft, Bot, ArrowLeft, ChevronDown, Circle } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import { formatSessionLabel } from '../utils'
import type { Agent } from '@/features/agents/types'
import type { SessionListItem } from '@/features/playground/types'
import type { ReleaseStatus } from '@/features/agents/types'

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
  releaseVersion?: string
  releaseStatus?: ReleaseStatus
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
  releaseVersion,
  releaseStatus,
}: PlaygroundHeaderProps) {
  const navigate = useNavigate()
  const { organizationId, projectId } = useParams<{ organizationId?: string; projectId: string }>()
  const sessionDropdownRef = useRef<DropdownHandle>(null)
  const currentSession = sessionId ? sessions.find((s) => s.id === sessionId) ?? null : null

  const handleBackToProject = () => {
    if (organizationId && projectId) {
      navigate(`/organizations/${organizationId}/projects/${projectId}`)
    } else if (projectId) {
      navigate(`/projects/${projectId}`)
    }
  }

  return (
    <header className="h-[72px] shrink-0 flex items-center justify-between border-b border-border bg-surface px-4">
      <div className="flex items-center gap-4 min-w-0">
        <button
          onClick={handleBackToProject}
          className="flex items-center gap-1 text-xs text-muted hover:text-white transition-colors shrink-0"
          title="Back to project"
        >
          <ArrowLeft className="h-4 w-4" />
          <span className="hidden sm:inline">Project</span>
        </button>
        <div className="flex items-center gap-2 shrink-0">
          <Bot className="h-5 w-5 text-primary" />
          <span className="text-sm font-semibold text-white">ProjectRAI</span>
        </div>
        <div className="flex items-center gap-2">
          <h1 className="text-sm font-medium text-white truncate max-w-[200px]">{agent.name}</h1>
          <StatusBadge status={agent.status} />
          {releaseVersion && releaseStatus && (
            <Badge variant={releaseStatus === 'production' ? 'success' : releaseStatus === 'staging' ? 'warning' : 'secondary'}>
              {releaseStatus === 'production' ? '● ' : ''}{releaseVersion}
            </Badge>
          )}
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
          <Dropdown
            ref={sessionDropdownRef}
            align="end"
            className="min-w-[180px]"
            trigger={
              <button className="flex h-9 w-full items-center justify-between gap-2 rounded-lg border border-border bg-transparent px-3 py-1 text-sm transition-colors cursor-pointer hover:border-primary/30">
                <span className={currentSession ? 'text-white truncate' : 'text-muted truncate'}>
                  {currentSession ? formatSessionLabel(currentSession) : 'Select a session'}
                </span>
                <ChevronDown className="h-4 w-4 shrink-0 text-muted" />
              </button>
            }
          >
            <div className="py-1">
              <button
                onClick={() => { onNewSession(); sessionDropdownRef.current?.close() }}
                className="flex w-full items-center gap-2 px-3 py-2 text-sm text-muted hover:text-white hover:bg-accent transition-colors"
              >
                <Plus className="h-4 w-4" />
                New Session
              </button>
              {sessions.length > 0 && <div className="mx-2 my-1 border-t border-border" />}
              {sessions.map((s) => (
                <button
                  key={s.id}
                  onClick={() => { onSessionSelect(s.id); sessionDropdownRef.current?.close() }}
                  className={`flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors ${
                    s.id === sessionId
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted hover:text-white hover:bg-accent'
                  }`}
                >
                  <Circle className={`h-2 w-2 shrink-0 fill-current ${s.id === sessionId ? 'text-primary' : 'text-muted'}`} />
                  <span className="truncate text-left flex-1">{formatSessionLabel(s)}</span>
                  {s.id === sessionId && (
                    <span className="ml-auto text-[10px] font-medium text-primary uppercase">Active</span>
                  )}
                </button>
              ))}
            </div>
          </Dropdown>
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
