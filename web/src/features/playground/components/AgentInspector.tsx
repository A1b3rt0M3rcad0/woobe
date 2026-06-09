import { useState } from 'react'
import { Edit3, Rocket, Bot, FileJson, Cpu, BookOpen, Save, RotateCcw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { InspectorTabs } from './InspectorTabs'
import { AgentSettingsTab } from './AgentSettingsTab'
import { ModelSettingsTab } from './ModelSettingsTab'
import { KnowledgeTab } from './KnowledgeTab'
import { OutputSettingsTab } from './OutputSettingsTab'
import { ReleaseTab } from './ReleaseTab'
import { PanelRightClose } from 'lucide-react'
import { useAgentEditor } from '../AgentEditorContext'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { useUpdateAgent } from '@/features/agents/hooks'
import { toast } from 'sonner'
import type { Agent } from '@/features/agents/types'

interface AgentInspectorProps {
  agent: Agent
  projectId: string
  agentId: string
  activeTab: string
  onTabChange: (tab: string) => void
  onCollapse: () => void
}

const editorSubTabs = [
  { id: 'agent', label: 'Agent', icon: <Bot className="h-3 w-3" /> },
  { id: 'output', label: 'Output', icon: <FileJson className="h-3 w-3" /> },
  { id: 'model', label: 'Model', icon: <Cpu className="h-3 w-3" /> },
  { id: 'knowledge', label: 'Knowledge', icon: <BookOpen className="h-3 w-3" /> },
]

function EditorHeader() {
  const { loadedReleaseVersion, isModifiedFromLoaded } = useAgentEditor()
  return (
    <div className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-surface/50 shrink-0">
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-[10px] text-muted font-medium whitespace-nowrap">
          {loadedReleaseVersion ? (
            <>Editing: <span className="text-blue-400">{loadedReleaseVersion}</span></>
          ) : (
            'Current Draft'
          )}
        </span>
        {isModifiedFromLoaded && (
          <Badge variant="warning" className="text-[9px] px-1 py-0">Unsaved changes</Badge>
        )}
      </div>
    </div>
  )
}

function EditorActions({ agentId }: { agentId: string }) {
  const { state } = useAgentEditor()
  const updateAgent = useUpdateAgent(agentId)

  const handleSaveDraft = async () => {
    try {
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
        provider: state.provider,
        model: state.model,
        provider_credential_id: state.providerCredentialId,
        temperature: state.temperature,
        max_output_tokens: state.maxOutputTokens,
        session_mode: state.sessionMode,
        status: state.status,
        settings: {
          response_format: rf,
          base_url: state.baseUrl,
        },
      }
      await updateAgent.mutateAsync(payload as any)
      toast.success('Draft saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save draft')
    }
  }

  const handleReset = () => {
    window.location.reload()
  }

  return (
    <div className="flex items-center gap-1.5 px-3 py-2 border-b border-border bg-surface/50 shrink-0">
      <Button
        size="sm"
        variant="outline"
        className="text-[11px] flex-1"
        onClick={handleSaveDraft}
        loading={updateAgent.isPending}
      >
        <Save className="mr-1 h-3 w-3" />
        Save Draft
      </Button>
      <Button
        size="sm"
        variant="ghost"
        className="text-[11px]"
        onClick={handleReset}
        title="Reset editor to last saved agent state"
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
      <EditorActions agentId={agentId} />
      <div className="flex border-b border-border bg-surface shrink-0">
        {editorSubTabs.map((sub) => (
          <button
            key={sub.id}
            onClick={() => setEditorTab(sub.id)}
            className={cn(
              'flex-1 flex items-center justify-center gap-1 px-2 py-2 text-xs font-medium transition-colors border-b-2 -mb-[1px]',
              editorTab === sub.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted hover:text-white',
            )}
          >
            {sub.icon}
            {sub.label}
          </button>
        ))}
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto">
        {editorTab === 'agent' && <AgentSettingsTab />}
        {editorTab === 'output' && <OutputSettingsTab />}
        {editorTab === 'model' && <ModelSettingsTab projectId={projectId} />}
        {editorTab === 'knowledge' && <KnowledgeTab projectId={projectId} agentId={agentId} />}
      </div>
    </div>
  )
}

export function AgentInspector({ agent, projectId, agentId, activeTab, onTabChange, onCollapse }: AgentInspectorProps) {
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
      content: <ReleaseTab agentId={agentId} projectId={projectId} />,
    },
  ]

  return (
    <div className="w-[400px] shrink-0 border-l border-border bg-surface flex flex-col">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border shrink-0">
        <p className="text-xs font-semibold text-muted uppercase tracking-wider">Inspector</p>
        <button
          onClick={onCollapse}
          className="flex items-center justify-center w-7 h-7 rounded-md text-muted hover:text-white hover:bg-accent transition-colors"
          title="Collapse inspector"
        >
          <PanelRightClose className="h-4 w-4" />
        </button>
      </div>
      <div className="flex-1 min-h-0 overflow-hidden">
        <InspectorTabs tabs={tabs} defaultTab={activeTab} onTabChange={onTabChange} />
      </div>
    </div>
  )
}
