import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, Bot, CheckCircle2, Edit3, GitBranch, MessageSquare, Rocket, RotateCcw } from 'lucide-react'
import { toast } from 'sonner'

import type { Agent } from '@/features/agents/types'
import { AgentEditorProvider, useAgentEditor } from '@/features/playground/AgentEditorContext'
import { useAskStream } from '@/features/playground/hooks'
import type { AskResponse, ChatMessage as ChatMessageType, ToolCallInfo } from '@/features/playground/types'
import { AgentEditorWorkspace } from '@/features/playground/components/AgentEditorWorkspace'
import { ChatCanvas } from '@/features/playground/components/ChatCanvas'
import { ReleaseTab } from '@/features/playground/components/ReleaseTab'
import { cn } from '@/lib/utils'

type AgentWorkspaceTab = 'editor' | 'versions' | 'test'
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

function upsertToolCall(existing: ToolCallInfo[] | null | undefined, next: ToolCallInfo): ToolCallInfo[] {
  const items = existing ? [...existing] : []
  const index = next.tool_call_id
    ? items.findIndex((item) => item.tool_call_id === next.tool_call_id)
    : -1
  if (index === -1) return [...items, next]
  items[index] = {
    ...items[index],
    ...next,
    input: next.input ?? items[index].input,
    output: next.output ?? items[index].output,
  }
  return items
}

function sourceLabel(source: BindingSource) {
  if (source === 'draft') return 'Agent Draft'
  if (source === 'staging') return 'Agent Staging'
  return 'Agent Release'
}

function sourceClass(source: BindingSource) {
  if (source === 'draft') return 'border-blue-500/30 bg-blue-500/10 text-blue-300'
  if (source === 'staging') return 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300'
  return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
}

function AgentWorkspaceOnboarding({ isDirty, testCompleted }: { isDirty: boolean; testCompleted: boolean }) {
  return (
    <div className="border-b border-border/80 bg-background/20 px-3 py-3">
      <div className="rounded-xl border border-primary/20 bg-primary/[0.045] p-3">
        <div className="flex items-start gap-2.5">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold text-white">Configure and validate this Agent without leaving the Network</p>
            <div className="mt-2 grid gap-1 text-[9px] text-muted">
              <span className="flex items-center gap-2"><span className="text-emerald-400">●</span> Agent selected</span>
              <span className="flex items-center gap-2"><span className={isDirty ? 'text-amber-400' : 'text-emerald-400'}>●</span> {isDirty ? 'Draft contains unsaved changes' : 'Draft is synchronized'}</span>
              <span className="flex items-center gap-2"><span className={testCompleted ? 'text-emerald-400' : 'text-muted'}>●</span> {testCompleted ? 'Isolated Agent test completed' : 'Run an isolated Agent test'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function AgentTestPanel({ agent, projectId, onTestCompleted }: { agent: Agent; projectId: string; onTestCompleted: () => void }) {
  const { state, toSnapshot, isDirty } = useAgentEditor()
  const { stream, cancel } = useAskStream()
  const [messages, setMessages] = useState<ChatMessageType[]>([])
  const [isSending, setIsSending] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessionSnapshot, setSessionSnapshot] = useState<Record<string, unknown> | null>(null)
  const [pinnedPreviousSnapshot, setPinnedPreviousSnapshot] = useState(false)
  const accumulatedRef = useRef('')
  const metadataRef = useRef<Partial<AskResponse>>({})

  const currentSnapshot = toSnapshot()
  const currentSignature = useMemo(() => JSON.stringify(currentSnapshot), [currentSnapshot])
  const sessionSignature = useMemo(() => sessionSnapshot ? JSON.stringify(sessionSnapshot) : null, [sessionSnapshot])
  const configurationChanged = Boolean(sessionSignature && currentSignature !== sessionSignature)
  const isStateless = agent.session_mode === 'stateless'
  const isInactive = agent.status === 'inactive'
  const effectiveSnapshot = pinnedPreviousSnapshot && sessionSnapshot ? sessionSnapshot : currentSnapshot

  const updateLastAssistant = useCallback((updater: (message: ChatMessageType) => ChatMessageType) => {
    setMessages((previous) => {
      const updated = [...previous]
      const last = updated[updated.length - 1]
      if (last?.role === 'assistant') updated[updated.length - 1] = updater(last)
      return updated
    })
  }, [])

  const startNewSession = useCallback(() => {
    cancel()
    setMessages([])
    setSessionId(null)
    setSessionSnapshot(currentSnapshot)
    setPinnedPreviousSnapshot(false)
    accumulatedRef.current = ''
    metadataRef.current = {}
    toast.success('New isolated Agent test session started')
  }, [cancel, currentSignature])

  useEffect(() => {
    if (!isStateless || !sessionId) return
    setSessionId(null)
  }, [isStateless, sessionId])

  const handleSend = async (content: string) => {
    if (!content.trim() || isSending || isInactive) return
    if (configurationChanged && !pinnedPreviousSnapshot) {
      toast.warning('Start a new test session or keep the previous Draft snapshot before sending')
      return
    }

    const snapshot = effectiveSnapshot
    if (!sessionSnapshot) setSessionSnapshot(snapshot)
    accumulatedRef.current = ''
    metadataRef.current = {}
    setMessages((previous) => [
      ...previous,
      { role: 'user', content },
      { role: 'assistant', content: '', activity: { status: 'working', message: 'Working...' } },
    ])
    setIsSending(true)

    try {
      await stream({
        project_id: projectId,
        agent_id: agent.id,
        message: content,
        session_id: isStateless ? null : sessionId,
        execution_context: 'playground',
        metadata: { source: 'network_agent_test', client_sent_at: new Date().toISOString() },
        snapshot_override: snapshot,
      } as any, {
        onMeta: (meta) => {
          if (!isStateless && meta.session_id) setSessionId(meta.session_id)
          if (meta.trace_id) metadataRef.current.trace_id = meta.trace_id
        },
        onAgentActivity: (activity) => {
          updateLastAssistant((last) => ({ ...last, activity }))
        },
        onToken: (token) => {
          if (token.visibility !== 'assistant' || token.channel !== 'final') return
          accumulatedRef.current += token.content
          updateLastAssistant((last) => ({ ...last, content: accumulatedRef.current, activity: null }))
        },
        onTokenRetract: (info) => {
          if (info.content_length > 0) {
            accumulatedRef.current = accumulatedRef.current.slice(0, Math.max(0, accumulatedRef.current.length - info.content_length))
          }
          updateLastAssistant((last) => ({
            ...last,
            content: accumulatedRef.current,
            activity: { status: 'planning_tools', message: 'Checking whether tools are needed...' },
          }))
        },
        onInternalToken: () => undefined,
        onSources: (sources) => {
          metadataRef.current.sources = sources
        },
        onToolCallStarted: (info) => {
          const running: ToolCallInfo = { ...info, status: info.status ?? 'running' }
          updateLastAssistant((last) => ({
            ...last,
            activity: { status: 'calling_tool', message: `Calling tool: ${running.tool_name}...`, tool_name: running.tool_name },
            tool_calls: upsertToolCall(last.tool_calls, running),
          }))
        },
        onToolCallCompleted: (info) => {
          updateLastAssistant((last) => ({
            ...last,
            activity: { status: 'processing_tool_result', message: 'Processing tool result...', tool_name: info.tool_name },
            tool_calls: upsertToolCall(last.tool_calls, info),
          }))
        },
        onFallback: (info) => {
          accumulatedRef.current = ''
          updateLastAssistant((last) => ({ ...last, content: '', activity: { status: 'working', message: 'Trying fallback model...' } }))
          toast.info(`Primary model failed. Retrying with ${info.fallback_provider}/${info.fallback_model}.`)
        },
        onDone: (response) => {
          const finalContent = response.answer || accumulatedRef.current || ''
          if (!isStateless && response.session_id) setSessionId(response.session_id)
          setMessages((previous) => {
            const updated = [...previous]
            const last = updated[updated.length - 1]
            if (last?.role === 'assistant') {
              updated[updated.length - 1] = {
                ...last,
                content: finalContent,
                activity: null,
                usage: response.usage ?? null,
                sources: (response.sources ?? metadataRef.current.sources) as ChatMessageType['sources'],
                tool_calls: (response.tool_calls ?? last.tool_calls ?? null) as ChatMessageType['tool_calls'],
                model: response.model ?? null,
                provider: response.provider ?? null,
                latency_ms: response.latency_ms ?? null,
                trace_id: response.trace_id ?? null,
                parsed_output: response.parsed_output ?? null,
                output_parse_error: response.output_parse_error ?? null,
              }
            }
            return updated
          })
          if (finalContent.trim() && !response.output_parse_error) onTestCompleted()
        },
        onError: (error) => {
          toast.error(error.message)
          updateLastAssistant((last) => ({
            ...last,
            activity: null,
            content: last.content || `Error: ${error.message}`,
            output_parse_error: error.message,
            trace_id: metadataRef.current.trace_id ?? null,
          }))
        },
      })
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) {
        toast.error(error instanceof Error ? error.message : 'Agent test failed')
      }
    } finally {
      setIsSending(false)
    }
  }

  const runtimeBlockReason = isInactive ? 'Agent is inactive. Activate it before running isolated tests.' : undefined

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-background">
      <div className="border-b border-border/80 bg-surface/45 px-3 py-3">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
            <MessageSquare className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-xs font-semibold text-white">Agent Chat</p>
              <span className={cn('rounded-md border px-1.5 py-0.5 text-[8px] font-semibold uppercase', isDirty ? 'border-amber-500/30 bg-amber-500/10 text-amber-300' : 'border-blue-500/30 bg-blue-500/10 text-blue-300')}>
                {isDirty ? 'Draft preview' : 'Current Draft'}
              </span>
            </div>
            <p className="mt-1 text-[9px] leading-4 text-muted">Runs only {agent.name}. The Network composition and binding remain unchanged.</p>
          </div>
          <button type="button" onClick={startNewSession} className="flex shrink-0 items-center gap-1 rounded-lg border border-border/80 bg-background/40 px-2 py-1.5 text-[9px] text-muted hover:text-white">
            <RotateCcw className="h-3 w-3" /> New session
          </button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[9px] text-muted">
          <span>{state.provider || 'No provider'}/{state.model || 'No model'}</span>
          <span>·</span>
          <span>{isStateless ? 'Stateless' : sessionId ? `Session ${sessionId.slice(0, 8)}…` : 'Stateful · new session'}</span>
          {isInactive && <span className="font-medium text-red-400">· inactive</span>}
        </div>

        {configurationChanged && !pinnedPreviousSnapshot && (
          <div className="mt-3 flex items-start gap-2 rounded-xl border border-amber-500/25 bg-amber-500/[0.06] p-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-medium text-amber-100">Agent configuration changed during this session</p>
              <p className="mt-1 text-[9px] leading-4 text-amber-100/65">Keep the previous Draft snapshot for conversation continuity or start a clean test session.</p>
              <div className="mt-2 flex gap-2">
                <button type="button" onClick={() => setPinnedPreviousSnapshot(true)} className="rounded-lg border border-amber-500/25 px-2 py-1.5 text-[9px] text-amber-100">Keep previous</button>
                <button type="button" onClick={startNewSession} className="rounded-lg bg-primary px-2 py-1.5 text-[9px] font-semibold text-white">Start new session</button>
              </div>
            </div>
          </div>
        )}
        {pinnedPreviousSnapshot && (
          <div className="mt-3 rounded-lg border border-border bg-background/40 px-3 py-2 text-[9px] text-muted">
            This session remains pinned to the previous Agent Draft snapshot.
          </div>
        )}
      </div>

      <ChatCanvas
        messages={messages}
        isSending={isSending}
        onSend={handleSend}
        agentName={agent.name}
        runtimeBlocked={isInactive}
        runtimeBlockReason={runtimeBlockReason}
      />
    </div>
  )
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
  const [testCompleted, setTestCompleted] = useState(false)
  const { isDirty, loadedReleaseVersion } = useAgentEditor()

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-border/80 bg-background/20 px-3 py-3">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
            <Bot className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="truncate text-xs font-semibold text-white">{agent.name}</p>
              <span className={cn('rounded-md border px-1.5 py-0.5 text-[8px] font-semibold uppercase', agent.status === 'inactive' ? 'border-red-500/30 bg-red-500/10 text-red-300' : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300')}>
                {agent.status || 'active'}
              </span>
              <span className="rounded-md border border-border bg-background/50 px-1.5 py-0.5 text-[8px] font-semibold uppercase text-muted">
                {agent.session_mode === 'stateless' ? 'stateless' : 'stateful'}
              </span>
            </div>
            <p className="mt-1 truncate text-[9px] text-muted">{agent.provider || 'No provider'}/{agent.model || 'No model'}</p>
          </div>
        </div>

        <div className="mt-3 rounded-xl border border-primary/20 bg-primary/[0.045] p-3">
          <div className="flex items-start gap-2">
            <GitBranch className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary-light" />
            <div className="min-w-0 flex-1">
              <p className="text-[9px] font-semibold uppercase tracking-wide text-primary-light">Network binding</p>
              <p className="mt-1 text-[10px] text-white">This Network uses {sourceLabel(networkBinding.source)} <span className="font-mono">{networkBinding.version}</span></p>
              <p className="mt-1 text-[9px] leading-4 text-muted">
                Editing or testing {loadedReleaseVersion ? `the Draft based on ${loadedReleaseVersion}` : 'the current Draft'} does not change this binding.
              </p>
            </div>
            <button type="button" onClick={onOpenComposition} className="shrink-0 text-[9px] font-medium text-primary-light hover:text-white">Open Composition</button>
          </div>
        </div>
      </div>

      <AgentWorkspaceOnboarding isDirty={isDirty} testCompleted={testCompleted} />

      <div className="flex gap-1 border-b border-border/80 bg-surface/60 p-1.5">
        {([
          ['editor', 'Editor', Edit3],
          ['versions', 'Versions', Rocket],
          ['test', 'Test', MessageSquare],
        ] as Array<[AgentWorkspaceTab, string, typeof Edit3]>).map(([id, label, Icon]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={cn(
              'flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-2 py-2 text-[10px] font-medium',
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

      <div className={cn('flex min-h-0 flex-1 flex-col', tab !== 'editor' && 'hidden')}>
        <AgentEditorWorkspace
          agent={agent}
          projectId={projectId}
          agentId={agent.id}
          compact
          onDirtyChange={onDirtyChange}
          onRegisterSaveAction={onRegisterSaveAction}
        />
      </div>
      <div className={cn('versions-tab-compact min-h-0 flex-1', tab !== 'versions' && 'hidden')}>
        <ReleaseTab agentId={agent.id} projectId={projectId} />
      </div>
      <div className={cn('flex min-h-0 flex-1 flex-col', tab !== 'test' && 'hidden')}>
        <AgentTestPanel agent={agent} projectId={projectId} onTestCompleted={() => setTestCompleted(true)} />
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
