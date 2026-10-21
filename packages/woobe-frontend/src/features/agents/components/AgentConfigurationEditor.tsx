import { useCallback, useEffect, useRef, useState } from 'react'
import { RotateCcw, Save } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { AgentSkillsSection } from '@/features/skills/AgentSkillsSection'
import { cn } from '@/lib/utils'
import { artifactCapabilityError, externalContextContractError, outputContractError, validateAgentEditorState } from '../editorValidation'
import { useCreateRelease, useReleases } from '../hooks'
import { useProviderModels } from '@/features/provider-models/hooks'
import type { Agent } from '../types'
import { AgentEditorNavigation, useAgentEditorSection } from './AgentEditorNavigation'
import { AgentOverviewSettings } from './AgentOverviewSettings'
import { AgentBehaviorSettings } from './AgentBehaviorSettings'
import { AgentRuntimeSettings } from './AgentRuntimeSettings'
import { AgentModelSettings } from './AgentModelSettings'
import { AgentKnowledgeSettings } from './AgentKnowledgeSettings'
import { AgentToolsSettings } from './AgentToolsSettings'
import { AgentOutputSettings } from './AgentOutputSettings'
import { AgentExternalContextSettings } from './AgentExternalContextSettings'
import { AgentArtifactSettings } from './AgentArtifactSettings'

interface AgentConfigurationEditorProps {
  agent: Agent
  projectId: string
  agentId: string
  onDirtyChange?: (dirty: boolean) => void
  onRegisterSaveAction?: (action: (() => Promise<boolean>) | null) => void
}

export function AgentConfigurationEditor({ agent, projectId, agentId, onDirtyChange, onRegisterSaveAction }: AgentConfigurationEditorProps) {
  const [section, setSection] = useAgentEditorSection()
  const [saveFailed, setSaveFailed] = useState(false)
  const { state, baseRevision, loadedReleaseVersion, setLoadedRelease, isDirty, updateBaseline, resetToBaseline } = useAgentEditor()
  const createRelease = useCreateRelease(agent.id)
  const { data: models = [] } = useProviderModels(projectId)
  const { data: releases = [] } = useReleases(agent.id)
  const draft = releases.find(release => release.status === 'draft')
  const modelUpdatesAvailable = [
    { id: state.providerModelId, hash: draft?.model_spec_hash ?? agent.settings?.model_spec_hash },
    { id: state.fallbackProviderModelId, hash: draft?.fallback_model_spec_hash ?? agent.settings?.fallback_model_spec_hash },
  ].some(binding => {
    const model = models.find(model => model.id === binding.id)
    return Boolean(model?.spec_hash && model.spec_hash !== binding.hash)
  })
  const hasValidationIssue = Boolean(outputContractError(state) || externalContextContractError(state) || artifactCapabilityError(state))

  const saveDraft = useCallback(async () => {
    if (createRelease.isPending) return false
    setSaveFailed(false)
    const capturedState = state
    const result = validateAgentEditorState(capturedState)
    if (!result.valid) {
      setSection(result.issue.section)
      toast.error(result.issue.message)
      return false
    }

    try {
      const saved = await createRelease.mutateAsync({ expected_revision: baseRevision, project_id: projectId, agent_id: agent.id, version: 'draft', ...result.snapshot } as any)
      updateBaseline(capturedState, saved.agent_revision)
      setLoadedRelease(null, null)
      toast.success('Draft saved')
      return true
    } catch (error) {
      setSaveFailed(true)
      toast.error(error instanceof Error ? error.message : 'Failed to save Draft')
      return false
    }
  }, [agent.id, baseRevision, createRelease, projectId, setLoadedRelease, setSection, state, updateBaseline])

  const dirtyChangeRef = useRef(onDirtyChange)
  useEffect(() => { dirtyChangeRef.current = onDirtyChange }, [onDirtyChange])
  useEffect(() => { dirtyChangeRef.current?.(isDirty) }, [isDirty])
  useEffect(() => {
    onRegisterSaveAction?.(saveDraft)
    return () => onRegisterSaveAction?.(null)
  }, [onRegisterSaveAction, saveDraft])

  const status = createRelease.isPending ? 'Saving…'
    : saveFailed ? 'Save failed'
      : hasValidationIssue ? 'Fix Contracts'
        : isDirty ? 'Unsaved changes'
          : loadedReleaseVersion ? 'Ready to save as Draft' : modelUpdatesAvailable ? 'Model changes available' : 'Saved'

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-background">
      <div className="flex min-h-control shrink-0 items-center gap-ui-sm border-b border-border bg-background/20 px-ui-md py-ui-sm">
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-chrome-meta text-muted-foreground">{loadedReleaseVersion ? <>Draft based on <span className="text-primary-light">{loadedReleaseVersion}</span></> : 'Current Draft'}</p>
          <p role="status" className={cn('mt-ui-hairline font-mono text-chrome-meta', saveFailed || hasValidationIssue ? 'text-error' : isDirty ? 'text-warning' : 'text-muted-foreground')}>{status}</p>
        </div>
        <Button size="sm" variant="ghost" className="w-control-sm p-0 text-muted-foreground" onClick={() => { setSaveFailed(false); resetToBaseline() }} disabled={!isDirty || createRelease.isPending} title="Reset to saved Draft" aria-label="Reset Draft"><RotateCcw className="h-icon w-icon" /></Button>
        <Button size="sm" onClick={() => void saveDraft()} loading={createRelease.isPending} disabled={!isDirty && !loadedReleaseVersion && !modelUpdatesAvailable} title={modelUpdatesAvailable ? 'Save to adopt current Model configuration and prices in this Draft' : undefined} aria-invalid={hasValidationIssue || undefined}><Save className="h-icon-sm w-icon-sm" />Save</Button>
      </div>
      <AgentEditorNavigation value={section} onChange={setSection} />
      <div className="scrollbar-thin min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-contain">
        {section === 'details' ? <AgentOverviewSettings onOpenBehavior={() => setSection('behavior')} /> : null}
        {section === 'behavior' ? <AgentBehaviorSettings /> : null}
        {section === 'runtime' ? <AgentRuntimeSettings projectId={projectId} /> : null}
        {section === 'output' ? <AgentOutputSettings /> : null}
        {section === 'external-context' ? <AgentExternalContextSettings /> : null}
        {section === 'artifacts' ? <AgentArtifactSettings projectId={projectId} /> : null}
        {section === 'model' ? <AgentModelSettings projectId={projectId} /> : null}
        {section === 'knowledge' ? <AgentKnowledgeSettings projectId={projectId} agentId={agentId} /> : null}
        {section === 'skills' ? <div className="p-ui-md"><AgentSkillsSection projectId={projectId} /></div> : null}
        {section === 'tools' ? <AgentToolsSettings projectId={projectId} agentId={agentId} /> : null}
      </div>
    </div>
  )
}
