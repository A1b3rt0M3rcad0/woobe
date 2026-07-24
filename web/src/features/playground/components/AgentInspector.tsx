import { useState } from 'react'
import { Edit3, Rocket, Bot, FileJson, Cpu, BookOpen, Wrench, Save, RotateCcw, Lock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { InspectorTabs } from './InspectorTabs'
import { AgentSettingsTab } from './AgentSettingsTab'
import { ModelSettingsTab } from './ModelSettingsTab'
import { KnowledgeTab } from './KnowledgeTab'
import { ToolsTab } from './ToolsTab'
import { OutputSettingsTab } from './OutputSettingsTab'
import { ReleaseTab } from './ReleaseTab'
import { ReleaseDetailsView } from './ReleaseDetailsView'
import { useAgentEditor } from '../AgentEditorContext'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useCreateRelease, useUpdateAgent } from '@/features/agents/hooks'
import { toast } from 'sonner'
import type { Agent, AgentRelease, RuntimeEnvironment } from '@/features/agents/types'

interface AgentInspectorProps {
  agent: Agent
  projectId: string
  agentId: string
  activeTab: string
  environment: RuntimeEnvironment
  environmentRelease: AgentRelease | null
  environmentReleaseLoading?: boolean
  onTabChange: (tab: string) => void
  onCollapse?: () => void
}

const editorSubTabs = [
  { id: 'agent', label: 'Agent', icon: <Bot className="h-3 w-3" /> },
  { id: 'output', label: 'Output', icon: <FileJson className="h-3 w-3" /> },
  { id: 'model', label: 'Model', icon: <Cpu className="h-3 w-3" /> },
  { id: 'knowledge', label: 'Knowledge', icon: <BookOpen className="h-3 w-3" /> },
  { id: 'tools', label: 'Tools', icon: <Wrench className="h-3 w-3" /> },
]

function titleCaseEnvironment(environment: RuntimeEnvironment) {
  return environment.charAt(0).toUpperCase() + environment.slice(1)
}

function EditorHeader() {
  const { loadedReleaseVersion, isDirty } = useAgentEditor()
  return (
    <div className="flex items-center justify-between px-3 py-2 border-b border-border/90 bg-background/25 shrink-0">
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-[10px] text-muted font-medium whitespace-nowrap">
          {loadedReleaseVersion ? (
            <>Draft based on: <span className="text-primary-light">{loadedReleaseVersion}</span></>
          ) : (
            'Current Draft'
          )}
        </span>
        {isDirty && (
          <Badge variant="warning" className="text-[9px] px-1 py-0">Unsaved changes</Badge>
        )}
      </div>
    </div>
  )
}

function EditorActions({ agent, projectId }: { agent: Agent; projectId: string }) {
  const { toSnapshot, updateBaseline, resetToBaseline } = useAgentEditor()
  const updateAgent = useUpdateAgent(agent.id)
  const createRelease = useCreateRelease(agent.id)

  const handleSaveDraft = async () => {
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
        session_mode: canonicalSnapshot.session_mode,
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
        toast.warning('Draft saved, but the Agent summary could not be synchronized')
        return
      }

      updateBaseline()
      toast.success('Draft saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save draft')
    }
  }

  const handleReset = () => {
    resetToBaseline()
  }

  return (
    <div className="flex items-center gap-1.5 px-3 py-2 border-b border-border/90 bg-background/20 shrink-0">
      <Button
        size="sm"
        variant="outline"
        className="text-[11px] flex-1 border-primary/30 bg-primary/10 text-primary-light hover:bg-primary/15 hover:text-white"
        onClick={handleSaveDraft}
        loading={updateAgent.isPending || createRelease.isPending}
      >
        <Save className="mr-1 h-3 w-3" />
        Save Draft
      </Button>
      <Button
        size="sm"
        variant="ghost"
        className="text-[11px] border border-border/80 bg-background/45 hover:bg-surface/70"
        onClick={handleReset}
        title="Reset editor to last saved draft state"
      >
        <RotateCcw className="h-3 w-3" />
      </Button>
    </div>
  )
}

function EditorTabContent({ agent, projectId, agentId }: { agent: Agent; projectId: string; agentId: string }) {
  const [editorTab, setEditorTab] = useState('agent')

  return (
    <div className="flex flex-col h-full">
      <EditorHeader />
      <EditorActions agent={agent} projectId={projectId} />
      <div className="flex gap-1 border-b border-border/90 bg-surface/70 p-1.5 shrink-0">
        {editorSubTabs.map((sub) => (
          <button
            key={sub.id}
            onClick={() => setEditorTab(sub.id)}
            className={cn(
              'flex-1 flex items-center justify-center gap-1 rounded-lg border px-1.5 py-2 text-[11px] font-medium transition-colors',
              editorTab === sub.id
                ? 'border-primary/35 bg-primary/10 text-primary-light shadow-sm shadow-primary/5'
                : 'border-transparent text-muted hover:border-border/80 hover:bg-background/60 hover:text-white',
            )}
          >
            {sub.icon}
            {sub.label}
          </button>
        ))}
      </div>
      <ScrollArea className="flex-1 min-h-0">
        {editorTab === 'agent' && <AgentSettingsTab />}
        {editorTab === 'output' && <OutputSettingsTab />}
        {editorTab === 'model' && <ModelSettingsTab projectId={projectId} />}
        {editorTab === 'knowledge' && <KnowledgeTab projectId={projectId} agentId={agentId} />}
        {editorTab === 'tools' && <ToolsTab projectId={projectId} agentId={agentId} />}
      </ScrollArea>
    </div>
  )
}

function EnvironmentSnapshotContent({
  environment,
  release,
  loading,
}: {
  environment: Exclude<RuntimeEnvironment, 'draft'>
  release: AgentRelease | null
  loading: boolean
}) {
  const label = titleCaseEnvironment(environment)
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border/90 bg-background/25 px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <Lock className="h-3.5 w-3.5 text-muted" />
          <span className="text-[10px] font-medium text-muted">Viewing immutable {label}</span>
        </div>
        {release ? <Badge variant={environment === 'production' ? 'success' : 'secondary'}>{release.version}</Badge> : null}
      </div>
      <ScrollArea className="min-h-0 flex-1">
        {loading && !release ? (
          <div className="p-4 text-xs text-muted">Loading {label} snapshot…</div>
        ) : release ? (
          <div className="p-4"><ReleaseDetailsView release={release} /></div>
        ) : (
          <div className="p-4">
            <div className="rounded-xl border border-dashed border-border p-4 text-xs leading-5 text-muted">
              {environment === 'staging' ? 'No Agent Staging snapshot has been created yet.' : 'No Agent Production release is active.'}
            </div>
          </div>
        )}
      </ScrollArea>
    </div>
  )
}

export function AgentInspector({
  agent,
  projectId,
  agentId,
  activeTab,
  environment,
  environmentRelease,
  environmentReleaseLoading = false,
  onTabChange,
}: AgentInspectorProps) {
  const resolvedActiveTab = activeTab === 'runtime' ? 'editor' : activeTab
  const editorContent = environment === 'draft'
    ? <EditorTabContent agent={agent} projectId={projectId} agentId={agentId} />
    : <EnvironmentSnapshotContent environment={environment} release={environmentRelease} loading={environmentReleaseLoading} />
  const tabs = [
    {
      id: 'editor',
      label: environment === 'draft' ? 'Editor' : 'Snapshot',
      icon: environment === 'draft' ? <Edit3 className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />,
      content: editorContent,
    },
    {
      id: 'versions',
      label: 'Versions',
      icon: <Rocket className="h-3.5 w-3.5" />,
      content: <div className="versions-tab-compact h-full"><ReleaseTab agentId={agentId} projectId={projectId} /></div>,
    },
  ]

  return (
    <div className="w-[400px] shrink-0 border-l border-border/90 bg-surface/75 shadow-sm shadow-black/5 flex flex-col">
      <div className="flex items-center justify-between px-3 py-3 border-b border-border/90 bg-background/25 shrink-0">
        <p className="text-xs font-semibold text-muted uppercase tracking-wider">Inspector</p>
      </div>
      <div className="flex-1 min-h-0 overflow-hidden">
        <InspectorTabs tabs={tabs} defaultTab={resolvedActiveTab} onTabChange={onTabChange} />
      </div>
    </div>
  )
}
