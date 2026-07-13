import { useEffect, useMemo, useRef, useState } from 'react'
import { Bot, Edit3, GitBranch, MessageSquare, Power, Rocket, Settings2 } from 'lucide-react'
import { toast } from 'sonner'

import { useUpdateAgent } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import { AgentEditorProvider, useAgentEditor } from '@/features/playground/AgentEditorContext'
import { cn } from '@/lib/utils'
import { NetworkAgentChat } from './NetworkAgentChat'
import { NetworkAgentEditor } from './NetworkAgentEditor'
import { NetworkAgentVersions } from './NetworkAgentVersions'

type AgentWorkspaceTab = 'editor' | 'versions' | 'chat'
type BindingSource = 'draft' | 'staging' | 'release'
type SessionMode = 'stateful' | 'stateless'

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

function RuntimePopover({
  agentId,
  status,
  sessionMode,
  onStatus,
  onSessionMode,
}: {
  agentId: string
  status: string
  sessionMode: SessionMode
  onStatus: (status: string) => void
  onSessionMode: (mode: SessionMode) => void
}) {
  const updateAgent = useUpdateAgent(agentId)
  const [open, setOpen] = useState(false)
  const [confirmingOff, setConfirmingOff] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const active = status !== 'inactive'

  useEffect(() => {
    if (!open) return
    const close = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false)
        setConfirmingOff(false)
      }
    }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [open])

  const updateStatus = async (next: string) => {
    const previous = status
    onStatus(next)
    try {
      await updateAgent.mutateAsync({ status: next })
      toast.success(next === 'inactive' ? 'Agent runtime turned off' : 'Agent runtime turned on')
      setConfirmingOff(false)
    } catch (error) {
      onStatus(previous)
      toast.error(error instanceof Error ? error.message : 'Failed to update Agent runtime')
    }
  }

  const updateSessionMode = async (next: SessionMode) => {
    if (next === sessionMode) return
    const previous = sessionMode
    onSessionMode(next)
    try {
      await updateAgent.mutateAsync({ session_mode: next })
      toast.success(`Agent runtime is now ${next}`)
    } catch (error) {
      onSessionMode(previous)
      toast.error(error instanceof Error ? error.message : 'Failed to update session mode')
    }
  }

  return (
    <div ref={containerRef} className="relative ml-auto shrink-0">
      <button
        type="button"
        onClick={() => { setOpen((value) => !value); setConfirmingOff(false) }}
        className={cn(
          'flex h-7 w-7 items-center justify-center rounded-lg border transition-colors',
          open ? 'border-primary/35 bg-primary/10 text-primary-light' : 'border-border/80 bg-background/45 text-muted hover:text-white',
        )}
        aria-label="Agent runtime settings"
        title="Agent runtime"
      >
        <Settings2 className="h-3.5 w-3.5" />
      </button>

      {open ? (
        <div className="absolute right-0 top-9 z-[70] w-64 overflow-hidden rounded-xl border border-border/90 bg-surface shadow-2xl shadow-black/45">
          {confirmingOff ? (
            <div className="p-3">
              <div className="flex items-start gap-2.5">
                <Power className="mt-0.5 h-4 w-4 shrink-0 text-red-300" />
                <div><p className="text-[11px] font-semibold text-white">Turn off this Agent?</p><p className="mt-1 text-[9px] leading-4 text-muted">Runtime requests and the isolated Chat stop immediately. Draft and Network bindings are unchanged.</p></div>
              </div>
              <div className="mt-3 flex justify-end gap-2">
                <button type="button" onClick={() => setConfirmingOff(false)} className="rounded-lg border border-border px-2.5 py-1.5 text-[9px] text-muted hover:text-white">Cancel</button>
                <button type="button" disabled={updateAgent.isPending} onClick={() => { void updateStatus('inactive') }} className="rounded-lg border border-red-500/30 bg-red-500/10 px-2.5 py-1.5 text-[9px] font-medium text-red-200 disabled:opacity-50">Turn off</button>
              </div>
            </div>
          ) : (
            <div className="p-3">
              <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted">Runtime</p>
              <div className="mt-3 flex items-center justify-between gap-3">
                <div><p className="text-[10px] font-medium text-white">Execution</p><p className="mt-0.5 text-[8px] text-muted">Immediate operational state</p></div>
                <button
                  type="button"
                  disabled={updateAgent.isPending}
                  onClick={() => active ? setConfirmingOff(true) : void updateStatus('active')}
                  className={cn('relative h-6 w-10 rounded-full border transition-colors disabled:opacity-50', active ? 'border-emerald-500/40 bg-emerald-500/15' : 'border-border bg-background')}
                  aria-pressed={active}
                  aria-label={active ? 'Turn Agent off' : 'Turn Agent on'}
                >
                  <span className={cn('absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full transition-all', active ? 'left-5 bg-emerald-300' : 'left-1 bg-muted')} />
                </button>
              </div>

              <div className="mt-3 border-t border-border/75 pt-3">
                <div className="flex items-center justify-between gap-3"><div><p className="text-[10px] font-medium text-white">Session mode</p><p className="mt-0.5 text-[8px] text-muted">Controls runtime memory</p></div></div>
                <div className="mt-2 grid grid-cols-2 gap-1 rounded-lg border border-border/80 bg-background/45 p-1">
                  {(['stateful', 'stateless'] as SessionMode[]).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      disabled={updateAgent.isPending}
                      onClick={() => { void updateSessionMode(mode) }}
                      className={cn('rounded-md px-2 py-1.5 text-[9px] font-medium capitalize', mode === sessionMode ? 'bg-primary/12 text-primary-light' : 'text-muted hover:text-white')}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </div>

              <p className="mt-3 border-t border-border/75 pt-2 text-[8px] leading-4 text-muted">Applies immediately. Runtime controls are not part of the Agent Draft or Releases.</p>
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}

function NetworkAgentWorkspaceContent({ agent, projectId, networkBinding, onOpenComposition, onDirtyChange, onRegisterSaveAction }: NetworkAgentWorkspaceProps) {
  const [tab, setTab] = useState<AgentWorkspaceTab>('editor')
  const [runtimeStatus, setRuntimeStatus] = useState(agent.status || 'active')
  const [runtimeSessionMode, setRuntimeSessionMode] = useState<SessionMode>(agent.session_mode === 'stateless' ? 'stateless' : 'stateful')
  const { loadedReleaseVersion } = useAgentEditor()

  useEffect(() => { setRuntimeStatus(agent.status || 'active') }, [agent.status])
  useEffect(() => { setRuntimeSessionMode(agent.session_mode === 'stateless' ? 'stateless' : 'stateful') }, [agent.session_mode])

  const runtimeAgent = useMemo<Agent>(() => ({ ...agent, status: runtimeStatus, session_mode: runtimeSessionMode }), [agent, runtimeSessionMode, runtimeStatus])
  const bindingTitle = loadedReleaseVersion ? `Draft based on ${loadedReleaseVersion}. Editing it does not change the Network binding.` : 'Editing the Agent Draft does not change the Network binding.'

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-surface/75">
      <div className="shrink-0 border-b border-border/80 bg-background/20 px-3 py-2.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary-light"><Bot className="h-3.5 w-3.5" /></div>
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 items-center gap-2">
              <p className="truncate text-[11px] font-semibold text-white">{agent.name}</p>
              <span className={cn('shrink-0 rounded border px-1.5 py-0.5 text-[8px] font-semibold uppercase', runtimeStatus === 'inactive' ? 'border-red-500/30 bg-red-500/10 text-red-300' : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300')}>{runtimeStatus}</span>
              <span className="shrink-0 rounded border border-border bg-background/50 px-1.5 py-0.5 text-[8px] font-semibold uppercase text-muted">{runtimeSessionMode}</span>
              <RuntimePopover agentId={agent.id} status={runtimeStatus} sessionMode={runtimeSessionMode} onStatus={setRuntimeStatus} onSessionMode={setRuntimeSessionMode} />
            </div>
            <div className="mt-1 flex min-w-0 items-center gap-1.5 text-[8px] text-muted" title={bindingTitle}>
              <GitBranch className="h-3 w-3 shrink-0 text-primary-light" />
              <span className="truncate">Network uses <span className="text-white">{sourceLabel(networkBinding.source)}</span> <span className="font-mono text-slate-300">{networkBinding.version}</span></span>
              <button type="button" onClick={onOpenComposition} className="ml-auto shrink-0 font-medium text-primary-light hover:text-white">Composition</button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex shrink-0 gap-1 border-b border-border/80 bg-surface/60 p-1.5">
        {([['editor', 'Editor', Edit3], ['versions', 'Versions', Rocket], ['chat', 'Chat', MessageSquare]] as Array<[AgentWorkspaceTab, string, typeof Edit3]>).map(([id, label, Icon]) => (
          <button key={id} type="button" onClick={() => setTab(id)} className={cn('flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-2 py-1.5 text-[10px] font-medium', tab === id ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white')}><Icon className="h-3.5 w-3.5" />{label}</button>
        ))}
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden">
        <div className={cn('absolute inset-0', tab !== 'editor' && 'invisible pointer-events-none')} aria-hidden={tab !== 'editor'}>
          <NetworkAgentEditor agent={agent} projectId={projectId} agentId={agent.id} onDirtyChange={onDirtyChange} onRegisterSaveAction={onRegisterSaveAction} />
        </div>
        <div className={cn('absolute inset-0', tab !== 'versions' && 'invisible pointer-events-none')} aria-hidden={tab !== 'versions'}>
          <NetworkAgentVersions agent={agent} projectId={projectId} networkBinding={networkBinding} onOpenComposition={onOpenComposition} />
        </div>
        <div className={cn('absolute inset-0', tab !== 'chat' && 'invisible pointer-events-none')} aria-hidden={tab !== 'chat'}>
          <NetworkAgentChat agent={runtimeAgent} projectId={projectId} onChatCompleted={() => undefined} />
        </div>
      </div>
    </div>
  )
}

export function NetworkAgentWorkspace(props: NetworkAgentWorkspaceProps) {
  return <AgentEditorProvider key={props.agent.id} agent={props.agent} projectId={props.projectId}><NetworkAgentWorkspaceContent {...props} /></AgentEditorProvider>
}
