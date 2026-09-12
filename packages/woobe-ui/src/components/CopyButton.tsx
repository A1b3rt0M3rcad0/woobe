import { useEffect, useRef, useState } from 'react'
import { AlertCircle, Check, Copy } from 'lucide-react'
import { cn } from '../lib/cn'

export interface CopyButtonProps {
  text: string
  className?: string
  label?: string
  copiedLabel?: string
  errorLabel?: string
  iconOnly?: boolean
}

type CopyStatus = 'idle' | 'copied' | 'error'

async function copyWithFallback(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  document.body.removeChild(textarea)
  if (!copied) throw new Error('Clipboard copy failed')
}

export function CopyButton({
  text,
  className,
  label = 'Copy',
  copiedLabel = 'Copied',
  errorLabel = 'Unable to copy',
  iconOnly = false,
}: CopyButtonProps) {
  const [status, setStatus] = useState<CopyStatus>('idle')
  const resetTimer = useRef<number | null>(null)

  useEffect(() => () => {
    if (resetTimer.current != null) window.clearTimeout(resetTimer.current)
  }, [])

  const handleCopy = async () => {
    if (resetTimer.current != null) window.clearTimeout(resetTimer.current)
    try {
      await copyWithFallback(text)
      setStatus('copied')
    } catch {
      setStatus('error')
    }
    resetTimer.current = window.setTimeout(() => setStatus('idle'), 2000)
  }

  const title = status === 'error' ? errorLabel : status === 'copied' ? copiedLabel : label

  return (
    <button
      type="button"
      onClick={() => void handleCopy()}
      aria-label={title}
      title={title}
      className={cn(
        'inline-flex h-7 items-center justify-center gap-ui-xs rounded-control border border-transparent px-ui-sm',
        'font-mono text-system-label font-medium text-muted-foreground transition-colors',
        'hover:border-border hover:bg-accent hover:text-slate-100',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35',
        status === 'error' ? 'text-red-300' : undefined,
        className,
      )}
    >
      {status === 'copied' ? (
        <Check className="h-3.5 w-3.5 text-emerald-400" />
      ) : status === 'error' ? (
        <AlertCircle className="h-3.5 w-3.5" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
      {iconOnly ? null : <span>{status === 'copied' ? copiedLabel : status === 'error' ? errorLabel : label}</span>}
    </button>
  )
}
