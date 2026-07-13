import { useCallback, useEffect, useRef, useState } from 'react'
import { Bot, BookOpen, Cpu, FileJson, RotateCcw, Save, Wrench } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useCreateRelease, useUpdateAgent } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import { cn } from '@/lib/utils'
import { useAgentEditor } from '../AgentEditorContext'
import { AgentSettingsTab } from './AgentSettingsTab'
import { KnowledgeTab } from './KnowledgeTab'
import { ModelSettingsTab } from './ModelSettingsTab'
import { OutputSettingsTab } from './OutputSettingsTab'
import { ToolsTab } from './ToolsTab'

type EditorSection = 'agent' | 'output' | 'model' | 'knowledge' | 'tools'

interface AgentEditorWorkspaceProps {
  agent: Agent
  projectId: string
  agentId: string
  compact?: boolean
  onDirtyChange?: (dirty: boolean) => void
  onRegisterSaveAction?: (action: (() => Promise<boolean>) | null) => void
  onSaved?: () => void
}

const editorTabs = [
  { id: 'agent' as const, label: 'Agent', icon: Bot },
  { id: 'output' as const, label: 'Output', icon: FileJson },
  { id: 'model' as const, label: 'Model', icon: Cpu },
  { id: 'knowledge' as const, label: 'Knowledge', icon: BookOpen },
  { id: 'tools' as const, label: 'Tools', icon: Wrench },
]

export function AgentEditorWorkspace({
  agent,
  projectId,
  agentId,
  compact = false,
  onDirtyChange,
  onRegisterSaveAction,
  onSaved,
}: AgentEditorWorkspaceProps) {
  const [activeSection, setActiveSection] = useState<EditorSection>('agent')
  const { loadedReleaseVersion, isDirty, toSnapshot, updateBaseline, resetToBaseline } = useAgentEditor()
  const updateAgent = useUpdateAgent(agent.id)
  const createRelease = useCreateRelease(agent.id)
  const dirtyChangeRef = useRef(onDirtyChange)

  useEffect(() => {
    dirtyChangeRef.current = onDirtyChange
  }, [onDirtyChange])

  const saveDraft = useCallback(async (): Promise<boolean> => {
    try {
      const snapshot = toSnapshot()
      const rawResponseFormat = snapshot.response_format
      const responseFormat = rawResponseFormat && typeof rawResponseFormat === 'object' && !Array.isArray(rawResponseFormat)
        ? rawResponseFormat as Record<string, unknown>
        : {}
      const jsonEnabled = responseFormat.enabled === true && responseFormat.type === 'json'
      const currentSchema = responseFormat.schema
      const hasSchema = typeof currentSchema === 'string'
        ? currentSchema.trim().length > 0
        : Boolean(currentSchema && typeof currentSchema === 'object')
      const schema = jsonEnabled && !hasSchema
        ? { message: 'string', confidence: 'float' }
        : currentSchema
      const canonicalSnapshot: Record<string, unknown> = {
        ...snapshot,
        response_format: {
          ...responseFormat,
          strict: true,
          schema,
        },
        output_schema: schema,
      }

      await createRelease.mutateAsync({
        project_id: projectId,
        agent_id: agent.id,
        version: 'draft',
        ...canonicalSnapshot,
      } as any)

      const payload: Record<string, unknown> = {
        name: canonicalSnapshot.name,
        description: canonicalSnapshot.description,
        system_prompt: canonicalSnapshot.system_prompt,
        provider_model_id: canonicalSnapshot.provider_model_id,
        provider: canonicalSnapshot.provider,
        model: canonicalSnapshot.model,
        provider_credential_id: canonicalSnapshot.provider_credential_id,
        fallback_provider_model_id: canonicalSnapshot.fallback_provider_model_id ?? null,
        fallback_provider: canonicalSnapshot.fallback_provider ?? null,
        fallback_model: canonicalSnapshot.fallback_model ?? null,
        fallback_credential_id: canonicalSnapshot.fallback_credential_id ?? null,
        temperature: canonicalSnapshot.temperature,
        max_output_tokens: canonicalSnapshot.max_output_tokens,
        settings: {
          ...(agent.settings || {}),
          response_format: canonicalSnapshot.response_format,
          base_url: canonicalSnapshot.base_url,
          knowledge_version_id: canonicalSnapshot.knowledge_version_id,
          runtime_config: canonicalSnapshot.runtime_config,
        },
      }

      try {
        await updateAgent.mutateAsync(payload as any)
      } catch {
        updateBaseline()
        onSaved?.()
        toast.warning('Draft saved, but the Agent summary could not be synchronized')
        return true
      }

      updateBaseline()
      onSaved?.()
      toast.success('Draft saved')
      return true
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save draft')
      return false
    }
  }, [agent, createRelease, onSaved, projectId, toSnapshot, updateAgent, updateBaseline])

  useEffect(() => dirtyChangeRef.current?.(isDirty), [isDirty])
  useEffect(() => {
    onRegisterSaveAction?.(saveDraft)
    return () => onRegisterSaveAction?.(null)
  }, [onRegisterSaveAction, saveDraft])

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between gap-3 border-b border-border/90 bg-background/25 px-3 py-2.5">
        <div className="min-w-0">
          <p className="text-[10px] font-medium text-muted">
            {loadedReleaseVersion ? (
              <>Draft based on: <span className="font-mono text-primary-light">{loadedReleaseVersion}</span></>
            ) : 'Current Draft'}
          </p>
        </div>
        {isDirty && <Badge variant="warning" className="shrink-0 text-[9px]">Unsaved changes</Badge>}
      </div>

      <div className="flex items-center gap-2 border-b border-border/90 bg-background/20 px-3 py-2">
        <Button
          size="sm"
          variant="outline"
          className="flex-1 border-primary/30 bg-primary/10 text-[11px] text-primary-light hover:bg-primary/15 hover:text-white"
          onClick={() => void saveDraft()}
          loading={updateAgent.isPending || createRelease.isPending}
          disabled={!isDirty && !loadedReleaseVersion}
        >
          <Save className="mr-1 h-3 w-3" />
          Save Draft
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="border border-border/80 bg-background/45 text-[11px] hover:bg-surface/70"
          onClick={resetToBaseline}
          disabled={!isDirty}
          title="Reset to the last saved Draft"
        >
          <RotateCcw className="h-3 w-3" />
        </Button>
      </div>

      <div className={cn('flex gap-1 overflow-x-auto border-b border-border/90 bg-surface/70 p-1.5', compact && 'px-2')}>
        {editorTabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setActiveSection(id)}
            className={cn(
              'flex min-w-fit flex-1 items-center justify-center gap-1 rounded-lg border px-2 py-2 text-[10px] font-medium transition-colors',
              activeSection === id
                ? 'border-primary/35 bg-primary/10 text-primary-light shadow-sm shadow-primary/5'
                : 'border-transparent text-muted hover:border-border/80 hover:bg-background/60 hover:text-white',
            )}
          >
            <Icon className="h-3 w-3" />
            {label}
          </button>
        ))}
      </div>

      <ScrollArea className="min-h-0 flex-1">
        {activeSection === 'agent' && <AgentSettingsTab />}
        {activeSection === 'output' && <OutputSettingsTab />}
        {activeSection === 'model' && <ModelSettingsTab projectId={projectId} />}
        {activeSection === 'knowledge' && <KnowledgeTab projectId={projectId} agentId={agentId} />}
        {activeSection === 'tools' && <ToolsTab projectId={projectId} agentId={agentId} />}
      </ScrollArea>
    </div>
  )
}
