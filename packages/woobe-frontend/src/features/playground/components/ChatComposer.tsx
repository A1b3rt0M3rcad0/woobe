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
    <div className="border-t border-border bg-surface/[0.78] px-3 py-3">
      <div className="rounded-container border border-border bg-control/40 transition-colors focus-within:border-primary/45 focus-within:ring-1 focus-within:ring-primary/15">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={runtimeBlocked ? (runtimeBlockReason ?? 'Runtime blocked') : placeholder}
          rows={1}
          className="min-h-[42px] max-h-[160px] w-full resize-none bg-transparent px-3 py-2.5 font-sans text-[13px] leading-5 text-slate-100 outline-none placeholder:text-muted-foreground"
          disabled={blocked}
        />
        <div className="flex items-center justify-between border-t border-border/60 px-2.5 py-2">
          <div className="flex items-center gap-1">
            <button type="button" className="flex h-[27px] items-center gap-1 rounded-technical border border-transparent px-2 font-mono text-[8px] text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50 disabled:opacity-40" disabled={blocked}>
              <Paperclip className="h-3 w-3" />
              Attach
            </button>
            <button type="button" className="flex h-[27px] items-center gap-1 rounded-technical border border-transparent px-2 font-mono text-[8px] text-muted-foreground transition-colors hover:border-border hover:bg-control hover:text-slate-50 disabled:opacity-40" disabled={blocked}>
              <Wrench className="h-3 w-3" />
              Tools
            </button>
          </div>
          <div className="flex min-w-0 items-center gap-2">
            <span className="hidden max-w-[280px] truncate font-mono text-[8px] text-muted-foreground sm:inline">
              {resolvedStatus}
            </span>
            {isSending ? (
              <button
                type="button"
                onClick={onStop}
                disabled={isStopping}
                aria-label={isStopping ? 'Stopping generation' : 'Stop generation'}
                className="flex h-[30px] w-[30px] items-center justify-center rounded-control border border-red-500/35 bg-red-500/[0.09] text-red-200 transition-colors hover:bg-red-500/[0.14] disabled:cursor-wait disabled:opacity-55"
              >
                <Square className="h-3 w-3 fill-current" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSend}
                disabled={!input.trim() || blocked}
                className="flex h-[30px] w-[30px] items-center justify-center rounded-control border border-primary/40 bg-primary text-white transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:border-border disabled:bg-control disabled:text-muted-foreground disabled:opacity-50"
                aria-label={isPreparing ? preparingText : 'Send message'}
              >
                {isPreparing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
