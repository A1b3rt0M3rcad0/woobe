import { useCallback, useEffect, useRef, useState } from 'react'
import { RotateCcw, Save } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { useCreateRelease, useUpdateAgent } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { AgentEditorNavigation, useAgentEditorSection } from '@/features/agents/components/AgentEditorNavigation'
import { AgentSkillsSection } from '@/features/skills/AgentSkillsSection'
import { NetworkAgentFields } from './NetworkAgentFields'
import { NetworkAgentKnowledge } from './NetworkAgentKnowledge'
import { NetworkAgentModel } from './NetworkAgentModel'
import { isNetworkOutputValid, NetworkAgentOutput } from './NetworkAgentOutput'
import { NetworkAgentTools } from './NetworkAgentTools'

interface Props { agent: Agent; projectId: string; agentId: string; onDirtyChange?: (dirty: boolean) => void; onRegisterSaveAction?: (action: (() => Promise<boolean>) | null) => void }
function record(value: unknown): Record<string, unknown> { return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {} }

export function NetworkAgentEditor({ agent, projectId, agentId, onDirtyChange, onRegisterSaveAction }: Props) {
  const [section, setSection] = useAgentEditorSection()
  const [outputValid, setOutputValid] = useState(true)
  const { loadedReleaseVersion, isDirty, toSnapshot, updateBaseline, resetToBaseline } = useAgentEditor()
  const updateAgent = useUpdateAgent(agent.id)
  const createRelease = useCreateRelease(agent.id)
  const dirtyRef = useRef(onDirtyChange)
  useEffect(() => { dirtyRef.current = onDirtyChange }, [onDirtyChange])

  const saveDraft = useCallback(async () => {
    const snapshot = toSnapshot()
    const responseFormat = record(snapshot.response_format)
    if (responseFormat.enabled === true && responseFormat.type === 'json' && !isNetworkOutputValid(responseFormat.schema)) { setSection('output'); setOutputValid(false); toast.error('Fix the invalid Output contract before saving the Draft'); return false }
    try {
      await createRelease.mutateAsync({ project_id: projectId, agent_id: agent.id, version: 'draft', ...snapshot } as any)
      try {
        await updateAgent.mutateAsync({ name: snapshot.name, description: snapshot.description, system_prompt: snapshot.system_prompt, session_mode: snapshot.session_mode, provider_model_id: snapshot.provider_model_id, provider: snapshot.provider, model: snapshot.model, provider_credential_id: snapshot.provider_credential_id, fallback_provider_model_id: snapshot.fallback_provider_model_id ?? null, fallback_provider: snapshot.fallback_provider ?? null, fallback_model: snapshot.fallback_model ?? null, fallback_credential_id: snapshot.fallback_credential_id ?? null, temperature: snapshot.temperature, max_output_tokens: snapshot.max_output_tokens, settings: { ...(agent.settings || {}), response_format: snapshot.response_format, base_url: snapshot.base_url, knowledge_version_id: snapshot.knowledge_version_id, runtime_config: snapshot.runtime_config } } as any)
      } catch { updateBaseline(); toast.warning('Draft saved, but the Agent summary could not be synchronized'); return true }
      updateBaseline(); toast.success('Draft saved'); return true
    } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to save Draft'); return false }
  }, [agent, createRelease, projectId, toSnapshot, updateAgent, updateBaseline])

  useEffect(() => dirtyRef.current?.(isDirty), [isDirty])
  useEffect(() => { onRegisterSaveAction?.(saveDraft); return () => onRegisterSaveAction?.(null) }, [onRegisterSaveAction, saveDraft])

  return <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background">
    <div className="flex shrink-0 items-center gap-2 border-b border-border/80 bg-background/25 px-3 py-2"><p className="min-w-0 flex-1 truncate text-[10px] text-muted">{loadedReleaseVersion ? <>Draft based on <span className="font-mono text-primary-light">{loadedReleaseVersion}</span></> : 'Current Draft'}</p>{isDirty ? <Badge variant="warning" className="px-1.5 py-0 text-[8px]">Unsaved</Badge> : null}<Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={resetToBaseline} disabled={!isDirty} title="Reset to saved Draft"><RotateCcw className="h-3 w-3" /></Button><Button size="sm" className="h-7 px-2 text-[10px]" onClick={() => void saveDraft()} loading={updateAgent.isPending || createRelease.isPending} disabled={!outputValid || (!isDirty && !loadedReleaseVersion)}><Save className="mr-1 h-3 w-3" />Save</Button></div>
    <AgentEditorNavigation value={section} onChange={setSection} />
    <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain">{section === 'agent' ? <NetworkAgentFields /> : null}{section === 'output' ? <NetworkAgentOutput onValidity={setOutputValid} /> : null}{section === 'model' ? <NetworkAgentModel projectId={projectId} /> : null}{section === 'knowledge' ? <NetworkAgentKnowledge projectId={projectId} agentId={agentId} /> : null}{section === 'skills' ? <div className="p-4"><AgentSkillsSection projectId={projectId} /></div> : null}{section === 'tools' ? <NetworkAgentTools projectId={projectId} agentId={agentId} /> : null}</div>
  </div>
}
