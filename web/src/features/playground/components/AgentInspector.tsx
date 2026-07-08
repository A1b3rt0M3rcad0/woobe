import { useState } from 'react'
import { Edit3, Rocket, Bot, FileJson, Cpu, BookOpen, Wrench, Save, RotateCcw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { InspectorTabs } from './InspectorTabs'
import { AgentSettingsTab } from './AgentSettingsTab'
import { ModelSettingsTab } from './ModelSettingsTab'
import { KnowledgeTab } from './KnowledgeTab'
import { ToolsTab } from './ToolsTab'
import { OutputSettingsTab } from './OutputSettingsTab'
import { ReleaseTab } from './ReleaseTab'
import { useAgentEditor } from '../AgentEditorContext'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { useCreateRelease, useUpdateAgent } from '@/features/agents/hooks'
import { toast } from 'sonner'
import type { Agent } from '@/features/agents/types'

interface AgentInspectorProps {
  agent: Agent
  projectId: string
  agentId: string
  activeTab: string
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
  const { state, toSnapshot, updateBaseline, resetToBaseline } = useAgentEditor()
  const updateAgent = useUpdateAgent(agent.id)
  const createRelease = useCreateRelease(agent.id)

  const handleSaveDraft = async () => {
    try {
      const snapshot = toSnapshot()
      await createRelease.mutateAsync({
        project_id: projectId,
        agent_id: agent.id,
        version: 'draft',
        ...snapshot,
      } as any)

      const rf = {
        enabled: state.responseFormat.enabled,
        type: state.responseFormat.type,
        strict: state.responseFormat.strict,
        schema: state.responseFormat.schema,
        repair_attempts: state.responseFormat.repair_attempts,
      }
      const payload: Record<string, unknown> = {
        name: state.name,
        description: state.description,
        system_prompt: state.systemPrompt,
        provider_model_id: state.providerModelId,
        provider: state.provider,
        model: state.model,
        provider_credential_id: state.providerCredentialId,
        fallback_provider_model_id: state.fallbackProviderModelId || null,
        fallback_provider: state.fallbackProvider || null,
        fallback_model: state.fallbackModel || null,
        fallback_credential_id: state.fallbackProviderCredentialId || null,
        temperature: state.temperature,
        max_output_tokens: state.maxOutputTokens,
        settings: {
          ...(agent.settings || {}),
          response_format: rf,
          base_url: state.baseUrl,
          knowledge_version_id: state.knowledgeVersionId,
          runtime_config: snapshot.runtime_config,
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

export function AgentInspector({ agent, projectId, agentId, activeTab, onTabChange }: AgentInspectorProps) {
  const resolvedActiveTab = activeTab === 'runtime' ? 'editor' : activeTab
  const tabs = [
    {
      id: 'editor',
      label: 'Editor',
      icon: <Edit3 className="h-3.5 w-3.5" />,
      content: <EditorTabContent agent={agent} projectId={projectId} agentId={agentId} />,
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
