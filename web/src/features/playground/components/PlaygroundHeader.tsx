import { useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Code2, PanelRight, PanelLeft, Bot, ArrowLeft, History } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import { UI_LAYER_CLASS } from '@/lib/ui-layers'
import { cn } from '@/lib/utils'
import { AgentControlsPopover } from './AgentControlsPopover'
import { AgentLifecycleAction } from './AgentLifecycleAction'
import { AgentManagerModal, type AgentManagerMode, type AgentManagerSection } from './AgentManagerModal'
import type { Agent, ReleaseStatus, RuntimeEnvironment } from '@/features/agents/types'

interface PlaygroundHeaderProps {
  agent: Agent
  projectId: string
  showLeftPanel: boolean
  showRightPanel: boolean
  environment: RuntimeEnvironment
  environmentChangeDisabled?: boolean
  onEnvironmentChange: (environment: RuntimeEnvironment) => void
  onToggleLeftPanel: () => void
  onToggleRightPanel: () => void
  onApiClick: () => void
  onSettingsClick?: () => void
  releaseVersion?: string
  releaseStatus?: ReleaseStatus
}

const environments: RuntimeEnvironment[] = ['draft', 'staging', 'production']

function environmentSection(environment: RuntimeEnvironment): AgentManagerSection {
  return environment
}

export function PlaygroundHeader({
  agent,
  projectId,
  showLeftPanel,
  showRightPanel,
  environment,
  environmentChangeDisabled = false,
  onEnvironmentChange,
  onToggleLeftPanel,
  onToggleRightPanel,
  onApiClick,
  releaseVersion,
  releaseStatus,
}: PlaygroundHeaderProps) {
  const navigate = useNavigate()
  const { workspaceId } = useParams<{ workspaceId?: string; projectId: string }>()
  const [manager, setManager] = useState<{ section: AgentManagerSection; mode: AgentManagerMode } | null>(null)

  const handleBack = () => {
    const historyIndex = window.history.state?.idx
    if (typeof historyIndex === 'number' && historyIndex > 0) {
      navigate(-1)
      return
    }

    if (workspaceId) {
      navigate(`/workspaces/${workspaceId}/projects/${projectId}/agents`)
      return
    }
    navigate(`/projects/${projectId}/agents`)
  }

  const openManager = (section: AgentManagerSection = environmentSection(environment), mode: AgentManagerMode = 'browse') => {
    setManager({ section, mode })
  }

  const handleManagerEnvironmentChange = (next: RuntimeEnvironment) => {
    onEnvironmentChange(next)
    setManager({ section: environmentSection(next), mode: 'browse' })
  }

  return (
    <>
      <header className={`relative ${UI_LAYER_CLASS.playgroundChrome} h-[72px] shrink-0 flex items-center justify-between border-b border-border/90 bg-surface/80 px-4 shadow-sm shadow-black/5 backdrop-blur-sm`}>
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={handleBack}
            className="flex h-8 items-center gap-1.5 rounded-lg border border-transparent px-2 text-xs font-medium text-muted hover:text-white hover:border-border/80 hover:bg-background/60 transition-colors shrink-0"
            title="Back"
          >
            <ArrowLeft className="h-4 w-4" />
            <span className="hidden sm:inline">Back</span>
          </button>
          <div className="h-8 w-px bg-border/80" />
          <div className="flex items-center gap-2 shrink-0 rounded-lg border border-border/70 bg-background/45 px-2.5 py-1.5 min-w-0">
            <span className="flex h-6 w-6 items-center justify-center rounded-md border border-primary/20 bg-primary/10 text-primary-light shrink-0">
              <Bot className="h-3.5 w-3.5" />
            </span>
            <span className="truncate text-sm font-semibold text-white max-w-[240px]">{agent.name}</span>
          </div>
          <div className="flex items-center gap-2 min-w-0">
            {releaseVersion && releaseStatus && (
              <Badge variant={releaseStatus === 'production' ? 'success' : releaseStatus === 'staging' ? 'warning' : 'secondary'}>
                {releaseStatus === 'production' ? '● ' : ''}{releaseVersion}
              </Badge>
            )}
          </div>
          <span className="hidden max-w-[180px] truncate rounded-md border border-border/70 bg-background/45 px-2 py-1 font-mono text-[11px] text-muted md:inline">
            {agent.provider}/{agent.model}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div role="tablist" aria-label="Agent environment" className="flex rounded-xl border border-border bg-background/35 p-1">
            {environments.map((item) => (
              <button
                key={item}
                type="button"
                role="tab"
                aria-selected={item === environment}
                disabled={environmentChangeDisabled}
                onClick={() => onEnvironmentChange(item)}
                title={item === 'draft' ? 'Mutable working configuration' : item === 'staging' ? 'Immutable validation snapshot' : 'Immutable active Production release'}
                className={cn(
                  'rounded-lg px-3 py-1.5 text-[10px] capitalize transition-colors disabled:cursor-not-allowed disabled:opacity-50',
                  item === environment
                    ? item === 'production'
                      ? 'bg-emerald-500/10 text-emerald-300'
                      : item === 'staging'
                        ? 'bg-indigo-500/10 text-indigo-300'
                        : 'bg-primary/10 text-primary-light'
                    : 'text-muted hover:text-white',
                )}
              >
                {item}
              </button>
            ))}
          </div>

          <button
            onClick={onToggleLeftPanel}
            className={`flex items-center justify-center w-8 h-8 rounded-lg border transition-colors ${showLeftPanel ? 'border-primary/30 bg-primary/10 text-primary-light shadow-sm shadow-primary/5' : 'border-transparent text-muted hover:text-white hover:border-border/80 hover:bg-background/60'}`}
            title={showLeftPanel ? 'Hide operations' : 'Show operations'}
          >
            <PanelLeft className={`h-4 w-4 transition-opacity ${showLeftPanel ? 'opacity-100' : 'opacity-50'}`} />
          </button>

          <Button variant="outline" size="sm" disabled={environmentChangeDisabled} onClick={() => openManager()} className="border-border/80 bg-background/55 hover:border-primary/35 hover:bg-primary/5">
            <History className="mr-1 h-4 w-4" />
            Manage Agent
          </Button>

          <Button variant="outline" size="sm" onClick={onApiClick} className="border-border/80 bg-background/55 hover:border-primary/35 hover:bg-primary/5">
            <Code2 className="mr-1 h-4 w-4" />
            API
          </Button>

          <AgentControlsPopover agent={agent} projectId={projectId} />
          <AgentLifecycleAction agentId={agent.id} environment={environment} disabled={environmentChangeDisabled} onManageAgent={openManager} />

          <button
            onClick={onToggleRightPanel}
            className={`flex items-center justify-center w-8 h-8 rounded-lg border transition-colors ${showRightPanel ? 'border-primary/30 bg-primary/10 text-primary-light shadow-sm shadow-primary/5' : 'border-transparent text-muted hover:text-white hover:border-border/80 hover:bg-background/60'}`}
            title={showRightPanel ? 'Hide inspector' : 'Show inspector'}
          >
            <PanelRight className={`h-4 w-4 transition-opacity ${showRightPanel ? 'opacity-100' : 'opacity-50'}`} />
          </button>
        </div>
      </header>

      <AgentManagerModal
        open={Boolean(manager)}
        agentId={agent.id}
        agentName={agent.name}
        projectId={projectId}
        environment={environment}
        initialSection={manager?.section}
        initialMode={manager?.mode ?? 'browse'}
        onClose={() => setManager(null)}
        onEnvironmentChange={handleManagerEnvironmentChange}
      />
    </>
  )
}
