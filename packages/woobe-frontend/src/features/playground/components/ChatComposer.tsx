import { useState, useRef, useCallback } from 'react'
import { Send, Paperclip, Square, Wrench } from 'lucide-react'

interface ChatComposerProps {
  isSending: boolean
  isStopping?: boolean
  onSend: (content: string) => void
  onStop: () => void
  runtimeBlocked?: boolean
  runtimeBlockReason?: string
}

export function ChatComposer({ isSending, isStopping = false, onSend, onStop, runtimeBlocked = false, runtimeBlockReason }: ChatComposerProps) {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const blocked = isSending || runtimeBlocked

  const handleSend = useCallback(() => {
    if (!input.trim() || blocked) return
    onSend(input.trim())
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [input, blocked, onSend])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  return (
    <div className="border-t border-border/90 bg-surface/70 p-4 shadow-[0_-18px_50px_rgba(0,0,0,0.10)]">
      <div className="rounded-xl border border-border/90 bg-background/75 shadow-lg shadow-black/10 transition-colors focus-within:border-primary/35 focus-within:ring-1 focus-within:ring-primary/10">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={runtimeBlocked ? (runtimeBlockReason ?? 'Runtime blocked') : 'Type your message...'}
          rows={1}
          className="w-full bg-transparent px-4 py-3 text-sm text-white placeholder:text-muted resize-none outline-none min-h-[44px] max-h-[160px]"
          disabled={blocked}
        />
        <div className="flex items-center justify-between px-3 pb-2">
          <div className="flex items-center gap-1">
            <button type="button" className="flex items-center gap-1 rounded-md border border-transparent px-2 py-1 text-xs text-muted hover:text-white hover:border-border/80 hover:bg-surface/70 transition-colors disabled:opacity-40" disabled={blocked}>
              <Paperclip className="h-3.5 w-3.5" />
              Attach
            </button>
            <button type="button" className="flex items-center gap-1 rounded-md border border-transparent px-2 py-1 text-xs text-muted hover:text-white hover:border-border/80 hover:bg-surface/70 transition-colors disabled:opacity-40" disabled={blocked}>
              <Wrench className="h-3.5 w-3.5" />
              Tools
            </button>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-muted/80 hidden sm:inline">
              {runtimeBlocked ? runtimeBlockReason : isStopping ? 'Stopping...' : isSending ? 'Generating...' : 'Enter to send · Shift+Enter for new line'}
            </span>
            {isSending ? (
              <button
                type="button"
                onClick={onStop}
                disabled={isStopping}
                aria-label={isStopping ? 'Stopping generation' : 'Stop generation'}
                className="flex items-center justify-center w-8 h-8 rounded-lg border border-red-500/35 bg-red-500/15 text-red-100 hover:bg-red-500/25 transition-colors disabled:cursor-wait disabled:opacity-55"
              >
                <Square className="h-3.5 w-3.5 fill-current" />
              </button>
            ) : (
              <button type="button" onClick={handleSend} disabled={!input.trim() || blocked} className="flex items-center justify-center w-8 h-8 rounded-lg border border-primary/35 bg-primary/90 text-white hover:bg-primary transition-colors disabled:border-border disabled:bg-surface disabled:text-muted disabled:opacity-50 disabled:cursor-not-allowed">
                <Send className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
