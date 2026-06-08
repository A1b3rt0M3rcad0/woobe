import { useState, useRef, useCallback } from 'react'
import { Send, Paperclip, Wrench } from 'lucide-react'

interface ChatComposerProps {
  isSending: boolean
  onSend: (content: string) => void
}

export function ChatComposer({ isSending, onSend }: ChatComposerProps) {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = useCallback(() => {
    if (!input.trim() || isSending) return
    onSend(input.trim())
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [input, isSending, onSend])

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
    <div className="p-4 border-t border-border bg-surface">
      <div className="rounded-xl border border-border bg-background shadow-sm">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Type your message..."
          rows={1}
          className="w-full bg-transparent px-4 py-3 text-sm text-white placeholder:text-muted resize-none outline-none min-h-[44px] max-h-[160px]"
          disabled={isSending}
        />
        <div className="flex items-center justify-between px-3 pb-2">
          <div className="flex items-center gap-1">
            <button
              className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted hover:text-white hover:bg-accent transition-colors"
              disabled={isSending}
            >
              <Paperclip className="h-3.5 w-3.5" />
              Attach
            </button>
            <button
              className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted hover:text-white hover:bg-accent transition-colors"
              disabled={isSending}
            >
              <Wrench className="h-3.5 w-3.5" />
              Tools
            </button>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-muted hidden sm:inline">
              Enter to send · Shift+Enter for new line
            </span>
            <button
              onClick={handleSend}
              disabled={!input.trim() || isSending}
              className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
