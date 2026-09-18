import { useCallback, useMemo, useRef, useState } from 'react'
import { Button } from '@woobe/ui'
import { Braces, ChevronDown, ChevronRight, Loader2, Paperclip, Send, Square, Wrench } from 'lucide-react'

import { ContractValueForm } from '@/features/contracts/ContractValueForm'
import { contractFields } from '@/features/contracts/contractFields'

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
  density?: 'default' | 'compact'
  externalContextContract?: unknown
  externalContextValues?: Record<string, unknown>
  onExternalContextValuesChange?: (values: Record<string, unknown>) => void
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
  density = 'default',
  externalContextContract,
  externalContextValues = {},
  onExternalContextValuesChange,
}: ChatComposerProps) {
  const [internalInput, setInternalInput] = useState('')
  const [externalContextOpen, setExternalContextOpen] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const input = value ?? internalInput
  const blocked = isSending || isPreparing || runtimeBlocked
  const compact = density === 'compact'
  const externalContextFields = useMemo(() => contractFields(externalContextContract), [externalContextContract])
  const externalContextFieldEntries = Object.entries(externalContextFields)
  const missingRequiredExternalContextFields = externalContextFieldEntries.filter(([name, field]) => {
    const consumers = field && typeof field === 'object' && 'consumers' in field && field.consumers && typeof field.consumers === 'object' && !Array.isArray(field.consumers)
      ? field.consumers as Record<string, { required?: boolean }>
      : {}
    const required = Boolean(field.required) || Object.values(consumers).some((consumer) => Boolean(consumer?.required))
    if (!required) return false
    const fieldValue = externalContextValues[name]
    return fieldValue === undefined || fieldValue === null || fieldValue === ''
  }).length

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
    element.style.height = `${element.scrollHeight}px`
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
    <div className={compact ? 'min-w-0 border-t border-border bg-surface/[0.78] p-ui-sm' : 'min-w-0 border-t border-border bg-surface/[0.78] p-ui-md'}>
      {externalContextFieldEntries.length > 0 ? (
        <div className="mb-ui-xs overflow-hidden rounded-control border border-border/80 bg-background/30">
          <button
            type="button"
            onClick={() => setExternalContextOpen((current) => !current)}
            className="flex min-h-control w-full items-center gap-ui-xs px-ui-sm text-left transition-colors hover:bg-control/35"
            aria-expanded={externalContextOpen}
          >
            {externalContextOpen
              ? <ChevronDown className="h-icon-sm w-icon-sm text-muted-foreground" />
              : <ChevronRight className="h-icon-sm w-icon-sm text-muted-foreground" />}
            <Braces className="h-icon-sm w-icon-sm text-primary-light" />
            <span className="font-mono text-system-control font-medium text-slate-100">External Context</span>
            <span className="font-sans text-product-caption text-muted-foreground">
              {externalContextFieldEntries.length} field{externalContextFieldEntries.length === 1 ? '' : 's'}
            </span>
            {missingRequiredExternalContextFields > 0 ? (
              <span className="ml-auto rounded-technical border border-amber-400/25 bg-amber-400/[0.06] px-ui-xs font-mono text-system-meta text-amber-300">
                {missingRequiredExternalContextFields} required missing
              </span>
            ) : (
              <span className="ml-auto font-mono text-system-meta text-muted-foreground">run + session</span>
            )}
          </button>
          {externalContextOpen ? (
            <div className="border-t border-border/70 px-ui-sm pb-ui-sm">
              <p className="py-ui-xs font-sans text-product-caption text-muted-foreground">
                Fields stay available while testing. Run-scoped values are sent on each execution; Session-scoped values are persisted by the Runtime when a Session is available.
              </p>
              <ContractValueForm
                contract={externalContextContract}
                values={externalContextValues}
                disabled={blocked}
                density="compact"
                onChange={onExternalContextValuesChange ?? (() => undefined)}
              />
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="min-w-0 max-w-full rounded-container border border-border bg-control/40 transition-colors focus-within:border-primary/45 focus-within:ring-1 focus-within:ring-primary/15">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={runtimeBlocked ? (runtimeBlockReason ?? 'Runtime blocked') : placeholder}
          rows={1}
          className={compact
            ? 'min-h-control max-h-multiline min-w-0 w-full resize-none bg-transparent px-ui-sm py-ui-sm font-sans text-product-small text-slate-100 outline-none placeholder:text-muted-foreground'
            : 'min-h-control-row max-h-multiline min-w-0 w-full resize-none bg-transparent px-ui-md py-ui-sm font-sans text-product-reading text-slate-100 outline-none placeholder:text-muted-foreground'}
          disabled={blocked}
        />
        <div className={compact
          ? 'flex min-w-0 items-center justify-between gap-ui-xs border-t border-border/60 px-ui-xs py-ui-xs'
          : 'flex min-w-0 items-center justify-between border-t border-border/60 px-ui-sm py-ui-sm'}>
          <div className="flex min-w-0 items-center gap-ui-xs">
            <Button type="button" variant="ghost" size={compact ? 'xs' : 'sm'} disabled={blocked} className="font-sans text-muted-foreground">
              <Paperclip className="h-icon-sm w-icon-sm" />
              Attach
            </Button>
            <Button type="button" variant="ghost" size={compact ? 'xs' : 'sm'} disabled={blocked} className="font-sans text-muted-foreground">
              <Wrench className="h-icon-sm w-icon-sm" />
              Tools
            </Button>
          </div>
          <div className="flex min-w-0 shrink-0 items-center gap-ui-sm">
            {compact ? <span className="sr-only">{resolvedStatus}</span> : (
              <span className="hidden max-w-[17.5rem] truncate font-mono text-system-micro text-muted-foreground/80 sm:inline">
                {resolvedStatus}
              </span>
            )}
            {isSending ? (
              <Button
                type="button"
                variant="destructive"
                size={compact ? 'xs' : 'sm'}
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
                size={compact ? 'xs' : 'sm'}
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
