import { Tabs } from '@/components/ui/Tabs'
import { AgentQuickSettings } from './AgentQuickSettings'
import { ModelQuickSettings } from './ModelQuickSettings'
import { KnowledgePanel } from './KnowledgePanel'
import { DebugPanel } from './DebugPanel'
import { ApiExamplePanel } from './ApiExamplePanel'
import { Bot, Cpu, BookOpen, Bug, Code2 } from 'lucide-react'
import type { Agent } from '@/features/agents/types'
import type { AskResponse } from '@/features/playground/types'

interface PlaygroundSidePanelProps {
  agent: Agent
  projectId: string
  agentId: string
  organizationId?: string
  lastResponse: AskResponse | null
  sessionId: string | null
  messagesCount: number
  orgProjectPathFn: (projId: string, ...segments: string[]) => string
}

export function PlaygroundSidePanel({
  agent,
  projectId,
  agentId,
  organizationId,
  lastResponse,
  sessionId,
  messagesCount,
  orgProjectPathFn,
}: PlaygroundSidePanelProps) {
  const tabs = [
    {
      id: 'agent',
      label: (
        <span className="flex items-center gap-1.5">
          <Bot className="h-3.5 w-3.5" />
          Agent
        </span>
      ),
      content: <AgentQuickSettings agent={agent} />,
    },
    {
      id: 'model',
      label: (
        <span className="flex items-center gap-1.5">
          <Cpu className="h-3.5 w-3.5" />
          Model
        </span>
      ),
      content: <ModelQuickSettings agent={agent} projectId={projectId} />,
    },
    {
      id: 'knowledge',
      label: (
        <span className="flex items-center gap-1.5">
          <BookOpen className="h-3.5 w-3.5" />
          Knowledge
        </span>
      ),
      content: <KnowledgePanel projectId={projectId} agentId={agentId} organizationId={organizationId} />,
    },
    {
      id: 'debug',
      label: (
        <span className="flex items-center gap-1.5">
          <Bug className="h-3.5 w-3.5" />
          Debug
        </span>
      ),
      content: <DebugPanel sessionId={sessionId} agent={agent} lastResponse={lastResponse} messagesCount={messagesCount} />,
    },
    {
      id: 'api',
      label: (
        <span className="flex items-center gap-1.5">
          <Code2 className="h-3.5 w-3.5" />
          API
        </span>
      ),
      content: <ApiExamplePanel agent={agent} projectId={projectId} orgProjectPathFn={orgProjectPathFn} />,
    },
  ]

  return (
    <div className="w-[420px] shrink-0 overflow-y-auto border-l border-border bg-surface">
      <Tabs tabs={tabs} className="p-4" />
    </div>
  )
}
