import { useEffect, useRef, useState } from 'react'
import { AlertCircle, Check, Copy } from 'lucide-react'

import { cn } from '@/lib/utils'

interface CopyButtonProps {
  text: string
  className?: string
  label?: string
  copiedLabel?: string
  errorLabel?: string
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

  return (
    <button
      type="button"
      onClick={() => void handleCopy()}
      className={cn(
        'inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors',
        'text-muted hover:bg-accent hover:text-white',
        status === 'error' && 'text-red-300 hover:text-red-200',
        className,
      )}
      title={status === 'error' ? errorLabel : 'Copy to clipboard'}
    >
      {status === 'copied' ? (
        <Check className="h-3.5 w-3.5 text-emerald-400" />
      ) : status === 'error' ? (
        <AlertCircle className="h-3.5 w-3.5" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
      {status === 'copied' ? copiedLabel : status === 'error' ? errorLabel : label}
    </button>
  )
}
