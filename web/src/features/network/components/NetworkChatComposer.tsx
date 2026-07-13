import { useRef } from 'react'
import { Send, Square } from 'lucide-react'

interface NetworkChatComposerProps {
  value: string
  running: boolean
  onChange: (value: string) => void
  onSend: () => void
  onStop: () => void
}

export function NetworkChatComposer({ value, running, onChange, onSend, onStop }: NetworkChatComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const resetHeight = () => {
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  return (
    <div className="shrink-0 border-t border-border bg-surface/55 p-3">
      <div className="mx-auto flex max-w-4xl items-end gap-2 rounded-xl border border-border bg-background/65 p-2 focus-within:border-primary/35 focus-within:ring-1 focus-within:ring-primary/10">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(event) => {
            onChange(event.target.value)
            event.target.style.height = 'auto'
            event.target.style.height = `${Math.min(event.target.scrollHeight, 140)}px`
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              onSend()
              resetHeight()
            }
          }}
          rows={1}
          disabled={running}
          placeholder="Send a message to the Network…"
          className="max-h-[140px] min-h-[42px] min-w-0 flex-1 resize-none bg-transparent px-2 py-2 text-[11px] leading-5 text-white outline-none placeholder:text-muted"
        />
        {running ? (
          <button type="button" onClick={onStop} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10 text-red-200" aria-label="Stop Network execution"><Square className="h-3.5 w-3.5 fill-current" /></button>
        ) : (
          <button type="button" onClick={() => { onSend(); resetHeight() }} disabled={!value.trim()} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-white disabled:bg-surface disabled:text-muted disabled:opacity-60" aria-label="Send message"><Send className="h-4 w-4" /></button>
        )}
      </div>
    </div>
  )
}
