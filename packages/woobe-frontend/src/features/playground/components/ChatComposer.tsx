import { useCallback, useRef, useState } from 'react'
import { Loader2, Paperclip, Send, Square, Wrench } from 'lucide-react'

interface ChatComposerProps {
  isSending: boolean
  isStopping?: boolean
  isPreparing?: boolean
  onSend: (content: string) => void
  onStop: () => void
  runtimeBlocked?: boolean
  runtimeBlockReason?: string
  value?: string
  onChange?: (value: string) => void
  placeholder?: string
  statusText?: string
  preparingText?: string
}

export function ChatComposer({
  isSending,
  isStopping = false,
  isPreparing = false,
  onSend,
  onStop,
  runtimeBlocked = false,
  runtimeBlockReason,
  value,
  onChange,
  placeholder = 'Type your message...',
  statusText,
  preparingText = 'Preparing...',
}: ChatComposerProps) {
  const [internalInput, setInternalInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const input = value ?? internalInput
  const blocked = isSending || isPreparing || runtimeBlocked

  const setInput = useCallback((next: string) => {
    if (value === undefined) setInternalInput(next)
    onChange?.(next)
  }, [onChange, value])

  const handleSend = useCallback(() => {
    if (!input.trim() || blocked) return
    onSend(input.trim())
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }, [blocked, input, onSend, setInput])

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }

  const handleInput = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(event.target.value)
    const element = event.target
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, 160)}px`
  }

  const resolvedStatus = runtimeBlocked
    ? runtimeBlockReason
    : isPreparing
      ? preparingText
      : isStopping
        ? 'Stopping...'
        : isSending
          ? statusText ?? 'Generating...'
          : statusText ?? 'Enter to send · Shift+Enter for new line'

  return (
    <div className="border-t border-border/90 bg-surface/70 p-4 shadow-[0_-18px_50px_rgba(0,0,0,0.10)]">
      <div className="rounded-xl border border-border/90 bg-background/75 shadow-lg shadow-black/10 transition-colors focus-within:border-primary/35 focus-within:ring-1 focus-within:ring-primary/10">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={runtimeBlocked ? (runtimeBlockReason ?? 'Runtime blocked') : placeholder}
          rows={1}
          className="min-h-[44px] max-h-[160px] w-full resize-none bg-transparent px-4 py-3 text-sm text-white outline-none placeholder:text-muted"
          disabled={blocked}
        />
        <div className="flex items-center justify-between px-3 pb-2">
          <div className="flex items-center gap-1">
            <button type="button" className="flex items-center gap-1 rounded-md border border-transparent px-2 py-1 text-xs text-muted transition-colors hover:border-border/80 hover:bg-surface/70 hover:text-white disabled:opacity-40" disabled={blocked}>
              <Paperclip className="h-3.5 w-3.5" />
              Attach
            </button>
            <button type="button" className="flex items-center gap-1 rounded-md border border-transparent px-2 py-1 text-xs text-muted transition-colors hover:border-border/80 hover:bg-surface/70 hover:text-white disabled:opacity-40" disabled={blocked}>
              <Wrench className="h-3.5 w-3.5" />
              Tools
            </button>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden text-[11px] text-muted/80 sm:inline">
              {resolvedStatus}
            </span>
            {isSending ? (
              <button
                type="button"
                onClick={onStop}
                disabled={isStopping}
                aria-label={isStopping ? 'Stopping generation' : 'Stop generation'}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-red-500/35 bg-red-500/15 text-red-100 transition-colors hover:bg-red-500/25 disabled:cursor-wait disabled:opacity-55"
              >
                <Square className="h-3.5 w-3.5 fill-current" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSend}
                disabled={!input.trim() || blocked}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-primary/35 bg-primary/90 text-white transition-colors hover:bg-primary disabled:cursor-not-allowed disabled:border-border disabled:bg-surface disabled:text-muted disabled:opacity-50"
                aria-label={isPreparing ? preparingText : 'Send message'}
              >
                {isPreparing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
