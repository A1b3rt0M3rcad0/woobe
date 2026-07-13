import { useState } from 'react'
import { Edit3, Rocket } from 'lucide-react'

import type { Agent } from '@/features/agents/types'
import { AgentEditorWorkspace } from './AgentEditorWorkspace'
import { InspectorTabs } from './InspectorTabs'
import { ReleaseTab } from './ReleaseTab'

interface AgentInspectorProps {
  agent: Agent
  projectId: string
  agentId: string
  activeTab: string
  onTabChange: (tab: string) => void
  onCollapse?: () => void
}

export function AgentInspector({ agent, projectId, agentId, activeTab, onTabChange }: AgentInspectorProps) {
  const [resolvedActiveTab, setResolvedActiveTab] = useState(activeTab === 'runtime' ? 'editor' : activeTab)
  const tabs = [
    {
      id: 'editor',
      label: 'Editor',
      icon: <Edit3 className="h-3.5 w-3.5" />,
      content: <AgentEditorWorkspace agent={agent} projectId={projectId} agentId={agentId} />,
    },
    {
      id: 'versions',
      label: 'Versions',
      icon: <Rocket className="h-3.5 w-3.5" />,
      content: <div className="versions-tab-compact h-full"><ReleaseTab agentId={agentId} projectId={projectId} /></div>,
    },
  ]

  const handleTabChange = (tab: string) => {
    setResolvedActiveTab(tab)
    onTabChange(tab)
  }

  return (
    <div className="flex w-[400px] shrink-0 flex-col border-l border-border/90 bg-surface/75 shadow-sm shadow-black/5">
      <div className="flex items-center justify-between border-b border-border/90 bg-background/25 px-3 py-3 shrink-0">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted">Inspector</p>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        <InspectorTabs tabs={tabs} defaultTab={resolvedActiveTab} onTabChange={handleTabChange} />
      </div>
    </div>
  )
}
