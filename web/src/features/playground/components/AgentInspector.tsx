import { Bot, Cpu, BookOpen, FileJson } from 'lucide-react'
import { InspectorTabs } from './InspectorTabs'
import { AgentSettingsTab } from './AgentSettingsTab'
import { ModelSettingsTab } from './ModelSettingsTab'
import { KnowledgeTab } from './KnowledgeTab'
import { OutputSettingsTab } from './OutputSettingsTab'
import { PanelRightClose } from 'lucide-react'
import type { Agent } from '@/features/agents/types'

interface AgentInspectorProps {
  agent: Agent
  projectId: string
  agentId: string
  activeTab: string
  onTabChange: (tab: string) => void
  onCollapse: () => void
}

export function AgentInspector({ agent, projectId, agentId, activeTab, onTabChange, onCollapse }: AgentInspectorProps) {
  const tabs = [
    {
      id: 'agent',
      label: 'Agent',
      icon: <Bot className="h-3.5 w-3.5" />,
      content: <AgentSettingsTab agent={agent} />,
    },
    {
      id: 'model',
      label: 'Model',
      icon: <Cpu className="h-3.5 w-3.5" />,
      content: <ModelSettingsTab agent={agent} projectId={projectId} />,
    },
    {
      id: 'knowledge',
      label: 'Knowledge',
      icon: <BookOpen className="h-3.5 w-3.5" />,
      content: <KnowledgeTab projectId={projectId} agentId={agentId} />,
    },
    {
      id: 'output',
      label: 'Output',
      icon: <FileJson className="h-3.5 w-3.5" />,
      content: <OutputSettingsTab agent={agent} />,
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
