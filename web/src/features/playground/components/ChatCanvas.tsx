import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ArrowRight, Bot, CheckCircle2 } from 'lucide-react'
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

interface ChatCanvasProps {
  messages: ChatMessageType[]
  isSending: boolean
  isStopping?: boolean
  isSessionLoading?: boolean
  onSend: (content: string) => void
  onStop: () => void
  agentName?: string
  runtimeBlocked?: boolean
  runtimeBlockReason?: string
}

const suggestions = [
  'Introduce yourself and explain what you can help with.',
  'Respond to a typical user request.',
  'Explain your current role in one sentence.',
]

const BOTTOM_THRESHOLD_PX = 48

function isNearBottom(el: HTMLDivElement): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= BOTTOM_THRESHOLD_PX
}

function SessionMessagesLoading() {
  return (
    <div className="relative flex h-full items-center justify-center px-6">
      <div className="w-full max-w-2xl space-y-4">
        <div className="flex gap-3 justify-start">
          <div className="h-8 w-8 shrink-0 animate-pulse rounded-full border border-border bg-surface" />
          <div className="w-[72%] space-y-2 rounded-xl rounded-bl-md border border-border/80 bg-surface/70 px-4 py-3 shadow-sm shadow-black/5">
            <div className="h-3 w-1/2 animate-pulse rounded-full bg-white/[0.07]" />
            <div className="h-3 w-full animate-pulse rounded-full bg-white/[0.07]" />
            <div className="h-3 w-2/3 animate-pulse rounded-full bg-white/[0.07]" />
          </div>
        </div>
        <div className="flex gap-3 justify-end">
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

export function ChatCanvas({ messages, isSending, isStopping, isSessionLoading = false, onSend, onStop, agentName, runtimeBlocked = false, runtimeBlockReason }: ChatCanvasProps) {
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const messagesContentRef = useRef<HTMLDivElement>(null)
  const shouldStickToBottomRef = useRef(true)
  const wasSendingRef = useRef(isSending)
  const firstRunPendingRef = useRef(
    typeof window !== 'undefined' && isFirstRunSearch(window.location.search),
  )
  const [showFirstRunSuccess, setShowFirstRunSuccess] = useState(false)
  const stopState = useAgentStreamStopState()
  const stopping = isStopping ?? stopState === 'stopping'
  const lastMessageContent = messages[messages.length - 1]?.content ?? ''
  const currentFirstRun = typeof window !== 'undefined'
    && isFirstRunSearch(window.location.search)

  useEffect(() => {
    if (currentFirstRun) firstRunPendingRef.current = true
  }, [currentFirstRun])

  useEffect(() => {
    const wasSending = wasSendingRef.current
    wasSendingRef.current = isSending

    if (messages.length === 0) {
      setShowFirstRunSuccess(false)
      return
    }

    if (
      !firstRunPendingRef.current
      || !didCompleteFirstRun(wasSending, isSending, messages)
    ) return

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
  }, [isSending, messages])

  const scrollToBottomIfPinned = useCallback(() => {
    const el = messagesContainerRef.current
    if (!el || !shouldStickToBottomRef.current) return
    el.scrollTop = el.scrollHeight
  }, [])

  const handleScroll = useCallback(() => {
    const el = messagesContainerRef.current
    if (!el) return
    shouldStickToBottomRef.current = isNearBottom(el)
  }, [])

  const handleSend = useCallback((content: string) => {
    setShowFirstRunSuccess(false)
    onSend(content)
  }, [onSend])

  useLayoutEffect(() => {
    scrollToBottomIfPinned()
  }, [messages.length, lastMessageContent, isSending, scrollToBottomIfPinned])

  useLayoutEffect(() => {
    const content = messagesContentRef.current
    if (!content) return

    const observer = new ResizeObserver(() => {
      scrollToBottomIfPinned()
    })
    observer.observe(content)
    return () => observer.disconnect()
  }, [scrollToBottomIfPinned])

  const isEmpty = messages.length === 0

  return (
    <section className="flex flex-col flex-1 min-w-0 min-h-0 overflow-hidden bg-background">
      <ScrollArea
        ref={messagesContainerRef}
        className="flex-1 min-h-0 relative"
        onScroll={handleScroll}
      >
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: 'radial-gradient(ellipse at 50% 0%, rgba(59,130,246,0.045) 0%, transparent 68%)',
          }}
        />

        {isSessionLoading ? (
          <SessionMessagesLoading />
        ) : isEmpty ? (
          <div className="relative flex flex-col items-center justify-center h-full px-6 text-center">
            <div className="mb-4 rounded-2xl border border-primary/25 bg-primary/10 p-4 shadow-lg shadow-primary/5">
              <Bot className="h-8 w-8 text-primary-light" />
            </div>
            <h2 className="text-lg font-semibold tracking-tight text-white mb-1">
              Test your Agent
            </h2>
            <p className="text-sm text-muted max-w-md mb-6">
              {runtimeBlocked ? runtimeBlockReason : 'Your model and provider are ready. Send a message to validate the current Draft.'}
            </p>
            {!runtimeBlocked && (
              <div className="flex flex-col gap-2 w-full max-w-sm">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => handleSend(suggestion)}
                    className="group flex items-center justify-between rounded-xl border border-border/80 bg-surface/45 px-4 py-3 text-sm text-muted hover:text-white hover:border-primary/35 hover:bg-primary/5 transition-all text-left shadow-sm shadow-black/5"
                  >
                    <span>{suggestion}</span>
                    <ArrowRight className="h-4 w-4 shrink-0 ml-2 transition-transform group-hover:translate-x-0.5" />
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div ref={messagesContentRef} className="relative space-y-4 p-4 pb-2">
            {messages.map((msg, i) => (
              <ChatMessage
                key={i}
                message={msg}
                isStreaming={msg.role === 'assistant' && isSending && i === messages.length - 1}
                isLast={i === messages.length - 1}
                agentName={agentName}
              />
            ))}
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

      <ChatComposer isSending={isSending} isStopping={stopping} onSend={handleSend} onStop={onStop} runtimeBlocked={runtimeBlocked} runtimeBlockReason={runtimeBlockReason} />
    </section>
  )
}
