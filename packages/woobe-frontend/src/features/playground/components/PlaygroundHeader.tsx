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
      <header className={`relative ${UI_LAYER_CLASS.playgroundChrome} flex h-[54px] shrink-0 items-center justify-between border-b border-border bg-surface/[0.92] px-3`}>
        <div className="flex min-w-0 items-center gap-2">
          <button
            onClick={handleBack}
            className="flex h-[30px] shrink-0 items-center gap-1.5 rounded-control border border-transparent px-2 font-mono text-[9px] text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50"
            title="Back"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Back</span>
          </button>
          <div className="h-6 w-px bg-border" />
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light">
            <Bot className="h-3.5 w-3.5" />
          </span>
          <div className="min-w-0">
            <div className="flex min-w-0 items-center gap-2">
              <span className="max-w-[220px] truncate font-mono text-[10px] font-bold text-slate-50">{agent.name}</span>
              {releaseVersion && releaseStatus ? (
                <Badge variant={releaseStatus === 'production' ? 'success' : releaseStatus === 'staging' ? 'warning' : 'secondary'} className="shrink-0">
                  {releaseVersion}
                </Badge>
              ) : null}
            </div>
            <p className="mt-0.5 hidden max-w-[300px] truncate font-mono text-[8px] text-muted-foreground md:block">
              {agent.provider || 'provider not set'} / {agent.model || 'model not set'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <div role="tablist" aria-label="Agent environment" className="inline-flex rounded-control border border-border bg-control p-[3px]">
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
                  'flex h-[27px] items-center rounded-technical border px-2.5 font-mono text-[8px] uppercase tracking-[0.08em] transition-colors disabled:cursor-not-allowed disabled:opacity-50',
                  item === environment
                    ? 'border-primary/35 bg-primary/[0.12] text-slate-50'
                    : 'border-transparent text-muted-foreground hover:bg-accent/45 hover:text-slate-200',
                )}
              >
                {item}
              </button>
            ))}
          </div>

          <button
            onClick={onToggleLeftPanel}
            className={cn(
              'flex h-[30px] w-[30px] items-center justify-center rounded-control border transition-colors',
              showLeftPanel
                ? 'border-primary/35 bg-primary/[0.10] text-primary-light'
                : 'border-border bg-control/40 text-muted-foreground hover:bg-control hover:text-slate-50',
            )}
            title={showLeftPanel ? 'Hide operations' : 'Show operations'}
          >
            <PanelLeft className="h-3.5 w-3.5" />
          </button>

          <Button variant="outline" size="sm" disabled={environmentChangeDisabled} onClick={() => openManager()}>
            <History className="h-3.5 w-3.5" />
            <span className="hidden xl:inline">Manage Agent</span>
          </Button>

          <Button variant="outline" size="sm" onClick={onApiClick}>
            <Code2 className="h-3.5 w-3.5" />
            <span className="hidden xl:inline">API</span>
          </Button>

          <AgentControlsPopover agent={agent} projectId={projectId} />
          <AgentLifecycleAction agentId={agent.id} environment={environment} disabled={environmentChangeDisabled} onManageAgent={openManager} />

          <button
            onClick={onToggleRightPanel}
            className={cn(
              'flex h-[30px] w-[30px] items-center justify-center rounded-control border transition-colors',
              showRightPanel
                ? 'border-primary/35 bg-primary/[0.10] text-primary-light'
                : 'border-border bg-control/40 text-muted-foreground hover:bg-control hover:text-slate-50',
            )}
            title={showRightPanel ? 'Hide inspector' : 'Show inspector'}
          >
            <PanelRight className="h-3.5 w-3.5" />
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
