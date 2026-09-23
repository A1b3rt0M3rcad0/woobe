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
  density?: 'default' | 'compact'
  externalContextContract?: unknown
  externalContextValues?: Record<string, unknown>
  lockedExternalContextValues?: Record<string, unknown>
  onExternalContextValuesChange?: (values: Record<string, unknown>) => void
  onClearExternalContextValues?: () => void
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

function SessionMessagesLoading({ compact = false }: { compact?: boolean }) {
  return (
    <div className={compact ? 'relative flex h-full items-center justify-center px-ui-md' : 'relative flex h-full items-center justify-center px-ui-xxl'}>
      <div className="w-full max-w-2xl space-y-ui-md">
        <div className="flex justify-start gap-ui-sm">
          <div className="h-control-segment w-control-segment shrink-0 animate-pulse rounded-control border border-border bg-control" />
          <div className={compact
            ? 'w-[82%] space-y-ui-sm rounded-control border border-border bg-surface/60 px-ui-sm py-ui-sm'
            : 'w-[72%] space-y-ui-sm rounded-container border border-border bg-surface/60 px-ui-md py-ui-sm'}>
            <div className="h-2.5 w-1/2 animate-pulse rounded-technical bg-white/[0.07]" />
            <div className="h-2.5 w-full animate-pulse rounded-technical bg-white/[0.07]" />
            <div className="h-2.5 w-2/3 animate-pulse rounded-technical bg-white/[0.07]" />
          </div>
        </div>
        <div className="flex justify-end gap-ui-sm">
          <div className={compact
            ? 'w-[68%] space-y-ui-sm rounded-control border border-primary/20 bg-primary/[0.08] px-ui-sm py-ui-sm'
            : 'w-[52%] space-y-ui-sm rounded-container border border-primary/20 bg-primary/[0.08] px-ui-md py-ui-sm'}>
            <div className="ml-auto h-2.5 w-full animate-pulse rounded-technical bg-white/[0.08]" />
            <div className="ml-auto h-2.5 w-2/3 animate-pulse rounded-technical bg-white/[0.08]" />
          </div>
          <div className="h-control-segment w-control-segment shrink-0 animate-pulse rounded-control border border-primary/25 bg-primary/[0.08]" />
        </div>
        <p className="pt-ui-xs text-center font-mono text-system-meta text-muted-foreground">Loading session messages...</p>
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
  density = 'default',
  externalContextContract,
  externalContextValues,
  lockedExternalContextValues,
  onExternalContextValuesChange,
  onClearExternalContextValues,
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
  const compact = density === 'compact'
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
      <ScrollArea ref={messagesContainerRef} className="relative min-h-0 min-w-0 flex-1" onScroll={handleScroll}>
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-technical-grid bg-technical-grid opacity-100" />

        {isSessionLoading ? (
          <SessionMessagesLoading compact={compact} />
        ) : isEmpty ? (
          <div className={compact
            ? 'relative flex h-full min-w-0 flex-col items-center justify-center px-ui-md text-center'
            : 'relative flex h-full min-w-0 flex-col items-center justify-center px-ui-xxl text-center'}>
            <div className="mb-ui-md flex h-control-nav w-control-nav items-center justify-center rounded-control border border-border bg-control text-primary-light">
              <EmptyIcon className="h-icon-lg w-icon-lg" />
            </div>
            <h2 className="font-mono text-system-heading font-bold text-slate-50">{emptyTitle}</h2>
            <p className="mt-ui-sm max-w-md font-sans text-product-small text-muted-foreground">
              {runtimeBlocked ? runtimeBlockReason : emptyDescription}
            </p>
            {!runtimeBlocked && (
              <div className={compact
                ? 'mt-ui-md w-full max-w-md divide-y divide-border/60 overflow-hidden rounded-control border border-border bg-surface/45 text-left'
                : 'mt-ui-xl w-full max-w-md divide-y divide-border/60 overflow-hidden rounded-container border border-border bg-surface/45 text-left'}>
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => handleSend(suggestion)}
                    className={compact
                      ? 'group flex min-h-control w-full items-center justify-between gap-ui-sm px-ui-sm py-ui-sm font-sans text-product-caption text-muted-foreground transition-colors hover:bg-control/45 hover:text-slate-100'
                      : 'group flex min-h-control-row w-full items-center justify-between gap-ui-md px-ui-md py-ui-sm font-sans text-product-small text-muted-foreground transition-colors hover:bg-control/45 hover:text-slate-100'}
                  >
                    <span className="min-w-0">{suggestion}</span>
                    <ArrowRight className="h-icon w-icon shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary-light" />
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div ref={messagesContentRef} className={compact
            ? 'relative min-w-0 space-y-ui-sm p-ui-sm pb-ui-xs'
            : 'relative min-w-0 space-y-ui-md p-ui-lg pb-ui-sm'}>
            {visibleEntries.map((entry, index) => {
              const content = (
                <ChatMessage
                  message={entry.message}
                  isStreaming={entry.isStreaming ?? (entry.message.role === 'assistant' && isSending && index === visibleEntries.length - 1)}
                  isLast={index === visibleEntries.length - 1}
                  agentName={entry.agentName ?? agentName}
                  variant={compact ? 'network' : 'playground'}
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
              <div className={compact
                ? 'mx-auto flex max-w-2xl items-start gap-ui-sm border-l-2 border-l-primary bg-primary/[0.045] px-ui-sm py-ui-sm text-left'
                : 'mx-auto flex max-w-2xl items-start gap-ui-sm border-l-2 border-l-primary bg-primary/[0.045] px-ui-md py-ui-sm text-left'}>
                <CheckCircle2 className="mt-ui-hairline h-icon w-icon shrink-0 text-primary-light" />
                <div>
                  <p className="font-mono text-system-label font-semibold text-slate-100">First test completed</p>
                  <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Your Agent Draft responded successfully. Continue testing or configure Versions when you are ready.</p>
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
        density={density}
        externalContextContract={externalContextContract}
        externalContextValues={externalContextValues}
        lockedExternalContextValues={lockedExternalContextValues}
        onExternalContextValuesChange={onExternalContextValuesChange}
        onClearExternalContextValues={onClearExternalContextValues}
      />
    </section>
  )
}
