import { useCallback, useEffect, useRef, useState } from 'react'
import { RotateCcw, Save } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { AgentSkillsSection } from '@/features/skills/AgentSkillsSection'
import { cn } from '@/lib/utils'
import { outputContractError, validateAgentEditorState } from '../editorValidation'
import { useCreateRelease } from '../hooks'
import type { Agent } from '../types'
import { AgentEditorNavigation, useAgentEditorSection } from './AgentEditorNavigation'
import { AgentOverviewSettings } from './AgentOverviewSettings'
import { AgentBehaviorSettings } from './AgentBehaviorSettings'
import { AgentRuntimeSettings } from './AgentRuntimeSettings'
import { AgentModelSettings } from './AgentModelSettings'
import { AgentKnowledgeSettings } from './AgentKnowledgeSettings'
import { AgentToolsSettings } from './AgentToolsSettings'
import { AgentOutputSettings } from './AgentOutputSettings'

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
  const { state, loadedReleaseVersion, setLoadedRelease, isDirty, updateBaseline, resetToBaseline } = useAgentEditor()
  const createRelease = useCreateRelease(agent.id)
  const hasValidationIssue = Boolean(outputContractError(state))

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
      await createRelease.mutateAsync({ project_id: projectId, agent_id: agent.id, version: 'draft', ...result.snapshot } as any)
      updateBaseline(capturedState)
      setLoadedRelease(null, null)
      toast.success('Draft saved')
      return true
    } catch (error) {
      setSaveFailed(true)
      toast.error(error instanceof Error ? error.message : 'Failed to save Draft')
      return false
    }
  }, [agent.id, createRelease, projectId, setLoadedRelease, setSection, state, updateBaseline])

  const dirtyChangeRef = useRef(onDirtyChange)
  useEffect(() => { dirtyChangeRef.current = onDirtyChange }, [onDirtyChange])
  useEffect(() => { dirtyChangeRef.current?.(isDirty) }, [isDirty])
  useEffect(() => {
    onRegisterSaveAction?.(saveDraft)
    return () => onRegisterSaveAction?.(null)
  }, [onRegisterSaveAction, saveDraft])

  const status = createRelease.isPending ? 'Saving…'
    : saveFailed ? 'Save failed'
      : hasValidationIssue ? 'Fix Output contract'
        : isDirty ? 'Unsaved changes'
          : loadedReleaseVersion ? 'Ready to save as Draft' : 'Saved'

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background">
      <div className="flex min-h-[38px] shrink-0 items-center gap-2 border-b border-border bg-background/20 px-3 py-2">
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-[8px] text-muted-foreground">{loadedReleaseVersion ? <>Draft based on <span className="text-primary-light">{loadedReleaseVersion}</span></> : 'Current Draft'}</p>
          <p role="status" className={cn('mt-0.5 font-mono text-[8px]', saveFailed || hasValidationIssue ? 'text-red-300' : isDirty ? 'text-amber-300/90' : 'text-muted-foreground')}>{status}</p>
        </div>
        <Button size="sm" variant="ghost" className="h-7 w-7 p-0 text-muted-foreground" onClick={() => { setSaveFailed(false); resetToBaseline() }} disabled={!isDirty || createRelease.isPending} title="Reset to saved Draft" aria-label="Reset Draft"><RotateCcw className="h-3.5 w-3.5" /></Button>
        <Button size="sm" onClick={() => void saveDraft()} loading={createRelease.isPending} disabled={!isDirty && !loadedReleaseVersion} aria-invalid={hasValidationIssue || undefined}><Save className="h-3 w-3" />Save</Button>
      </div>
      <AgentEditorNavigation value={section} onChange={setSection} />
      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain">
        {section === 'details' ? <AgentOverviewSettings onOpenBehavior={() => setSection('behavior')} /> : null}
        {section === 'behavior' ? <AgentBehaviorSettings /> : null}
        {section === 'runtime' ? <AgentRuntimeSettings projectId={projectId} /> : null}
        {section === 'output' ? <AgentOutputSettings /> : null}
        {section === 'model' ? <AgentModelSettings projectId={projectId} /> : null}
        {section === 'knowledge' ? <AgentKnowledgeSettings projectId={projectId} agentId={agentId} /> : null}
        {section === 'skills' ? <div className="p-3"><AgentSkillsSection projectId={projectId} /></div> : null}
        {section === 'tools' ? <AgentToolsSettings projectId={projectId} agentId={agentId} /> : null}
      </div>
    </div>
  )
}
