import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Check, History, Loader2, MessageSquare, RotateCcw } from 'lucide-react'
import { Badge, Button, EmptyStatePanel, TechnicalListItem } from '@woobe/ui'
import { toast } from 'sonner'

import type { Agent } from '@/features/agents/types'
import { filterContractValues, filterExternalContextInput } from '@/features/contracts/contractFields'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { ChatCanvas } from '@/features/playground/components/ChatCanvas'
import { useAgentSessions, useAskStream, useSessionMessages } from '@/features/playground/hooks'
import { getActiveAgentRun } from '@/features/playground/reattach-api'
import type { StreamCallbacks } from '@/features/playground/stream-client'
import type {
  AskResponse,
  ChatMessage as ChatMessageType,
  Message as PersistedMessage,
  SessionListItem,
  ToolCallInfo,
  UsageInfo,
} from '@/features/playground/types'
import {
  getStoredNetworkAgentRunId,
  getStoredNetworkAgentSessionId,
  setStoredNetworkAgentRunId,
  setStoredNetworkAgentSessionId,
} from './networkAgentChatRuntimeStore'

interface NetworkAgentChatProps {
  agent: Agent
  projectId: string
  onChatCompleted: () => void
}

function suggestionsForAgent(agent: Agent): string[] {
  const identity = `${agent.name} ${agent.description || ''}`.toLowerCase()
  if (/billing|invoice|payment|refund|subscription/.test(identity)) {
    return ['I was charged twice for the same invoice.', 'Explain how you would handle a refund request.']
  }
  if (/technical|support|api|incident|error/.test(identity)) {
    return ['The API is returning a 504 timeout.', 'Explain the first diagnostic steps for an incident.']
  }
  if (/coordinator|router|manager|orchestrat/.test(identity)) {
    return ['Classify a billing request and choose the right specialist.', 'Explain how you decide when to hand off a request.']
  }
  return ['Introduce yourself and explain your role.', 'Respond to a typical request for this Agent.']
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

function formatSessionDate(value: string | null) {
  if (!value) return 'No messages yet'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown date'
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function persistedMessageToChat(message: PersistedMessage): ChatMessageType {
  const data = message.data ?? {}
  return {
    role: message.role === 'user' ? 'user' : 'assistant',
    content: message.content,
    usage: message.input_tokens != null
      ? {
          input_tokens: message.input_tokens,
          output_tokens: message.output_tokens ?? null,
          cost_usd: message.cost_usd ?? null,
        }
      : null,
    tool_calls: (data.tool_calls ?? null) as ChatMessageType['tool_calls'],
    sources: (data.sources ?? null) as ChatMessageType['sources'],
    model: typeof data.model === 'string' ? data.model : null,
    provider: typeof data.provider === 'string' ? data.provider : null,
    latency_ms: typeof data.latency_ms === 'number' ? data.latency_ms : null,
    trace_id: typeof data.trace_id === 'string' ? data.trace_id : null,
    parsed_output: data.parsed_output && typeof data.parsed_output === 'object'
      ? data.parsed_output as Record<string, unknown>
      : null,
    output_parse_error: typeof data.output_parse_error === 'string' ? data.output_parse_error : null,
    created_at: message.created_at,
  }
}

function SessionItem({
  session,
  current,
  onSelect,
}: {
  session: SessionListItem
  current: boolean
  onSelect: () => void
}) {
  return (
    <TechnicalListItem
      label={formatSessionDate(session.last_message_at || session.created_at)}
      description={`${session.message_count} ${session.message_count === 1 ? 'message' : 'messages'}`}
      meta={`${session.id.slice(0, 8)}…`}
      selected={current}
      trailing={current ? <Check className="h-icon-sm w-icon-sm text-primary-light" /> : null}
      onClick={onSelect}
    />
  )
}

export function NetworkAgentChat({ agent, projectId, onChatCompleted }: NetworkAgentChatProps) {
  const { toSnapshot, isDirty } = useAgentEditor()
  const { stream, reattach, cancel } = useAskStream()
  const isStateless = agent.session_mode === 'stateless'
  const isInactive = agent.status === 'inactive'
  const initialSessionId = getStoredNetworkAgentSessionId(projectId, agent.id)
  const [messages, setMessages] = useState<ChatMessageType[]>([])
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(() => initialSessionId)
  const [sessionSnapshot, setSessionSnapshot] = useState<Record<string, unknown> | null>(null)
  const [externalContextValues, setExternalContextValues] = useState<Record<string, unknown>>({})
  const [pinnedPreviousSnapshot, setPinnedPreviousSnapshot] = useState(false)
  const [sessionsOpen, setSessionsOpen] = useState(false)
  const [sessionToLoad, setSessionToLoad] = useState<string | null>(() => isStateless ? null : initialSessionId)
  const [historicalSessionPending, setHistoricalSessionPending] = useState(false)
  const sessionMenuRef = useRef<HTMLDivElement>(null)
  const accumulatedRef = useRef('')
  const metadataRef = useRef<Partial<AskResponse>>({})
  const activeRunIdRef = useRef<string | null>(getStoredNetworkAgentRunId(projectId, agent.id))
  const reattachingRunRef = useRef<string | null>(null)
  const finishedRunRef = useRef<string | null>(null)
  const mountedRef = useRef(true)

  const currentSnapshot = toSnapshot()
  const currentSignature = JSON.stringify(currentSnapshot)
  const sessionSignature = sessionSnapshot ? JSON.stringify(sessionSnapshot) : null
  const configurationChanged = Boolean(sessionSignature && currentSignature !== sessionSignature)
  const effectiveSnapshot = pinnedPreviousSnapshot && sessionSnapshot ? sessionSnapshot : currentSnapshot
  const externalContextContract = (
    effectiveSnapshot.external_context_contract
    && typeof effectiveSnapshot.external_context_contract === 'object'
    && !Array.isArray(effectiveSnapshot.external_context_contract)
      ? effectiveSnapshot.external_context_contract
      : {}
  )
  const suggestions = useMemo(() => suggestionsForAgent(agent), [agent])

  const sessionsQuery = useAgentSessions(agent.id, projectId)
  const sessions = useMemo(() => {
    const byId = new Map<string, SessionListItem>()
    for (const page of sessionsQuery.data?.pages ?? []) {
      for (const item of page.items) {
        if (!byId.has(item.id)) byId.set(item.id, item)
      }
    }
    return Array.from(byId.values())
  }, [sessionsQuery.data])
  const lockedExternalContextValues = useMemo(
    () => sessions.find((item) => item.id === sessionId)?.external_context_snapshot ?? {},
    [sessionId, sessions],
  )
  const handleExternalContextValuesChange = useCallback((values: Record<string, unknown>) => {
    setExternalContextValues(filterContractValues(externalContextContract, values))
  }, [externalContextContract])
  const clearExternalContextValues = useCallback(() => setExternalContextValues({}), [])

  useEffect(() => {
    setExternalContextValues((current) => filterContractValues(externalContextContract, current))
  }, [externalContextContract])
  const historyQuery = useSessionMessages(sessionToLoad ?? undefined)

  const rememberSessionId = useCallback((nextSessionId: string | null) => {
    setSessionId(nextSessionId)
    setStoredNetworkAgentSessionId(projectId, agent.id, nextSessionId)
  }, [agent.id, projectId])

  const rememberRunId = useCallback((runId: string | null) => {
    activeRunIdRef.current = runId
    setStoredNetworkAgentRunId(projectId, agent.id, runId)
  }, [agent.id, projectId])

  const finishActiveRun = useCallback(() => {
    if (activeRunIdRef.current) finishedRunRef.current = activeRunIdRef.current
    rememberRunId(null)
  }, [rememberRunId])

  const updateLastAssistant = useCallback((updater: (message: ChatMessageType) => ChatMessageType) => {
    setMessages((previous) => {
      const next = [...previous]
      const last = next[next.length - 1]
      if (last?.role === 'assistant') next[next.length - 1] = updater(last)
      return next
    })
  }, [])

  const runtimeCallbacks = useCallback((): StreamCallbacks => ({
    onMeta: (meta) => {
      if (meta.run_id) rememberRunId(meta.run_id)
      if (meta.session_id) rememberSessionId(meta.session_id)
      if (meta.trace_id) metadataRef.current.trace_id = meta.trace_id
    },
    onAgentActivity: (activity) => updateLastAssistant((last) => ({ ...last, activity })),
    onToken: (token) => {
      if (token.visibility !== 'assistant' || token.channel !== 'final') return
      accumulatedRef.current += token.content
      updateLastAssistant((last) => ({ ...last, content: accumulatedRef.current, activity: null }))
    },
    onTokenRetract: (info) => {
      if (info.content_length > 0) {
        accumulatedRef.current = accumulatedRef.current.slice(
          0,
          Math.max(0, accumulatedRef.current.length - info.content_length),
        )
      }
      updateLastAssistant((last) => ({
        ...last,
        content: accumulatedRef.current,
        activity: { status: 'planning_tools', message: 'Checking Tools…' },
      }))
    },
    onInternalToken: () => undefined,
    onSources: (sources) => { metadataRef.current.sources = sources },
    onToolCallStarted: (tool) => updateLastAssistant((last) => ({
      ...last,
      activity: {
        status: 'calling_tool',
        message: `Calling ${tool.tool_name}…`,
        tool_name: tool.tool_name,
      },
      tool_calls: upsertToolCall(last.tool_calls, { ...tool, status: tool.status || 'running' }),
    })),
    onToolCallCompleted: (tool) => updateLastAssistant((last) => ({
      ...last,
      activity: {
        status: 'processing_tool_result',
        message: 'Processing Tool result…',
        tool_name: tool.tool_name,
      },
      tool_calls: upsertToolCall(last.tool_calls, tool),
    })),
    onFallback: (info) => {
      accumulatedRef.current = ''
      updateLastAssistant((last) => ({
        ...last,
        content: '',
        activity: { status: 'working', message: 'Trying fallback model…' },
      }))
      toast.info(`Primary model failed. Retrying with ${info.fallback_provider}/${info.fallback_model}.`)
    },
    onDone: (response) => {
      const finalContent = response.answer || accumulatedRef.current || ''
      if (response.session_id) rememberSessionId(response.session_id)
      const usage = (response.usage ?? null) as UsageInfo | null
      setMessages((previous) => {
        const next = [...previous]
        const last = next[next.length - 1]
        if (last?.role === 'assistant') {
          next[next.length - 1] = {
            ...last,
            content: finalContent,
            activity: null,
            usage,
            sources: (response.sources ?? metadataRef.current.sources ?? null) as ChatMessageType['sources'],
            tool_calls: (response.tool_calls ?? last.tool_calls ?? null) as ChatMessageType['tool_calls'],
            model: response.model ?? null,
            provider: response.provider ?? null,
            latency_ms: response.latency_ms ?? null,
            trace_id: response.trace_id ?? metadataRef.current.trace_id ?? null,
            parsed_output: response.parsed_output ?? null,
            output_parse_error: response.output_parse_error ?? null,
          }
        }
        return next
      })
      finishActiveRun()
      void sessionsQuery.refetch()
      if (finalContent.trim() && !response.output_parse_error) onChatCompleted()
    },
    onError: (error) => {
      finishActiveRun()
      toast.error(error.message)
      updateLastAssistant((last) => ({
        ...last,
        activity: null,
        content: last.content || `Error: ${error.message}`,
        output_parse_error: error.message,
        trace_id: metadataRef.current.trace_id ?? null,
      }))
    },
    onCancelled: (event) => {
      const output = typeof event.output === 'string' ? event.output : accumulatedRef.current
      accumulatedRef.current = output
      finishActiveRun()
      updateLastAssistant((last) => ({
        ...last,
        content: output || last.content,
        activity: null,
      }))
      void sessionsQuery.refetch()
      toast.info('Agent Run cancelled')
    },
  }), [
    finishActiveRun,
    onChatCompleted,
    rememberRunId,
    rememberSessionId,
    sessionsQuery,
    updateLastAssistant,
  ])

  useEffect(() => () => {
    mountedRef.current = false
  }, [])

  useEffect(() => {
    const nextSessionId = getStoredNetworkAgentSessionId(projectId, agent.id)
    activeRunIdRef.current = getStoredNetworkAgentRunId(projectId, agent.id)
    reattachingRunRef.current = null
    finishedRunRef.current = null
    setMessages([])
    setSessionId(nextSessionId)
    setSessionToLoad(isStateless ? null : nextSessionId)
    setSessionSnapshot(null)
    setPinnedPreviousSnapshot(false)
    setHistoricalSessionPending(false)
    accumulatedRef.current = ''
    metadataRef.current = {}
  }, [agent.id, isStateless, projectId])

  useEffect(() => {
    if (!sessionsOpen) return
    const onPointerDown = (event: PointerEvent) => {
      if (!sessionMenuRef.current?.contains(event.target as Node)) setSessionsOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [sessionsOpen])

  useEffect(() => {
    if (!sessionToLoad || historyQuery.isFetching || !historyQuery.data) return
    setMessages(historyQuery.data.map(persistedMessageToChat))
    rememberSessionId(sessionToLoad)
    setSessionSnapshot(null)
    setPinnedPreviousSnapshot(false)
    setHistoricalSessionPending(true)
    setSessionToLoad(null)
  }, [historyQuery.data, historyQuery.isFetching, rememberSessionId, sessionToLoad])

  useEffect(() => {
    if (!isStateless) return
    setSessionsOpen(false)
    setSessionToLoad(null)
    setHistoricalSessionPending(false)
  }, [isStateless])

  useEffect(() => {
    if (sessionToLoad || historyQuery.isFetching || isSending || reattachingRunRef.current) return
    let disposed = false

    void (async () => {
      let runId = getStoredNetworkAgentRunId(projectId, agent.id)
      if (!runId && sessionId) {
        try {
          const active = await getActiveAgentRun(sessionId)
          if (active?.agent_id === agent.id) runId = active.run_id
        } catch {
          return
        }
      }
      if (!runId || disposed || finishedRunRef.current === runId) return

      reattachingRunRef.current = runId
      rememberRunId(runId)
      accumulatedRef.current = ''
      metadataRef.current = {}
      setHistoricalSessionPending(false)
      setMessages((current) => {
        const last = current[current.length - 1]
        if (last?.role === 'assistant') return current
        return [
          ...current,
          { role: 'assistant', content: '', activity: { status: 'working', message: 'Reattaching to active Run…' } },
        ]
      })
      setIsSending(true)
      let terminalObserved = false
      try {
        await reattach(runId, runtimeCallbacks())
        terminalObserved = true
      } catch (error) {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          toast.warning(error instanceof Error ? error.message : 'Active Agent Run reattach failed')
        }
      } finally {
        if (terminalObserved && reattachingRunRef.current === runId) {
          reattachingRunRef.current = null
        }
        if (mountedRef.current) setIsSending(false)
      }
    })()

    return () => { disposed = true }
  }, [
    agent.id,
    historyQuery.isFetching,
    isSending,
    projectId,
    reattach,
    rememberRunId,
    runtimeCallbacks,
    sessionId,
    sessionToLoad,
  ])

  const startNewChat = useCallback(() => {
    cancel()
    finishActiveRun()
    rememberSessionId(null)
    reattachingRunRef.current = null
    setMessages([])
    setSessionToLoad(null)
    setSessionSnapshot(currentSnapshot)
    setPinnedPreviousSnapshot(false)
    setHistoricalSessionPending(false)
    setSessionsOpen(false)
    setInput('')
    accumulatedRef.current = ''
    metadataRef.current = {}
    toast.success('New isolated Agent chat started')
  }, [cancel, currentSignature, finishActiveRun, rememberSessionId])

  const selectSession = (nextSessionId: string) => {
    if (isSending || isStateless || nextSessionId === sessionId) {
      setSessionsOpen(false)
      return
    }
    cancel()
    finishActiveRun()
    reattachingRunRef.current = null
    setSessionToLoad(nextSessionId)
    setMessages([])
    setHistoricalSessionPending(false)
    setSessionsOpen(false)
    accumulatedRef.current = ''
    metadataRef.current = {}
  }

  const continueHistoricalSession = () => {
    setHistoricalSessionPending(false)
    setSessionSnapshot(currentSnapshot)
    setPinnedPreviousSnapshot(false)
  }

  const send = async (rawContent: string) => {
    const content = rawContent.trim()
    if (!content || isSending || isInactive || historicalSessionPending) return
    if (configurationChanged && !pinnedPreviousSnapshot) {
      toast.warning('Start a new Chat or keep the previous Draft snapshot before sending')
      return
    }

    const snapshot = effectiveSnapshot
    if (!sessionSnapshot) setSessionSnapshot(snapshot)
    finishedRunRef.current = null
    rememberRunId(null)
    reattachingRunRef.current = null
    accumulatedRef.current = ''
    metadataRef.current = {}
    setMessages((previous) => [
      ...previous,
      { role: 'user', content },
      { role: 'assistant', content: '', activity: { status: 'working', message: 'Working…' } },
    ])
    setInput('')
    setIsSending(true)

    try {
      await stream({
        project_id: projectId,
        agent_id: agent.id,
        message: content,
        session_id: sessionId,
        execution_context: 'playground',
        external_context: filterExternalContextInput(
          externalContextContract,
          externalContextValues,
          lockedExternalContextValues,
        ),
        metadata: { source: 'network_agent_chat', client_sent_at: new Date().toISOString() },
        snapshot_override: snapshot,
      } as any, runtimeCallbacks())
      await sessionsQuery.refetch()
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) {
        toast.error(error instanceof Error ? error.message : 'Agent Chat failed')
      }
    } finally {
      setIsSending(false)
    }
  }

  const restoringSession = Boolean(sessionToLoad)
  const configurationBlocked = configurationChanged && !pinnedPreviousSnapshot && !historicalSessionPending
  const runtimeBlocked = isInactive || historicalSessionPending || configurationBlocked || restoringSession
  const runtimeBlockReason = isInactive
    ? 'This Agent is inactive. Activate it before using Chat.'
    : restoringSession
      ? 'Loading the selected session.'
      : historicalSessionPending
        ? 'Choose Continue or Start new before sending another message.'
        : configurationBlocked
          ? 'The Draft changed during this Chat. Keep the previous snapshot or start a new Chat.'
          : undefined

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background">
      <div
        ref={sessionMenuRef}
        className="relative flex shrink-0 items-center gap-ui-sm border-b border-border bg-background/25 px-ui-sm py-ui-sm"
      >
        <MessageSquare className="h-icon w-icon shrink-0 text-primary-light" />
        <div className="flex min-w-0 flex-1 items-center gap-ui-sm">
          <p className="font-mono text-system-control font-semibold text-accent-foreground">Chat</p>
          <Badge variant={isDirty ? 'warning' : 'default'} size="compact">
            {isDirty ? 'Draft preview' : 'Current Draft'}
          </Badge>
        </div>

        <Button
          type="button"
          variant="outline"
          size="xs"
          onClick={() => setSessionsOpen((value) => !value)}
          disabled={isStateless}
          title={isStateless ? 'Stateless Agents keep a technical Session but do not reuse conversation history' : 'Open previous sessions'}
        >
          <History className="h-icon-sm w-icon-sm" />
          Sessions
        </Button>
        <Button type="button" variant="outline" size="xs" onClick={startNewChat}>
          <RotateCcw className="h-icon-sm w-icon-sm" />
          New
        </Button>

        {sessionsOpen ? (
          <div className="absolute right-0 top-full z-popover mt-ui-xs flex max-h-popover w-dialog-sidebar flex-col overflow-hidden rounded-container border border-border bg-surface shadow-popup">
            <div className="flex shrink-0 items-center border-b border-border px-ui-md py-ui-sm">
              <div className="min-w-0 flex-1">
                <p className="font-mono text-system-control font-semibold text-accent-foreground">Sessions</p>
                <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Previous conversations for this Agent</p>
              </div>
              {sessionsQuery.isFetching ? <Loader2 className="h-icon w-icon animate-spin text-muted-foreground" /> : null}
            </div>

            <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-ui-sm">
              {sessionsQuery.isLoading && sessions.length === 0 ? (
                <div className="flex items-center justify-center gap-ui-sm py-ui-xl font-mono text-system-label text-muted-foreground">
                  <Loader2 className="h-icon w-icon animate-spin" />
                  Loading sessions…
                </div>
              ) : sessions.length === 0 ? (
                <EmptyStatePanel compact icon={<History className="h-icon-lg w-icon-lg" />} title="No previous sessions" description="Start a Chat to create the first session." />
              ) : (
                <div className="grid gap-ui-xs">
                  {sessions.map((session) => (
                    <SessionItem
                      key={session.id}
                      session={session}
                      current={session.id === sessionId}
                      onSelect={() => selectSession(session.id)}
                    />
                  ))}
                </div>
              )}

              {sessionsQuery.hasNextPage ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-ui-sm w-full"
                  onClick={() => void sessionsQuery.fetchNextPage()}
                  disabled={sessionsQuery.isFetchingNextPage}
                >
                  {sessionsQuery.isFetchingNextPage ? <Loader2 className="h-icon-sm w-icon-sm animate-spin" /> : null}
                  Load more
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      <ChatCanvas
        messages={messages}
        isSending={isSending}
        isSessionLoading={restoringSession}
        onSend={(content) => { void send(content) }}
        onStop={() => { cancel() }}
        agentName={agent.name}
        assistantIcon="bot"
        density="compact"
        runtimeBlocked={runtimeBlocked}
        runtimeBlockReason={runtimeBlockReason}
        emptyTitle={`Chat with ${agent.name}`}
        emptyDescription="Validate the current Agent Draft in isolation."
        suggestions={suggestions}
        composerValue={input}
        onComposerValueChange={setInput}
        composerPlaceholder="Message this Agent…"
        composerStatusText={isStateless ? 'Stateless isolated test · Session context preserved' : 'Session-aware isolated test'}
        enableFirstRunSuccess={false}
        externalContextContract={externalContextContract}
        externalContextValues={externalContextValues}
        lockedExternalContextValues={lockedExternalContextValues}
        onExternalContextValuesChange={handleExternalContextValuesChange}
        onClearExternalContextValues={clearExternalContextValues}
      />

      {historicalSessionPending ? (
        <div className="flex shrink-0 flex-wrap items-center gap-ui-sm border-t border-primary/20 bg-primary/[0.055] px-ui-sm py-ui-sm">
          <History className="h-icon w-icon shrink-0 text-primary-light" />
          <span className="min-w-0 flex-1 font-sans text-product-caption text-primary-light">Historical session loaded. Continuing uses the current Agent Draft.</span>
          <Button type="button" variant="ghost" size="xs" onClick={startNewChat}>Start new</Button>
          <Button type="button" size="xs" onClick={continueHistoricalSession}>Continue</Button>
        </div>
      ) : null}

      {configurationBlocked ? (
        <div className="flex shrink-0 flex-wrap items-center gap-ui-sm border-t border-warning/20 bg-warning/[0.055] px-ui-sm py-ui-sm">
          <span className="min-w-0 flex-1 font-sans text-product-caption text-warning">Draft changed during this Chat.</span>
          <Button type="button" variant="ghost" size="xs" onClick={() => setPinnedPreviousSnapshot(true)}>Keep snapshot</Button>
          <Button type="button" size="xs" onClick={startNewChat}>New Chat</Button>
        </div>
      ) : null}

      {pinnedPreviousSnapshot ? (
        <div className="shrink-0 border-t border-border bg-background/35 px-ui-sm py-ui-xs font-mono text-system-meta text-muted-foreground">
          This Chat remains pinned to its previous Draft snapshot.
        </div>
      ) : null}
    </div>
  )
}
