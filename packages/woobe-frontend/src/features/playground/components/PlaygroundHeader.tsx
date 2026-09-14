import { useState } from 'react'
import { Badge, SegmentedControl, Select } from '@woobe/ui'
import { Button } from '@/components/ui/Button'
import { Code2, PanelRight, PanelLeft, Bot, ArrowLeft, History, Lock, Route } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import { UI_LAYER_CLASS } from '@/lib/ui-layers'
import { cn } from '@/lib/utils'
import {
  executionStrategyDescriptor,
  executionStrategyForEnvironment,
  executionStrategySelectOptions,
  withExecutionStrategy,
} from '@/features/agents/executionStrategy'
import { useExecutionStrategies, useReleases } from '@/features/agents/hooks'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
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
  const { state, setField } = useAgentEditor()
  const { data: releases = [] } = useReleases(agent.id)
  const { data: executionStrategies = [], isLoading: executionStrategiesLoading, isError: executionStrategiesError } = useExecutionStrategies()

  const executionStrategy = executionStrategyForEnvironment(
    environment,
    state.runtimeConfig,
    releases,
  )
  const strategyOptions = executionStrategySelectOptions(executionStrategies, executionStrategy)
  const selectedStrategy = executionStrategyDescriptor(executionStrategies, executionStrategy)
  const strategyCatalogReady = !executionStrategiesLoading && !executionStrategiesError && executionStrategies.length > 0
  const strategyReadOnly = environment !== 'draft'
  const strategyDisabled = strategyReadOnly || environmentChangeDisabled || !strategyCatalogReady
  const strategyTitle = strategyReadOnly
    ? `Execution Strategy ${selectedStrategy?.display_name ?? executionStrategy} is locked by the immutable ${environment} snapshot.`
    : selectedStrategy?.description ?? 'Select the Execution Strategy used by the next Draft Run.'

  const handleExecutionStrategyChange = (strategy: string) => {
    if (strategyReadOnly || environmentChangeDisabled || !strategyCatalogReady) return
    setField(
      'runtimeConfig',
      withExecutionStrategy(state.runtimeConfig, strategy),
    )
  }

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
      <header className={`relative ${UI_LAYER_CLASS.playgroundChrome} flex h-workspace-header shrink-0 items-center justify-between border-b border-border bg-surface/[0.92] px-ui-md`}>
        <div className="flex min-w-0 flex-1 items-center gap-ui-sm">
          <button
            onClick={handleBack}
            className="flex h-control-sm shrink-0 items-center gap-ui-xs rounded-control border border-transparent px-ui-sm font-mono text-chrome-meta text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50"
            title="Back"
          >
            <ArrowLeft className="h-icon-sm w-icon-sm" />
            <span className="hidden sm:inline">Back</span>
          </button>
          <div className="h-6 w-px bg-border" />
          <span className="flex h-control-segment w-control-segment shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light">
            <Bot className="h-icon w-icon" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 items-center gap-ui-sm">
              <span className="min-w-0 truncate font-sans text-entity-title font-semibold text-slate-50" title={agent.name}>{agent.name}</span>
              {releaseVersion && releaseStatus ? (
                <Badge variant={releaseStatus === 'production' ? 'success' : releaseStatus === 'staging' ? 'warning' : 'outline'} className="shrink-0">
                  {releaseVersion}
                </Badge>
              ) : null}
            </div>
            <p className="mt-ui-hairline hidden truncate font-mono text-chrome-nano text-muted-foreground md:block" title={`${agent.provider || 'provider not set'} / ${agent.model || 'model not set'}`}>
              {agent.provider || 'provider not set'} / {agent.model || 'model not set'}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-ui-xs">
          <div className="hidden min-w-[10rem] items-center gap-ui-xs lg:flex" title={strategyTitle}>
            <Route className="h-icon-sm w-icon-sm shrink-0 text-muted-foreground" />
            <Select
              aria-label="Playground Execution Strategy"
              value={executionStrategy}
              disabled={strategyDisabled}
              options={strategyOptions}
              onChange={(event) => handleExecutionStrategyChange(event.target.value)}
              className="h-control-sm min-w-[8.5rem]"
            />
            {strategyReadOnly ? <Lock className="h-icon-sm w-icon-sm shrink-0 text-muted-foreground" aria-label="Strategy locked by snapshot" /> : null}
          </div>

          <SegmentedControl
            ariaLabel="Agent environment"
            value={environment}
            onValueChange={(next) => onEnvironmentChange(next as RuntimeEnvironment)}
            items={environments.map((item) => ({ value: item, label: item.toUpperCase(), disabled: environmentChangeDisabled }))}
          />

          <button
            onClick={onToggleLeftPanel}
            className={cn(
              'flex h-control-sm w-control-sm items-center justify-center rounded-control border transition-colors',
              showLeftPanel
                ? 'border-primary/35 bg-primary/[0.10] text-primary-light'
                : 'border-border bg-control/40 text-muted-foreground hover:bg-control hover:text-slate-50',
            )}
            title={showLeftPanel ? 'Hide operations' : 'Show operations'}
          >
            <PanelLeft className="h-icon w-icon" />
          </button>

          <Button variant="outline" size="sm" disabled={environmentChangeDisabled} onClick={() => openManager()}>
            <History className="h-icon w-icon" />
            <span className="hidden xl:inline">Manage Agent</span>
          </Button>

          <Button variant="outline" size="sm" onClick={onApiClick}>
            <Code2 className="h-icon w-icon" />
            <span className="hidden xl:inline">API</span>
          </Button>

          <AgentControlsPopover agent={agent} projectId={projectId} />
          <AgentLifecycleAction agentId={agent.id} environment={environment} disabled={environmentChangeDisabled} onManageAgent={openManager} />

          <button
            onClick={onToggleRightPanel}
            className={cn(
              'flex h-control-sm w-control-sm items-center justify-center rounded-control border transition-colors',
              showRightPanel
                ? 'border-primary/35 bg-primary/[0.10] text-primary-light'
                : 'border-border bg-control/40 text-muted-foreground hover:bg-control hover:text-slate-50',
            )}
            title={showRightPanel ? 'Hide inspector' : 'Show inspector'}
          >
            <PanelRight className="h-icon w-icon" />
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
