import { useState } from 'react'
import { Bot, Edit3, GitBranch, MessageSquare, Rocket } from 'lucide-react'

import type { Agent } from '@/features/agents/types'
import { AgentEditorProvider, useAgentEditor } from '@/features/playground/AgentEditorContext'
import { cn } from '@/lib/utils'
import { NetworkAgentChat } from './NetworkAgentChat'
import { NetworkAgentEditor } from './NetworkAgentEditor'
import { NetworkAgentVersions } from './NetworkAgentVersions'

type AgentWorkspaceTab = 'editor' | 'versions' | 'chat'
type BindingSource = 'draft' | 'staging' | 'release'

export interface AgentNetworkBindingSummary { source: BindingSource; version: string }
interface NetworkAgentWorkspaceProps { agent: Agent; projectId: string; networkBinding: AgentNetworkBindingSummary; onOpenComposition: () => void; onDirtyChange?: (dirty: boolean) => void; onRegisterSaveAction?: (action: (() => Promise<boolean>) | null) => void }
function sourceLabel(source: BindingSource) { return source === 'draft' ? 'Draft' : source === 'staging' ? 'Staging' : 'Release' }

function NetworkAgentWorkspaceContent({ agent, projectId, networkBinding, onOpenComposition, onDirtyChange, onRegisterSaveAction }: NetworkAgentWorkspaceProps) {
  const [tab, setTab] = useState<AgentWorkspaceTab>('editor')
  const { loadedReleaseVersion } = useAgentEditor()
  return <div className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-surface/75">
    <div className="shrink-0 border-b border-border/80 bg-background/20 px-3 py-2.5"><div className="flex items-center gap-2.5"><div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary-light"><Bot className="h-3.5 w-3.5" /></div><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><p className="truncate text-[11px] font-semibold text-white">{agent.name}</p><span className={cn('shrink-0 rounded border px-1.5 py-0.5 text-[8px] font-semibold uppercase', agent.status === 'inactive' ? 'border-red-500/30 bg-red-500/10 text-red-300' : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300')}>{agent.status || 'active'}</span><span className="shrink-0 rounded border border-border bg-background/50 px-1.5 py-0.5 text-[8px] font-semibold uppercase text-muted">{agent.session_mode === 'stateless' ? 'stateless' : 'stateful'}</span></div><div className="mt-1 flex min-w-0 items-center gap-1.5 text-[8px] text-muted"><GitBranch className="h-3 w-3 shrink-0 text-primary-light" /><span className="truncate">Network uses <span className="text-white">{sourceLabel(networkBinding.source)}</span> <span className="font-mono text-slate-300">{networkBinding.version}</span></span><button type="button" onClick={onOpenComposition} className="ml-auto shrink-0 font-medium text-primary-light hover:text-white">Composition</button></div>{loadedReleaseVersion ? <p className="mt-1 truncate text-[8px] text-muted">Editing a Draft based on <span className="font-mono text-slate-300">{loadedReleaseVersion}</span> does not change this binding.</p> : null}</div></div></div>
    <div className="flex shrink-0 gap-1 border-b border-border/80 bg-surface/60 p-1.5">{([['editor', 'Editor', Edit3], ['versions', 'Versions', Rocket], ['chat', 'Chat', MessageSquare]] as Array<[AgentWorkspaceTab, string, typeof Edit3]>).map(([id, label, Icon]) => <button key={id} type="button" onClick={() => setTab(id)} className={cn('flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-2 py-1.5 text-[10px] font-medium', tab === id ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white')}><Icon className="h-3.5 w-3.5" />{label}</button>)}</div>
    <div className="relative min-h-0 flex-1 overflow-hidden"><div className={cn('absolute inset-0', tab !== 'editor' && 'invisible pointer-events-none')} aria-hidden={tab !== 'editor'}><NetworkAgentEditor agent={agent} projectId={projectId} agentId={agent.id} onDirtyChange={onDirtyChange} onRegisterSaveAction={onRegisterSaveAction} /></div><div className={cn('absolute inset-0', tab !== 'versions' && 'invisible pointer-events-none')} aria-hidden={tab !== 'versions'}><NetworkAgentVersions agent={agent} projectId={projectId} networkBinding={networkBinding} onOpenComposition={onOpenComposition} /></div><div className={cn('absolute inset-0', tab !== 'chat' && 'invisible pointer-events-none')} aria-hidden={tab !== 'chat'}><NetworkAgentChat agent={agent} projectId={projectId} onChatCompleted={() => undefined} /></div></div>
  </div>
}

export function NetworkAgentWorkspace(props: NetworkAgentWorkspaceProps) {
  return <AgentEditorProvider key={props.agent.id} agent={props.agent} projectId={props.projectId}><NetworkAgentWorkspaceContent {...props} /></AgentEditorProvider>
}
