import { useCallback, useRef, useState } from 'react'
import { Button } from '@woobe/ui'
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
    <div className="border-t border-border bg-surface/[0.78] p-ui-md">
      <div className="rounded-container border border-border bg-control/40 transition-colors focus-within:border-primary/45 focus-within:ring-1 focus-within:ring-primary/15">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={runtimeBlocked ? (runtimeBlockReason ?? 'Runtime blocked') : placeholder}
          rows={1}
          className="min-h-control-row max-h-multiline w-full resize-none bg-transparent px-ui-md py-ui-sm font-sans text-product-body text-slate-100 outline-none placeholder:text-muted-foreground"
          disabled={blocked}
        />
        <div className="flex items-center justify-between border-t border-border/60 px-ui-sm py-ui-sm">
          <div className="flex items-center gap-ui-xs">
            <Button type="button" variant="ghost" size="sm" disabled={blocked} className="text-muted-foreground">
              <Paperclip className="h-icon-sm w-icon-sm" />
              Attach
            </Button>
            <Button type="button" variant="ghost" size="sm" disabled={blocked} className="text-muted-foreground">
              <Wrench className="h-icon-sm w-icon-sm" />
              Tools
            </Button>
          </div>
          <div className="flex min-w-0 items-center gap-ui-sm">
            <span className="hidden max-w-[17.5rem] truncate font-mono text-system-meta text-muted-foreground sm:inline">
              {resolvedStatus}
            </span>
            {isSending ? (
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={onStop}
                disabled={isStopping}
                aria-label={isStopping ? 'Stopping generation' : 'Stop generation'}
                className="w-control-sm px-0"
              >
                <Square className="h-icon-sm w-icon-sm fill-current" />
              </Button>
            ) : (
              <Button
                type="button"
                size="sm"
                onClick={handleSend}
                disabled={!input.trim() || blocked}
                className="w-control-sm px-0"
                aria-label={isPreparing ? preparingText : 'Send message'}
              >
                {isPreparing ? <Loader2 className="h-icon w-icon animate-spin" /> : <Send className="h-icon w-icon" />}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
