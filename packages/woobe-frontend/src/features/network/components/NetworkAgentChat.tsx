import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import {
  AlertCircle,
  ArrowRight,
  Bot,
  Check,
  History,
  Loader2,
  MessageSquare,
  RotateCcw,
  Send,
  Square,
} from 'lucide-react'
import { toast } from 'sonner'

import type { Agent } from '@/features/agents/types'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { ChatMessage } from '@/features/playground/components/ChatMessage'
import { useAgentSessions, useAskStream, useSessionMessages } from '@/features/playground/hooks'
import type {
  AskResponse,
  ChatMessage as ChatMessageType,
  Message as PersistedMessage,
  SessionListItem,
  ToolCallInfo,
  UsageInfo,
} from '@/features/playground/types'
import { cn } from '@/lib/utils'

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
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'w-full rounded-lg border px-2.5 py-2 text-left transition-colors',
        current
          ? 'border-primary/35 bg-primary/10'
          : 'border-border/75 bg-background/45 hover:border-primary/25 hover:bg-background/70',
      )}
    >
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className={cn('truncate text-[9px]', current ? 'font-medium text-white' : 'text-slate-200')}>
            {formatSessionDate(session.last_message_at || session.created_at)}
          </p>
          <p className="mt-0.5 text-[8px] text-muted">
            {session.message_count} {session.message_count === 1 ? 'message' : 'messages'} · {session.id.slice(0, 8)}…
          </p>
        </div>
        {current && <Check className="mt-0.5 h-3 w-3 shrink-0 text-primary-light" />}
      </div>
    </button>
  )
}

function nearBottom(element: HTMLDivElement) {
  return element.scrollHeight - element.scrollTop - element.clientHeight < 48
}

export function NetworkAgentChat({ agent, projectId, onChatCompleted }: NetworkAgentChatProps) {
  const { toSnapshot, isDirty } = useAgentEditor()
  const { stream, cancel } = useAskStream()
  const [messages, setMessages] = useState<ChatMessageType[]>([])
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessionSnapshot, setSessionSnapshot] = useState<Record<string, unknown> | null>(null)
  const [pinnedPreviousSnapshot, setPinnedPreviousSnapshot] = useState(false)
  const [sessionsOpen, setSessionsOpen] = useState(false)
  const [sessionToLoad, setSessionToLoad] = useState<string | null>(null)
  const [historicalSessionPending, setHistoricalSessionPending] = useState(false)
  const messagesRef = useRef<HTMLDivElement>(null)
  const sessionMenuRef = useRef<HTMLDivElement>(null)
  const shouldStickRef = useRef(true)
  const accumulatedRef = useRef('')
  const metadataRef = useRef<Partial<AskResponse>>({})
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const currentSnapshot = toSnapshot()
  const currentSignature = JSON.stringify(currentSnapshot)
  const sessionSignature = sessionSnapshot ? JSON.stringify(sessionSnapshot) : null
  const configurationChanged = Boolean(sessionSignature && currentSignature !== sessionSignature)
  const isStateless = agent.session_mode === 'stateless'
  const isInactive = agent.status === 'inactive'
  const effectiveSnapshot = pinnedPreviousSnapshot && sessionSnapshot ? sessionSnapshot : currentSnapshot
  const suggestions = useMemo(() => suggestionsForAgent(agent), [agent])

  const sessionsQuery = useAgentSessions(
    isStateless ? undefined : agent.id,
    isStateless ? undefined : projectId,
  )
  const sessions = useMemo(() => {
    const byId = new Map<string, SessionListItem>()
    for (const page of sessionsQuery.data?.pages ?? []) {
      for (const item of page.items) {
        if (!byId.has(item.id)) byId.set(item.id, item)
      }
    }
    return Array.from(byId.values())
  }, [sessionsQuery.data])
  const historyQuery = useSessionMessages(sessionToLoad ?? undefined)

  const updateLastAssistant = useCallback((updater: (message: ChatMessageType) => ChatMessageType) => {
    setMessages((previous) => {
      const next = [...previous]
      const last = next[next.length - 1]
      if (last?.role === 'assistant') next[next.length - 1] = updater(last)
      return next
    })
  }, [])

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
    setSessionId(sessionToLoad)
    setSessionSnapshot(null)
    setPinnedPreviousSnapshot(false)
    setHistoricalSessionPending(true)
    setSessionToLoad(null)
    shouldStickRef.current = true
  }, [historyQuery.data, historyQuery.isFetching, sessionToLoad])

  useEffect(() => {
    if (!isStateless) return
    setSessionsOpen(false)
    setSessionToLoad(null)
    setSessionId(null)
    setHistoricalSessionPending(false)
  }, [isStateless])

  useLayoutEffect(() => {
    const element = messagesRef.current
    if (!element || !shouldStickRef.current) return
    element.scrollTop = element.scrollHeight
  }, [messages, isSending])

  const startNewChat = useCallback(() => {
    cancel()
    setMessages([])
    setSessionId(null)
    setSessionToLoad(null)
    setSessionSnapshot(currentSnapshot)
    setPinnedPreviousSnapshot(false)
    setHistoricalSessionPending(false)
    setSessionsOpen(false)
    setInput('')
    accumulatedRef.current = ''
    metadataRef.current = {}
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    toast.success('New isolated Agent chat started')
  }, [cancel, currentSignature])

  const selectSession = (nextSessionId: string) => {
    if (isSending || isStateless || nextSessionId === sessionId) {
      setSessionsOpen(false)
      return
    }
    cancel()
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

  const send = async (rawContent?: string) => {
    const content = (rawContent ?? input).trim()
    if (!content || isSending || isInactive || historicalSessionPending) return
    if (configurationChanged && !pinnedPreviousSnapshot) {
      toast.warning('Start a new Chat or keep the previous Draft snapshot before sending')
      return
    }

    const snapshot = effectiveSnapshot
    if (!sessionSnapshot) setSessionSnapshot(snapshot)
    accumulatedRef.current = ''
    metadataRef.current = {}
    setMessages((previous) => [
      ...previous,
      { role: 'user', content },
      { role: 'assistant', content: '', activity: { status: 'working', message: 'Working…' } },
    ])
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    setIsSending(true)

    try {
      await stream({
        project_id: projectId,
        agent_id: agent.id,
        message: content,
        session_id: isStateless ? null : sessionId,
        execution_context: 'playground',
        metadata: { source: 'network_agent_chat', client_sent_at: new Date().toISOString() },
        snapshot_override: snapshot,
      } as any, {
        onMeta: (meta) => {
          if (!isStateless && meta.session_id) setSessionId(meta.session_id)
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
          if (!isStateless && response.session_id) setSessionId(response.session_id)
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
          if (!isStateless) void sessionsQuery.refetch()
          if (finalContent.trim() && !response.output_parse_error) onChatCompleted()
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
        toast.error(error instanceof Error ? error.message : 'Agent Chat failed')
      }
    } finally {
      setIsSending(false)
    }
  }

  const handleInput = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(event.target.value)
    event.target.style.height = 'auto'
    event.target.style.height = `${Math.min(event.target.scrollHeight, 96)}px`
  }

  const restoringSession = Boolean(sessionToLoad)

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background">
      <div
        ref={sessionMenuRef}
        className="relative flex shrink-0 items-center gap-2 border-b border-border/80 bg-background/25 px-2.5 py-2"
      >
        <MessageSquare className="h-3.5 w-3.5 shrink-0 text-primary-light" />
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <p className="text-[10px] font-semibold text-white">Chat</p>
          <span
            className={cn(
              'rounded border px-1.5 py-0.5 text-[8px] font-semibold uppercase',
              isDirty
                ? 'border-amber-500/30 bg-amber-500/10 text-amber-300'
                : 'border-blue-500/30 bg-blue-500/10 text-blue-300',
            )}
          >
            {isDirty ? 'Draft preview' : 'Current Draft'}
          </span>
        </div>
        <button
          type="button"
          onClick={() => setSessionsOpen((open) => !open)}
          disabled={isStateless}
          title={isStateless ? 'Stateless Agents do not persist sessions' : 'Open previous sessions'}
          className="flex shrink-0 items-center gap-1 rounded-md border border-border/80 bg-background/40 px-2 py-1 text-[8px] text-muted hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          <History className="h-3 w-3" />
          Sessions
        </button>
        <button
          type="button"
          onClick={startNewChat}
          className="flex shrink-0 items-center gap-1 rounded-md border border-border/80 bg-background/40 px-2 py-1 text-[8px] text-muted hover:text-white"
        >
          <RotateCcw className="h-3 w-3" />
          New
        </button>

        {sessionsOpen && (
          <div className="absolute right-2 top-[calc(100%+6px)] z-50 flex max-h-[min(420px,65vh)] w-72 flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-2xl shadow-black/50">
            <div className="flex shrink-0 items-center border-b border-border/80 px-3 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="text-[10px] font-semibold text-white">Sessions</p>
                <p className="mt-0.5 text-[8px] text-muted">Previous conversations for this Agent</p>
              </div>
              {sessionsQuery.isFetching && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted" />}
            </div>
            <div className="scrollbar-thin min-h-0 flex-1 space-y-1.5 overflow-y-auto p-2">
              {sessionsQuery.isLoading && sessions.length === 0 ? (
                <div className="flex items-center justify-center gap-2 py-8 text-[9px] text-muted">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Loading sessions…
                </div>
              ) : sessions.length === 0 ? (
                <div className="py-8 text-center">
                  <History className="mx-auto h-5 w-5 text-muted" />
                  <p className="mt-2 text-[9px] text-white">No previous sessions</p>
                  <p className="mt-1 text-[8px] text-muted">Start a Chat to create the first session.</p>
                </div>
              ) : sessions.map((session) => (
                <SessionItem
                  key={session.id}
                  session={session}
                  current={session.id === sessionId}
                  onSelect={() => selectSession(session.id)}
                />
              ))}
              {sessionsQuery.hasNextPage && (
                <button
                  type="button"
                  onClick={() => void sessionsQuery.fetchNextPage()}
                  disabled={sessionsQuery.isFetchingNextPage}
                  className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-border/75 bg-background/35 px-2 py-2 text-[8px] text-muted hover:text-white disabled:opacity-50"
                >
                  {sessionsQuery.isFetchingNextPage && <Loader2 className="h-3 w-3 animate-spin" />}
                  Load more
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      <div
        ref={messagesRef}
        onScroll={(event) => { shouldStickRef.current = nearBottom(event.currentTarget) }}
        className="scrollbar-thin min-h-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-contain p-3"
      >
        {restoringSession ? (
          <div className="flex min-h-full items-center justify-center gap-2 text-[9px] text-muted">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading session…
          </div>
        ) : messages.length === 0 ? (
          <div className="flex min-h-full flex-col items-center justify-center px-3 py-4 text-center">
            <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-xl border border-primary/25 bg-primary/10">
              <Bot className="h-4 w-4 text-primary-light" />
            </div>
            <h2 className="text-[12px] font-semibold text-white">Chat with {agent.name}</h2>
            <p className="mt-1 max-w-sm text-[9px] leading-4 text-muted">Validate the current Agent Draft in isolation.</p>
            {isInactive ? (
              <div className="mt-3 rounded-lg border border-red-500/25 bg-red-500/5 px-3 py-2 text-[9px] text-red-200">
                This Agent is inactive. Activate it before using Chat.
              </div>
            ) : (
              <div className="mt-3 grid w-full max-w-sm gap-1.5">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => void send(suggestion)}
                    className="group flex items-center justify-between gap-2 rounded-lg border border-border/80 bg-surface/45 px-3 py-2 text-left text-[9px] leading-4 text-muted hover:border-primary/30 hover:text-white"
                  >
                    <span>{suggestion}</span>
                    <ArrowRight className="h-3 w-3 shrink-0 transition-transform group-hover:translate-x-0.5" />
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message, index) => (
              <ChatMessage
                key={`${message.created_at || 'live'}-${index}`}
                message={message}
                isStreaming={message.role === 'assistant' && isSending && index === messages.length - 1}
                isLast={index === messages.length - 1}
                agentName={agent.name}
                variant="network"
              />
            ))}
          </div>
        )}
      </div>

      {historicalSessionPending && (
        <div className="flex shrink-0 items-center gap-2 border-t border-blue-500/20 bg-blue-500/[0.055] px-2.5 py-2 text-[8px] text-blue-100">
          <History className="h-3.5 w-3.5 shrink-0 text-blue-300" />
          <span className="min-w-0 flex-1">Historical session loaded. Continuing uses the current Agent Draft.</span>
          <button type="button" onClick={startNewChat} className="shrink-0 font-medium text-muted hover:text-white">Start new</button>
          <button type="button" onClick={continueHistoricalSession} className="shrink-0 rounded bg-primary px-2 py-1 font-medium text-white">Continue</button>
        </div>
      )}

      {configurationChanged && !pinnedPreviousSnapshot && !historicalSessionPending && (
        <div className="flex shrink-0 items-center gap-2 border-t border-amber-500/20 bg-amber-500/[0.055] px-2.5 py-2 text-[8px] text-amber-100">
          <AlertCircle className="h-3.5 w-3.5 shrink-0 text-amber-400" />
          <span className="min-w-0 flex-1 truncate">Draft changed during this Chat.</span>
          <button type="button" onClick={() => setPinnedPreviousSnapshot(true)} className="shrink-0 font-medium text-amber-200 hover:text-white">Keep snapshot</button>
          <button type="button" onClick={startNewChat} className="shrink-0 rounded bg-primary px-2 py-1 font-medium text-white">New Chat</button>
        </div>
      )}
      {pinnedPreviousSnapshot && (
        <div className="shrink-0 border-t border-border/70 bg-background/35 px-2.5 py-1.5 text-[8px] text-muted">
          This Chat remains pinned to its previous Draft snapshot.
        </div>
      )}

      <div className="shrink-0 border-t border-border/80 bg-surface/65 p-2.5">
        <div className="rounded-lg border border-border/90 bg-background/70 focus-within:border-primary/35 focus-within:ring-1 focus-within:ring-primary/10">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void send()
              }
            }}
            rows={1}
            disabled={isInactive || isSending || historicalSessionPending}
            placeholder={isInactive ? 'Agent inactive' : historicalSessionPending ? 'Choose Continue or Start new' : 'Message this Agent…'}
            className="max-h-24 min-h-[38px] w-full resize-none bg-transparent px-3 py-2 text-[10px] leading-4 text-white outline-none placeholder:text-muted"
          />
          <div className="flex items-center justify-end border-t border-border/60 px-2 py-1.5">
            {isSending ? (
              <button
                type="button"
                onClick={() => { cancel() }}
                className="flex h-7 w-7 items-center justify-center rounded-md border border-red-500/30 bg-red-500/10 text-red-200"
                aria-label="Stop"
              >
                <Square className="h-3 w-3 fill-current" />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void send()}
                disabled={!input.trim() || isInactive || historicalSessionPending}
                className="flex h-7 w-7 items-center justify-center rounded-md border border-primary/35 bg-primary text-white disabled:border-border disabled:bg-surface disabled:text-muted disabled:opacity-50"
                aria-label="Send"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
