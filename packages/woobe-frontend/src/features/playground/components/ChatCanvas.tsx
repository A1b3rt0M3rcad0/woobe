import { Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { ArrowRight, Bot, CheckCircle2, Workflow } from 'lucide-react'
import { ChatMessage } from './ChatMessage'
import { ChatComposer } from './ChatComposer'
import { ScrollArea } from '@/components/ui/ScrollArea'
import {
  didCompleteFirstRun,
  isFirstRunSearch,
  removeFirstRunFromLocation,
} from '@/features/playground/lib/first-run'
import { useAgentStreamStopState } from '@/features/playground/stream-stop-state'
import type { ChatMessage as ChatMessageType } from '@/features/playground/types'

export interface ChatCanvasEntry {
  key?: string
  message: ChatMessageType
  agentName?: string
  assistantIcon?: 'bot' | 'network'
  isStreaming?: boolean
  details?: ReactNode
  footerMeta?: ReactNode
  footerActions?: ReactNode
  className?: string
}

interface ChatCanvasProps {
  messages?: ChatMessageType[]
  entries?: ChatCanvasEntry[]
  isSending: boolean
  isStopping?: boolean
  isPreparing?: boolean
  isSessionLoading?: boolean
  onSend: (content: string) => void
  onStop: () => void
  agentName?: string
  assistantIcon?: 'bot' | 'network'
  runtimeBlocked?: boolean
  runtimeBlockReason?: string
  emptyTitle?: string
  emptyDescription?: string
  suggestions?: string[]
  composerValue?: string
  onComposerValueChange?: (value: string) => void
  composerPlaceholder?: string
  composerStatusText?: string
  preparingText?: string
  enableFirstRunSuccess?: boolean
}

const defaultSuggestions = [
  'Introduce yourself and explain what you can help with.',
  'Respond to a typical user request.',
  'Explain your current role in one sentence.',
]

const BOTTOM_THRESHOLD_PX = 48

function isNearBottom(el: HTMLDivElement): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= BOTTOM_THRESHOLD_PX
}

function isEmptyTerminalAssistantPlaceholder(
  message: ChatMessageType,
  index: number,
  messages: ChatMessageType[],
  isSending: boolean,
): boolean {
  return !isSending
    && index === messages.length - 1
    && message.role === 'assistant'
    && !message.content.trim()
    && !message.activity
    && !message.output_parse_error
    && !message.parsed_output
    && !message.usage
    && !(message.tool_calls?.length)
    && !(message.sources?.length)
}

function SessionMessagesLoading() {
  return (
    <div className="relative flex h-full items-center justify-center px-6">
      <div className="w-full max-w-2xl space-y-4">
        <div className="flex justify-start gap-3">
          <div className="h-8 w-8 shrink-0 animate-pulse rounded-full border border-border bg-surface" />
          <div className="w-[72%] space-y-2 rounded-xl rounded-bl-md border border-border/80 bg-surface/70 px-4 py-3 shadow-sm shadow-black/5">
            <div className="h-3 w-1/2 animate-pulse rounded-full bg-white/[0.07]" />
            <div className="h-3 w-full animate-pulse rounded-full bg-white/[0.07]" />
            <div className="h-3 w-2/3 animate-pulse rounded-full bg-white/[0.07]" />
          </div>
        </div>
        <div className="flex justify-end gap-3">
          <div className="w-[52%] space-y-2 rounded-xl rounded-br-md border border-primary/20 bg-primary/10 px-4 py-3 shadow-sm shadow-black/5">
            <div className="ml-auto h-3 w-full animate-pulse rounded-full bg-white/[0.08]" />
            <div className="ml-auto h-3 w-2/3 animate-pulse rounded-full bg-white/[0.08]" />
          </div>
          <div className="h-8 w-8 shrink-0 animate-pulse rounded-full border border-primary/25 bg-primary/10" />
        </div>
        <p className="pt-2 text-center text-xs font-medium text-muted">Loading session messages...</p>
      </div>
    </div>
  )
}

export function ChatCanvas({
  messages,
  entries,
  isSending,
  isStopping,
  isPreparing = false,
  isSessionLoading = false,
  onSend,
  onStop,
  agentName,
  assistantIcon = 'bot',
  runtimeBlocked = false,
  runtimeBlockReason,
  emptyTitle = 'Test your Agent',
  emptyDescription = 'Your model and provider are ready. Send a message to validate the current Draft.',
  suggestions = defaultSuggestions,
  composerValue,
  onComposerValueChange,
  composerPlaceholder,
  composerStatusText,
  preparingText,
  enableFirstRunSuccess = true,
}: ChatCanvasProps) {
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const messagesContentRef = useRef<HTMLDivElement>(null)
  const shouldStickToBottomRef = useRef(true)
  const wasSendingRef = useRef(isSending)
  const firstRunPendingRef = useRef(
    enableFirstRunSuccess && typeof window !== 'undefined' && isFirstRunSearch(window.location.search),
  )
  const [showFirstRunSuccess, setShowFirstRunSuccess] = useState(false)
  const stopState = useAgentStreamStopState()
  const stopping = isStopping ?? stopState === 'stopping'
  const resolvedEntries = useMemo<ChatCanvasEntry[]>(
    () => entries ?? (messages ?? []).map((message, index) => ({ key: String(index), message })),
    [entries, messages],
  )
  const resolvedMessages = useMemo(
    () => resolvedEntries.map((entry) => entry.message),
    [resolvedEntries],
  )
  const visibleEntries = resolvedEntries.filter(
    (entry, index) => !isEmptyTerminalAssistantPlaceholder(entry.message, index, resolvedMessages, isSending),
  )
  const lastMessageContent = visibleEntries[visibleEntries.length - 1]?.message.content ?? ''
  const currentFirstRun = enableFirstRunSuccess
    && typeof window !== 'undefined'
    && isFirstRunSearch(window.location.search)

  useEffect(() => {
    if (currentFirstRun) firstRunPendingRef.current = true
  }, [currentFirstRun])

  useEffect(() => {
    if (!enableFirstRunSuccess) return
    const wasSending = wasSendingRef.current
    wasSendingRef.current = isSending

    if (resolvedMessages.length === 0) {
      setShowFirstRunSuccess(false)
      return
    }

    if (!firstRunPendingRef.current || !didCompleteFirstRun(wasSending, isSending, resolvedMessages)) return

    firstRunPendingRef.current = false
    setShowFirstRunSuccess(true)

    if (typeof window !== 'undefined') {
      const nextLocation = removeFirstRunFromLocation(
        window.location.pathname,
        window.location.search,
        window.location.hash,
      )
      window.history.replaceState(window.history.state, '', nextLocation)
    }
  }, [enableFirstRunSuccess, isSending, resolvedMessages])

  const scrollToBottomIfPinned = useCallback(() => {
    const element = messagesContainerRef.current
    if (!element || !shouldStickToBottomRef.current) return
    element.scrollTop = element.scrollHeight
  }, [])

  const handleScroll = useCallback(() => {
    const element = messagesContainerRef.current
    if (!element) return
    shouldStickToBottomRef.current = isNearBottom(element)
  }, [])

  const handleSend = useCallback((content: string) => {
    setShowFirstRunSuccess(false)
    onSend(content)
  }, [onSend])

  useLayoutEffect(() => {
    scrollToBottomIfPinned()
  }, [visibleEntries.length, lastMessageContent, isSending, scrollToBottomIfPinned])

  useLayoutEffect(() => {
    const content = messagesContentRef.current
    if (!content) return

    const observer = new ResizeObserver(() => scrollToBottomIfPinned())
    observer.observe(content)
    return () => observer.disconnect()
  }, [scrollToBottomIfPinned])

  const isEmpty = visibleEntries.length === 0
  const EmptyIcon = assistantIcon === 'network' ? Workflow : Bot

  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background">
      <ScrollArea ref={messagesContainerRef} className="relative min-h-0 flex-1" onScroll={handleScroll}>
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage: 'radial-gradient(ellipse at 50% 0%, rgba(59,130,246,0.045) 0%, transparent 68%)',
          }}
        />

        {isSessionLoading ? (
          <SessionMessagesLoading />
        ) : isEmpty ? (
          <div className="relative flex h-full flex-col items-center justify-center px-6 text-center">
            <div className="mb-4 rounded-2xl border border-primary/25 bg-primary/10 p-4 shadow-lg shadow-primary/5">
              <EmptyIcon className="h-8 w-8 text-primary-light" />
            </div>
            <h2 className="mb-1 text-lg font-semibold tracking-tight text-white">{emptyTitle}</h2>
            <p className="mb-6 max-w-md text-sm text-muted">
              {runtimeBlocked ? runtimeBlockReason : emptyDescription}
            </p>
            {!runtimeBlocked && (
              <div className="flex w-full max-w-sm flex-col gap-2">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => handleSend(suggestion)}
                    className="group flex items-center justify-between rounded-xl border border-border/80 bg-surface/45 px-4 py-3 text-left text-sm text-muted shadow-sm shadow-black/5 transition-all hover:border-primary/35 hover:bg-primary/5 hover:text-white"
                  >
                    <span>{suggestion}</span>
                    <ArrowRight className="ml-2 h-4 w-4 shrink-0 transition-transform group-hover:translate-x-0.5" />
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div ref={messagesContentRef} className="relative space-y-4 p-4 pb-2">
            {visibleEntries.map((entry, index) => {
              const content = (
                <ChatMessage
                  message={entry.message}
                  isStreaming={entry.isStreaming ?? (entry.message.role === 'assistant' && isSending && index === visibleEntries.length - 1)}
                  isLast={index === visibleEntries.length - 1}
                  agentName={entry.agentName ?? agentName}
                  assistantIcon={entry.assistantIcon ?? assistantIcon}
                  details={entry.details}
                  footerMeta={entry.footerMeta}
                  footerActions={entry.footerActions}
                />
              )
              const key = entry.key ?? String(index)
              return entry.className
                ? <div key={key} className={entry.className}>{content}</div>
                : <Fragment key={key}>{content}</Fragment>
            })}
            {showFirstRunSuccess && (
              <div className="mx-auto flex max-w-2xl items-start gap-3 rounded-xl border border-primary/25 bg-primary/[0.05] p-4 text-left">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />
                <div>
                  <p className="text-sm font-medium text-white">First test completed</p>
                  <p className="mt-1 text-xs leading-5 text-muted">Your Agent Draft responded successfully. Continue testing or configure Versions when you are ready.</p>
                </div>
              </div>
            )}
            <div />
          </div>
        )}
      </ScrollArea>

      <ChatComposer
        isSending={isSending}
        isStopping={stopping}
        isPreparing={isPreparing}
        onSend={handleSend}
        onStop={onStop}
        runtimeBlocked={runtimeBlocked}
        runtimeBlockReason={runtimeBlockReason}
        value={composerValue}
        onChange={onComposerValueChange}
        placeholder={composerPlaceholder}
        statusText={composerStatusText}
        preparingText={preparingText}
      />
    </section>
  )
}
