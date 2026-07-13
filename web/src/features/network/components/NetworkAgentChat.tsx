import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, ArrowRight, Bot, MessageSquare, RotateCcw, Send, Square, User } from 'lucide-react'
import { toast } from 'sonner'

import type { Agent } from '@/features/agents/types'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { useAskStream } from '@/features/playground/hooks'
import type { AskResponse, ChatMessage as ChatMessageType, SourceInfo, ToolCallInfo, UsageInfo } from '@/features/playground/types'
import { formatLatency, formatNumber } from '@/lib/formatters/number'
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
  const index = next.tool_call_id ? items.findIndex((item) => item.tool_call_id === next.tool_call_id) : -1
  if (index === -1) return [...items, next]
  items[index] = { ...items[index], ...next, input: next.input ?? items[index].input, output: next.output ?? items[index].output }
  return items
}

function ChatDetails({ message }: { message: ChatMessageType }) {
  const hasDetails = Boolean(
    message.tool_calls?.length
    || message.sources?.length
    || message.usage
    || message.trace_id
    || message.latency_ms != null
    || message.parsed_output,
  )
  if (!hasDetails) return null

  return (
    <details className="mt-1.5 rounded-md border border-border/70 bg-background/35 px-2 py-1.5">
      <summary className="cursor-pointer select-none text-[8px] font-medium text-muted hover:text-white">Execution details</summary>
      <div className="mt-2 space-y-2 text-[9px] text-muted">
        {message.parsed_output && <pre className="scrollbar-thin max-h-52 overflow-auto rounded-md border border-border/70 bg-black/15 p-2 font-mono text-[9px] leading-4 text-slate-300">{JSON.stringify(message.parsed_output, null, 2)}</pre>}
        {message.tool_calls && message.tool_calls.length > 0 && (
          <div><p className="mb-1 font-medium text-slate-300">Tools</p>{message.tool_calls.map((tool, index) => <div key={tool.tool_call_id || `${tool.tool_name}-${index}`} className="mb-1 rounded-md border border-border/70 bg-background/45 p-2"><div className="flex items-center justify-between gap-2"><span className="truncate text-white">{tool.tool_name}</span><span className={tool.success === false ? 'text-red-300' : tool.status === 'running' ? 'text-amber-300' : 'text-emerald-300'}>{tool.status || (tool.success === false ? 'failed' : 'completed')}</span></div>{tool.error && <p className="mt-1 text-red-300">{tool.error}</p>}</div>)}</div>
        )}
        {message.sources && message.sources.length > 0 && (
          <div><p className="mb-1 font-medium text-slate-300">Sources</p>{message.sources.map((source: SourceInfo, index: number) => <div key={source.chunk_id || `${source.document_id}-${index}`} className="mb-1 rounded-md border border-border/70 bg-background/45 p-2"><p className="truncate text-white">{source.document_title || 'Untitled document'}</p>{source.content_preview && <p className="mt-1 line-clamp-3 leading-4">{source.content_preview}</p>}</div>)}</div>
        )}
        <div className="flex flex-wrap gap-x-3 gap-y-1 border-t border-border/60 pt-2">
          {message.model && <span>{message.provider || ''}/{message.model}</span>}
          {message.latency_ms != null && <span>{formatLatency(message.latency_ms)}</span>}
          {message.usage && <span>{formatNumber(message.usage.input_tokens, 0)} in · {formatNumber(message.usage.output_tokens, 0)} out</span>}
          {message.trace_id && <span className="font-mono">trace {message.trace_id.slice(0, 8)}…</span>}
        </div>
      </div>
    </details>
  )
}

function MessageRow({ message, agentName, streaming }: { message: ChatMessageType; agentName: string; streaming: boolean }) {
  const user = message.role === 'user'
  return (
    <div className={cn('flex gap-2', user ? 'justify-end' : 'justify-start')}>
      {!user && <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-border bg-surface"><Bot className="h-3 w-3 text-primary-light" /></div>}
      <div className={cn('min-w-0 max-w-[calc(100%-34px)]', user ? 'max-w-[88%]' : 'flex-1')}>
        {!user && <p className="mb-1 truncate text-[8px] font-medium text-muted">{agentName}</p>}
        <div className={cn('rounded-lg border px-2.5 py-2 text-[10px] leading-4 text-white', user ? 'rounded-br-sm border-primary/30 bg-primary/12' : 'rounded-bl-sm border-border/80 bg-surface/70')}>
          {message.parsed_output && !streaming ? (
            <pre className="scrollbar-thin max-h-64 overflow-auto whitespace-pre-wrap break-words font-mono text-[9px] leading-4">{JSON.stringify(message.parsed_output, null, 2)}</pre>
          ) : message.content ? (
            <p className="whitespace-pre-wrap break-words">{message.content}{streaming && <span className="ml-1 inline-block h-3 w-1 animate-pulse rounded-sm bg-primary" />}</p>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-muted"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />{message.activity?.message || 'Working…'}</span>
          )}
        </div>
        {message.output_parse_error && <div className="mt-1.5 flex items-start gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1.5 text-[9px] leading-4 text-amber-200"><AlertCircle className="mt-0.5 h-3 w-3 shrink-0" />{message.output_parse_error}</div>}
        {!user && !streaming && <ChatDetails message={message} />}
      </div>
      {user && <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-primary/25 bg-primary/10"><User className="h-3 w-3 text-primary-light" /></div>}
    </div>
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
  const messagesRef = useRef<HTMLDivElement>(null)
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

  const updateLastAssistant = useCallback((updater: (message: ChatMessageType) => ChatMessageType) => {
    setMessages((previous) => {
      const next = [...previous]
      const last = next[next.length - 1]
      if (last?.role === 'assistant') next[next.length - 1] = updater(last)
      return next
    })
  }, [])

  useEffect(() => {
    if (isStateless && sessionId) setSessionId(null)
  }, [isStateless, sessionId])

  useLayoutEffect(() => {
    const element = messagesRef.current
    if (!element || !shouldStickRef.current) return
    element.scrollTop = element.scrollHeight
  }, [messages, isSending])

  const startNewChat = useCallback(() => {
    cancel()
    setMessages([])
    setSessionId(null)
    setSessionSnapshot(currentSnapshot)
    setPinnedPreviousSnapshot(false)
    setInput('')
    accumulatedRef.current = ''
    metadataRef.current = {}
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    toast.success('New isolated Agent chat started')
  }, [cancel, currentSignature])

  const send = async (rawContent?: string) => {
    const content = (rawContent ?? input).trim()
    if (!content || isSending || isInactive) return
    if (configurationChanged && !pinnedPreviousSnapshot) {
      toast.warning('Start a new Chat or keep the previous Draft snapshot before sending')
      return
    }

    const snapshot = effectiveSnapshot
    if (!sessionSnapshot) setSessionSnapshot(snapshot)
    accumulatedRef.current = ''
    metadataRef.current = {}
    setMessages((previous) => [...previous, { role: 'user', content }, { role: 'assistant', content: '', activity: { status: 'working', message: 'Working…' } }])
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
          if (info.content_length > 0) accumulatedRef.current = accumulatedRef.current.slice(0, Math.max(0, accumulatedRef.current.length - info.content_length))
          updateLastAssistant((last) => ({ ...last, content: accumulatedRef.current, activity: { status: 'planning_tools', message: 'Checking Tools…' } }))
        },
        onInternalToken: () => undefined,
        onSources: (sources) => { metadataRef.current.sources = sources },
        onToolCallStarted: (tool) => updateLastAssistant((last) => ({ ...last, activity: { status: 'calling_tool', message: `Calling ${tool.tool_name}…`, tool_name: tool.tool_name }, tool_calls: upsertToolCall(last.tool_calls, { ...tool, status: tool.status || 'running' }) })),
        onToolCallCompleted: (tool) => updateLastAssistant((last) => ({ ...last, activity: { status: 'processing_tool_result', message: 'Processing Tool result…', tool_name: tool.tool_name }, tool_calls: upsertToolCall(last.tool_calls, tool) })),
        onFallback: (info) => {
          accumulatedRef.current = ''
          updateLastAssistant((last) => ({ ...last, content: '', activity: { status: 'working', message: 'Trying fallback model…' } }))
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
          if (finalContent.trim() && !response.output_parse_error) onChatCompleted()
        },
        onError: (error) => {
          toast.error(error.message)
          updateLastAssistant((last) => ({ ...last, activity: null, content: last.content || `Error: ${error.message}`, output_parse_error: error.message, trace_id: metadataRef.current.trace_id ?? null }))
        },
      })
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) toast.error(error instanceof Error ? error.message : 'Agent Chat failed')
    } finally {
      setIsSending(false)
    }
  }

  const handleInput = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(event.target.value)
    event.target.style.height = 'auto'
    event.target.style.height = `${Math.min(event.target.scrollHeight, 96)}px`
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background">
      <div className="flex shrink-0 items-center gap-2 border-b border-border/80 bg-background/25 px-2.5 py-2">
        <MessageSquare className="h-3.5 w-3.5 shrink-0 text-primary-light" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2"><p className="text-[10px] font-semibold text-white">Isolated Chat</p><span className={cn('rounded border px-1.5 py-0.5 text-[8px] font-semibold uppercase', isDirty ? 'border-amber-500/30 bg-amber-500/10 text-amber-300' : 'border-blue-500/30 bg-blue-500/10 text-blue-300')}>{isDirty ? 'Draft preview' : 'Current Draft'}</span></div>
          <p className="mt-0.5 truncate text-[8px] text-muted">Only {agent.name} runs. Network composition remains unchanged.</p>
        </div>
        <button type="button" onClick={startNewChat} className="flex shrink-0 items-center gap-1 rounded-md border border-border/80 bg-background/40 px-2 py-1 text-[8px] text-muted hover:text-white"><RotateCcw className="h-3 w-3" />New</button>
      </div>

      <div ref={messagesRef} onScroll={(event) => { shouldStickRef.current = nearBottom(event.currentTarget) }} className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain p-3">
        {messages.length === 0 ? (
          <div className="flex min-h-full flex-col items-center justify-center px-3 py-4 text-center">
            <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-xl border border-primary/25 bg-primary/10"><Bot className="h-4 w-4 text-primary-light" /></div>
            <h2 className="text-[12px] font-semibold text-white">Chat with {agent.name}</h2>
            <p className="mt-1 max-w-sm text-[9px] leading-4 text-muted">Validate the current Agent Draft in isolation.</p>
            {isInactive ? <div className="mt-3 rounded-lg border border-red-500/25 bg-red-500/5 px-3 py-2 text-[9px] text-red-200">This Agent is inactive. Activate it before using Chat.</div> : (
              <div className="mt-3 grid w-full max-w-sm gap-1.5">
                {suggestions.map((suggestion) => <button key={suggestion} type="button" onClick={() => void send(suggestion)} className="group flex items-center justify-between gap-2 rounded-lg border border-border/80 bg-surface/45 px-3 py-2 text-left text-[9px] leading-4 text-muted hover:border-primary/30 hover:text-white"><span>{suggestion}</span><ArrowRight className="h-3 w-3 shrink-0 transition-transform group-hover:translate-x-0.5" /></button>)}
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {messages.map((message, index) => <MessageRow key={index} message={message} agentName={agent.name} streaming={message.role === 'assistant' && isSending && index === messages.length - 1} />)}
          </div>
        )}
      </div>

      {configurationChanged && !pinnedPreviousSnapshot && (
        <div className="flex shrink-0 items-center gap-2 border-t border-amber-500/20 bg-amber-500/[0.055] px-2.5 py-2 text-[8px] text-amber-100">
          <AlertCircle className="h-3.5 w-3.5 shrink-0 text-amber-400" />
          <span className="min-w-0 flex-1 truncate">Draft changed during this Chat.</span>
          <button type="button" onClick={() => setPinnedPreviousSnapshot(true)} className="shrink-0 font-medium text-amber-200 hover:text-white">Keep snapshot</button>
          <button type="button" onClick={startNewChat} className="shrink-0 rounded bg-primary px-2 py-1 font-medium text-white">New Chat</button>
        </div>
      )}
      {pinnedPreviousSnapshot && <div className="shrink-0 border-t border-border/70 bg-background/35 px-2.5 py-1.5 text-[8px] text-muted">This Chat remains pinned to its previous Draft snapshot.</div>}

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
            disabled={isInactive || isSending}
            placeholder={isInactive ? 'Agent inactive' : 'Message this Agent…'}
            className="max-h-24 min-h-[38px] w-full resize-none bg-transparent px-3 py-2 text-[10px] leading-4 text-white outline-none placeholder:text-muted"
          />
          <div className="flex items-center justify-between border-t border-border/60 px-2 py-1.5">
            <span className="text-[8px] text-muted">{isStateless ? 'Stateless' : sessionId ? `Session ${sessionId.slice(0, 8)}…` : 'Stateful · new session'}</span>
            {isSending ? (
              <button type="button" onClick={cancel} className="flex h-7 w-7 items-center justify-center rounded-md border border-red-500/30 bg-red-500/10 text-red-200" aria-label="Stop"><Square className="h-3 w-3 fill-current" /></button>
            ) : (
              <button type="button" onClick={() => void send()} disabled={!input.trim() || isInactive} className="flex h-7 w-7 items-center justify-center rounded-md border border-primary/35 bg-primary text-white disabled:border-border disabled:bg-surface disabled:text-muted disabled:opacity-50" aria-label="Send"><Send className="h-3.5 w-3.5" /></button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
