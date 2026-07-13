import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { BookOpen, Bot, Cpu, ExternalLink, FileJson, RotateCcw, Save, Wrench } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { useCreateRelease, useKnowledgeVersions, useUpdateAgent } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import { useProviderModels } from '@/features/provider-models/hooks'
import { useTools } from '@/features/tools/hooks'
import type { Tool } from '@/features/tools/types'
import { toolPermissionsFromTools, useAgentEditor } from '@/features/playground/AgentEditorContext'
import { orgProjectPath } from '@/lib/constants/routes'
import { cn } from '@/lib/utils'

type EditorSection = 'agent' | 'output' | 'model' | 'knowledge' | 'tools'

interface NetworkAgentEditorProps {
  agent: Agent
  projectId: string
  agentId: string
  onDirtyChange?: (dirty: boolean) => void
  onRegisterSaveAction?: (action: (() => Promise<boolean>) | null) => void
}

const editorTabs = [
  { id: 'agent' as const, label: 'Agent', icon: Bot },
  { id: 'output' as const, label: 'Output', icon: FileJson },
  { id: 'model' as const, label: 'Model', icon: Cpu },
  { id: 'knowledge' as const, label: 'Knowledge', icon: BookOpen },
  { id: 'tools' as const, label: 'Tools', icon: Wrench },
]

const DEFAULT_SCHEMA = `{
  "message": "string",
  "confidence": "float"
}`

function schemaToString(value: unknown) {
  if (typeof value === 'string') return value
  if (value && typeof value === 'object') return JSON.stringify(value, null, 2)
  return DEFAULT_SCHEMA
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section className="rounded-lg border border-border/80 bg-background/35 p-3"><p className="mb-2.5 text-[10px] font-semibold uppercase tracking-wider text-muted">{title}</p>{children}</section>
}

function AgentFields() {
  const { state, setField } = useAgentEditor()
  return <div className="space-y-3"><Section title="Agent details"><div className="grid gap-3 min-[620px]:grid-cols-2"><label className="text-[10px] font-medium text-muted">Name<Input className="mt-1 h-9 text-xs" value={state.name} onChange={(event) => setField('name', event.target.value)} /></label><label className="text-[10px] font-medium text-muted">Description<Input className="mt-1 h-9 text-xs" value={state.description} onChange={(event) => setField('description', event.target.value)} placeholder="Optional description" /></label></div></Section><Section title="System prompt"><Textarea value={state.systemPrompt} onChange={(event) => setField('systemPrompt', event.target.value)} className="min-h-[132px] resize-y font-mono text-xs leading-5" placeholder="System instructions..." /></Section></div>
}

function OutputFields() {
  const { state, setField } = useAgentEditor()
  const enabled = state.responseFormat.enabled
  const toggle = (next: boolean) => setField('responseFormat', { ...state.responseFormat, enabled: next, type: next ? 'json' : 'text', strict: true, schema: next && !state.responseFormat.schema ? DEFAULT_SCHEMA : state.responseFormat.schema })
  return <div className="space-y-3"><Section title="Response format"><div className="grid grid-cols-2 gap-2"><button type="button" onClick={() => toggle(false)} className={cn('rounded-lg border p-2.5 text-left', !enabled ? 'border-primary/35 bg-primary/10' : 'border-border bg-background/40')}><p className="text-[11px] font-medium text-white">Text</p><p className="mt-0.5 text-[9px] text-muted">Natural language</p></button><button type="button" onClick={() => toggle(true)} className={cn('rounded-lg border p-2.5 text-left', enabled ? 'border-primary/35 bg-primary/10' : 'border-border bg-background/40')}><p className="text-[11px] font-medium text-white">JSON</p><p className="mt-0.5 text-[9px] text-muted">Strict structured output</p></button></div></Section><Section title="Output contract"><Textarea disabled={!enabled} value={schemaToString(state.responseFormat.schema)} onChange={(event) => setField('responseFormat', { ...state.responseFormat, strict: true, schema: event.target.value })} className="min-h-[150px] resize-y font-mono text-[10px] leading-5" /><p className="mt-2 text-[9px] text-muted">Applied to isolated Chat and persisted in the Agent snapshot.</p></Section></div>
}

function ModelFields({ projectId }: { projectId: string }) {
  const navigate = useNavigate()
  const { organizationId } = useParams<{ organizationId?: string }>()
  const { data: models = [] } = useProviderModels(projectId)
  const { state, setField } = useAgentEditor()
  const active = models.filter((model) => model.status !== 'archived')
  const select = (id: string, fallback = false) => {
    const model = models.find((item) => item.id === id)
    if (fallback) {
      setField('fallbackProviderModelId', model?.id || null)
      setField('fallbackProviderCredentialId', model?.provider_credential_id || null)
      setField('fallbackProvider', model?.provider || '')
      setField('fallbackModel', model?.model || '')
      return
    }
    setField('providerModelId', model?.id || null)
    setField('providerCredentialId', model?.provider_credential_id || null)
    setField('provider', model?.provider || '')
    setField('model', model?.model || '')
  }
  return <div className="space-y-3"><Section title="Models"><div className="space-y-3"><label className="block text-[10px] font-medium text-muted">Primary model<select value={state.providerModelId || ''} onChange={(event) => select(event.target.value)} className="mt-1 h-9 w-full rounded-lg border border-border bg-background/70 px-2.5 text-xs text-white"><option value="">Select a model</option>{active.map((model) => <option key={model.id} value={model.id}>{model.name} · {model.model}</option>)}</select></label><label className="block text-[10px] font-medium text-muted">Fallback model<select value={state.fallbackProviderModelId || ''} onChange={(event) => select(event.target.value, true)} className="mt-1 h-9 w-full rounded-lg border border-border bg-background/70 px-2.5 text-xs text-white"><option value="">None</option>{active.map((model) => <option key={model.id} value={model.id}>{model.name} · {model.model}</option>)}</select></label><button type="button" onClick={() => navigate(orgProjectPath(organizationId, projectId, 'models'))} className="inline-flex items-center gap-1 text-[9px] font-medium text-primary-light hover:text-white">Manage models <ExternalLink className="h-3 w-3" /></button></div></Section><Section title="Generation"><div className="grid grid-cols-2 gap-3"><label className="text-[10px] font-medium text-muted">Temperature<Input type="number" min="0" max="2" step="0.1" className="mt-1 h-9 text-xs" value={state.temperature} onChange={(event) => setField('temperature', Number(event.target.value) || 0)} /></label><label className="text-[10px] font-medium text-muted">Max output tokens<Input type="number" min="1" className="mt-1 h-9 text-xs" value={state.maxOutputTokens} onChange={(event) => setField('maxOutputTokens', Number(event.target.value) || 1)} /></label></div></Section></div>
}

function KnowledgeFields({ projectId, agentId }: { projectId: string; agentId: string }) {
  const navigate = useNavigate()
  const { organizationId } = useParams<{ organizationId?: string }>()
  const { data: versions = [] } = useKnowledgeVersions(agentId)
  const { state, setField } = useAgentEditor()
  const rag = (state.runtimeConfig.rag || {}) as Record<string, unknown>
  const setRag = (key: string, value: unknown) => setField('runtimeConfig', { ...state.runtimeConfig, rag: { ...rag, [key]: value } })
  return <div className="space-y-3"><Section title="Knowledge version"><select value={state.knowledgeVersionId || ''} onChange={(event) => setField('knowledgeVersionId', event.target.value || null)} className="h-9 w-full rounded-lg border border-border bg-background/70 px-2.5 text-xs text-white"><option value="">No knowledge</option>{versions.map((version) => <option key={version.id} value={version.id}>Knowledge {version.version} · {version.status}</option>)}</select><button type="button" onClick={() => navigate(orgProjectPath(organizationId, projectId, 'knowledge'))} className="mt-2 inline-flex items-center gap-1 text-[9px] font-medium text-primary-light hover:text-white">Manage knowledge <ExternalLink className="h-3 w-3" /></button></Section><Section title="Runtime retrieval"><div className="grid grid-cols-2 gap-3"><label className="text-[10px] font-medium text-muted">Candidate K<Input type="number" min="1" className="mt-1 h-9 text-xs" value={typeof rag.candidate_k === 'number' ? rag.candidate_k : 20} onChange={(event) => setRag('candidate_k', Number(event.target.value) || 20)} /></label><label className="text-[10px] font-medium text-muted">Top K<Input type="number" min="1" className="mt-1 h-9 text-xs" value={typeof rag.top_k === 'number' ? rag.top_k : 5} onChange={(event) => setRag('top_k', Number(event.target.value) || 5)} /></label><label className="text-[10px] font-medium text-muted">Query mode<select value={rag.query_mode === 'current_message' ? 'current_message' : 'conversation_context'} onChange={(event) => setRag('query_mode', event.target.value)} className="mt-1 h-9 w-full rounded-lg border border-border bg-background/70 px-2 text-xs text-white"><option value="conversation_context">Conversation context</option><option value="current_message">Current message</option></select></label><label className="text-[10px] font-medium text-muted">Grounding<select value={rag.grounding_policy === 'required' ? 'required' : 'optional'} onChange={(event) => setRag('grounding_policy', event.target.value)} className="mt-1 h-9 w-full rounded-lg border border-border bg-background/70 px-2 text-xs text-white"><option value="optional">Optional</option><option value="required">Required</option></select></label></div></Section></div>
}

function ToolsFields({ projectId }: { projectId: string }) {
  const navigate = useNavigate()
  const { organizationId } = useParams<{ organizationId?: string }>()
  const { data: tools = [], isLoading } = useTools(projectId)
  const { state, setState } = useAgentEditor()
  const selected = new Set(state.toolIds)
  const toggle = (tool: Tool) => {
    if (selected.has(tool.id)) {
      const permissions = { ...state.toolPermissions }
      delete permissions[tool.id]
      setState({ ...state, toolIds: state.toolIds.filter((id) => id !== tool.id), toolPermissions: permissions })
      return
    }
    setState({ ...state, toolIds: [...state.toolIds, tool.id], toolPermissions: { ...state.toolPermissions, [tool.id]: toolPermissionsFromTools([tool])[tool.id] || {} } })
  }
  if (isLoading) return <p className="text-[10px] text-muted">Loading Tools…</p>
  return <div className="space-y-2"><div className="flex items-center justify-between"><p className="text-[9px] text-muted">{state.toolIds.length} selected</p><button type="button" onClick={() => navigate(orgProjectPath(organizationId, projectId, 'tools'))} className="inline-flex items-center gap-1 text-[9px] font-medium text-primary-light hover:text-white">Manage Tools <ExternalLink className="h-3 w-3" /></button></div>{tools.length === 0 ? <div className="rounded-lg border border-dashed border-border p-4 text-center text-[10px] text-muted">No Tools available.</div> : tools.map((tool) => <button key={tool.id} type="button" onClick={() => toggle(tool)} className={cn('flex w-full items-start gap-2.5 rounded-lg border p-2.5 text-left', selected.has(tool.id) ? 'border-primary/30 bg-primary/[0.045]' : 'border-border/75 bg-background/35')}><span className={cn('mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border text-[10px]', selected.has(tool.id) ? 'border-primary/45 bg-primary text-white' : 'border-border bg-background text-transparent')}>✓</span><span className="min-w-0 flex-1"><span className="flex items-center gap-2"><b className="truncate text-[11px] font-medium text-white">{tool.name}</b><Badge variant={tool.status === 'active' ? 'success' : 'secondary'} className="px-1.5 py-0 text-[8px]">{tool.status}</Badge></span><span className="mt-0.5 block line-clamp-2 text-[9px] leading-4 text-muted">{tool.description || 'No description'}</span></span></button>)}</div>
}

export function NetworkAgentEditor({ agent, projectId, agentId, onDirtyChange, onRegisterSaveAction }: NetworkAgentEditorProps) {
  const [activeSection, setActiveSection] = useState<EditorSection>('agent')
  const { loadedReleaseVersion, isDirty, toSnapshot, updateBaseline, resetToBaseline } = useAgentEditor()
  const updateAgent = useUpdateAgent(agent.id)
  const createRelease = useCreateRelease(agent.id)
  const dirtyRef = useRef(onDirtyChange)
  useEffect(() => { dirtyRef.current = onDirtyChange }, [onDirtyChange])

  const saveDraft = useCallback(async () => {
    try {
      const snapshot = toSnapshot()
      await createRelease.mutateAsync({ project_id: projectId, agent_id: agent.id, version: 'draft', ...snapshot } as any)
      try {
        await updateAgent.mutateAsync({ name: snapshot.name, description: snapshot.description, system_prompt: snapshot.system_prompt, provider_model_id: snapshot.provider_model_id, provider: snapshot.provider, model: snapshot.model, provider_credential_id: snapshot.provider_credential_id, fallback_provider_model_id: snapshot.fallback_provider_model_id ?? null, fallback_provider: snapshot.fallback_provider ?? null, fallback_model: snapshot.fallback_model ?? null, fallback_credential_id: snapshot.fallback_credential_id ?? null, temperature: snapshot.temperature, max_output_tokens: snapshot.max_output_tokens, settings: { ...(agent.settings || {}), response_format: snapshot.response_format, base_url: snapshot.base_url, knowledge_version_id: snapshot.knowledge_version_id, runtime_config: snapshot.runtime_config } } as any)
      } catch {
        updateBaseline()
        toast.warning('Draft saved, but the Agent summary could not be synchronized')
        return true
      }
      updateBaseline()
      toast.success('Draft saved')
      return true
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save Draft')
      return false
    }
  }, [agent, createRelease, projectId, toSnapshot, updateAgent, updateBaseline])

  useEffect(() => dirtyRef.current?.(isDirty), [isDirty])
  useEffect(() => { onRegisterSaveAction?.(saveDraft); return () => onRegisterSaveAction?.(null) }, [onRegisterSaveAction, saveDraft])

  return <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background"><div className="flex shrink-0 items-center gap-2 border-b border-border/80 bg-background/25 px-2.5 py-2"><p className="min-w-0 flex-1 truncate text-[9px] text-muted">{loadedReleaseVersion ? <>Draft based on <span className="font-mono text-primary-light">{loadedReleaseVersion}</span></> : 'Current Draft'}</p>{isDirty && <Badge variant="warning" className="px-1.5 py-0 text-[8px]">Unsaved</Badge>}<Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={resetToBaseline} disabled={!isDirty}><RotateCcw className="h-3 w-3" /></Button><Button size="sm" className="h-7 px-2 text-[9px]" onClick={() => void saveDraft()} loading={updateAgent.isPending || createRelease.isPending} disabled={!isDirty && !loadedReleaseVersion}><Save className="mr-1 h-3 w-3" />Save</Button></div><div className="scrollbar-thin flex shrink-0 gap-1 overflow-x-auto border-b border-border/80 bg-surface/60 p-1.5">{editorTabs.map(({ id, label, icon: Icon }) => <button key={id} type="button" onClick={() => setActiveSection(id)} className={cn('flex min-w-fit flex-1 items-center justify-center gap-1 rounded-md border px-2 py-1.5 text-[9px] font-medium', activeSection === id ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white')}><Icon className="h-3 w-3" />{label}</button>)}</div><div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain p-3">{activeSection === 'agent' && <AgentFields />}{activeSection === 'output' && <OutputFields />}{activeSection === 'model' && <ModelFields projectId={projectId} />}{activeSection === 'knowledge' && <KnowledgeFields projectId={projectId} agentId={agentId} />}{activeSection === 'tools' && <ToolsFields projectId={projectId} />}</div></div>
}
