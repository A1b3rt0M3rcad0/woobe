import { useEffect, useState } from 'react'
import { Bot, CheckCircle2, ChevronDown, ChevronRight, Edit3, GitBranch, MessageSquare, Rocket } from 'lucide-react'

import type { Agent } from '@/features/agents/types'
import { AgentEditorProvider, useAgentEditor } from '@/features/playground/AgentEditorContext'
import { cn } from '@/lib/utils'
import { NetworkAgentChat } from './NetworkAgentChat'
import { NetworkAgentEditor } from './NetworkAgentEditor'
import { NetworkAgentVersions } from './NetworkAgentVersions'

type AgentWorkspaceTab = 'editor' | 'versions' | 'chat'
type BindingSource = 'draft' | 'staging' | 'release'

export interface AgentNetworkBindingSummary {
  source: BindingSource
  version: string
}

interface NetworkAgentWorkspaceProps {
  agent: Agent
  projectId: string
  networkBinding: AgentNetworkBindingSummary
  onOpenComposition: () => void
  onDirtyChange?: (dirty: boolean) => void
  onRegisterSaveAction?: (action: (() => Promise<boolean>) | null) => void
}

function sourceLabel(source: BindingSource) {
  if (source === 'draft') return 'Draft'
  if (source === 'staging') return 'Staging'
  return 'Release'
}

function onboardingStorageKey(agentId: string) {
  return `network-agent-onboarding:${agentId}`
}

function NetworkAgentWorkspaceContent({
  agent,
  projectId,
  networkBinding,
  onOpenComposition,
  onDirtyChange,
  onRegisterSaveAction,
}: NetworkAgentWorkspaceProps) {
  const [tab, setTab] = useState<AgentWorkspaceTab>('editor')
  const [chatCompleted, setChatCompleted] = useState(false)
  const [onboardingOpen, setOnboardingOpen] = useState(() => {
    if (typeof window === 'undefined') return true
    return window.sessionStorage.getItem(onboardingStorageKey(agent.id)) !== 'seen'
  })
  const { isDirty, loadedReleaseVersion } = useAgentEditor()

  useEffect(() => {
    if (!chatCompleted) return
    setOnboardingOpen(false)
    if (typeof window !== 'undefined') window.sessionStorage.setItem(onboardingStorageKey(agent.id), 'seen')
  }, [agent.id, chatCompleted])

  const completedSteps = 2 + Number(chatCompleted)

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-surface/75">
      <div className="shrink-0 border-b border-border/80 bg-background/20 px-3 py-2.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary-light">
            <Bot className="h-3.5 w-3.5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 items-center gap-2">
              <p className="truncate text-[11px] font-semibold text-white">{agent.name}</p>
              <span className={cn(
                'shrink-0 rounded border px-1.5 py-0.5 text-[8px] font-semibold uppercase',
                agent.status === 'inactive'
                  ? 'border-red-500/30 bg-red-500/10 text-red-300'
                  : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
              )}>
                {agent.status || 'active'}
              </span>
              <span className="shrink-0 rounded border border-border bg-background/50 px-1.5 py-0.5 text-[8px] font-semibold uppercase text-muted">
                {agent.session_mode === 'stateless' ? 'stateless' : 'stateful'}
              </span>
            </div>
            <p className="mt-0.5 truncate text-[9px] text-muted">{agent.provider || 'No provider'}/{agent.model || 'No model'}</p>
          </div>
        </div>

        <div className="mt-2 flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/[0.045] px-2.5 py-2">
          <GitBranch className="h-3.5 w-3.5 shrink-0 text-primary-light" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-[9px] text-white">
              Network: <span className="font-medium">{sourceLabel(networkBinding.source)}</span> <span className="font-mono text-slate-300">{networkBinding.version}</span>
            </p>
            <p className="mt-0.5 truncate text-[8px] text-muted">
              Editing {loadedReleaseVersion ? `a Draft based on ${loadedReleaseVersion}` : 'the Agent Draft'} does not change this binding.
            </p>
          </div>
          <button type="button" onClick={onOpenComposition} className="shrink-0 text-[9px] font-medium text-primary-light hover:text-white">
            Composition
          </button>
        </div>
      </div>

      <div className="shrink-0 border-b border-border/80 bg-background/15 px-2 py-1.5">
        <button
          type="button"
          onClick={() => {
            const next = !onboardingOpen
            setOnboardingOpen(next)
            if (!next && typeof window !== 'undefined') window.sessionStorage.setItem(onboardingStorageKey(agent.id), 'seen')
          }}
          className="flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left hover:bg-background/40"
        >
          <CheckCircle2 className={cn('h-3.5 w-3.5', completedSteps === 3 ? 'text-emerald-400' : 'text-primary-light')} />
          <span className="text-[9px] font-medium text-white">Setup {completedSteps}/3</span>
          <span className="truncate text-[8px] text-muted">
            {isDirty ? 'Unsaved Draft' : 'Draft ready'} · {chatCompleted ? 'Chat validated' : 'Chat pending'}
          </span>
          {onboardingOpen ? <ChevronDown className="ml-auto h-3 w-3 text-muted" /> : <ChevronRight className="ml-auto h-3 w-3 text-muted" />}
        </button>
        {onboardingOpen && (
          <div className="mt-1 grid grid-cols-3 gap-1.5 px-1 pb-1 text-[8px] text-muted">
            <span className="rounded-md border border-border/70 bg-background/35 px-2 py-1.5"><b className="text-emerald-400">1.</b> Agent selected</span>
            <span className="rounded-md border border-border/70 bg-background/35 px-2 py-1.5"><b className={isDirty ? 'text-amber-400' : 'text-emerald-400'}>2.</b> {isDirty ? 'Save Draft' : 'Draft ready'}</span>
            <button type="button" onClick={() => setTab('chat')} className="rounded-md border border-border/70 bg-background/35 px-2 py-1.5 text-left hover:border-primary/30 hover:text-white"><b className={chatCompleted ? 'text-emerald-400' : 'text-muted'}>3.</b> Open Chat</button>
          </div>
        )}
      </div>

      <div className="flex shrink-0 gap-1 border-b border-border/80 bg-surface/60 p-1.5">
        {([
          ['editor', 'Editor', Edit3],
          ['versions', 'Versions', Rocket],
          ['chat', 'Chat', MessageSquare],
        ] as Array<[AgentWorkspaceTab, string, typeof Edit3]>).map(([id, label, Icon]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={cn(
              'flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-2 py-1.5 text-[10px] font-medium',
              tab === id
                ? 'border-primary/30 bg-primary/10 text-primary-light'
                : 'border-transparent text-muted hover:border-border/70 hover:text-white',
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden">
        <div className={cn('absolute inset-0', tab !== 'editor' && 'invisible pointer-events-none')} aria-hidden={tab !== 'editor'}>
          <NetworkAgentEditor
            agent={agent}
            projectId={projectId}
            agentId={agent.id}
            onDirtyChange={onDirtyChange}
            onRegisterSaveAction={onRegisterSaveAction}
          />
        </div>
        <div className={cn('absolute inset-0', tab !== 'versions' && 'invisible pointer-events-none')} aria-hidden={tab !== 'versions'}>
          <NetworkAgentVersions agent={agent} projectId={projectId} networkBinding={networkBinding} onOpenComposition={onOpenComposition} />
        </div>
        <div className={cn('absolute inset-0', tab !== 'chat' && 'invisible pointer-events-none')} aria-hidden={tab !== 'chat'}>
          <NetworkAgentChat agent={agent} projectId={projectId} onChatCompleted={() => setChatCompleted(true)} />
        </div>
      </div>
    </div>
  )
}

export function NetworkAgentWorkspace(props: NetworkAgentWorkspaceProps) {
  return (
    <AgentEditorProvider key={props.agent.id} agent={props.agent} projectId={props.projectId}>
      <NetworkAgentWorkspaceContent {...props} />
    </AgentEditorProvider>
  )
}
