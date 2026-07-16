import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'

import { Input } from '@/components/ui/Input'

interface ProviderSecretInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  autoFocus?: boolean
}

export function ProviderSecretInput({
  value,
  onChange,
  placeholder = 'Paste your API key',
  disabled = false,
  autoFocus = false,
}: ProviderSecretInputProps) {
  const [revealed, setRevealed] = useState(false)

  return (
    <div className="relative">
      <Input
        type="text"
        name="provider-api-key"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        autoFocus={autoFocus}
        autoComplete="off"
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        data-1p-ignore
        data-lpignore="true"
        data-form-type="other"
        className={`pr-10 ${revealed ? '' : '[-webkit-text-security:disc]'}`}
      />
      <button
        type="button"
        onClick={() => setRevealed((current) => !current)}
        aria-label={revealed ? 'Hide API key' : 'Show API key'}
        className="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted transition-colors hover:bg-accent hover:text-white focus:outline-none focus:ring-1 focus:ring-primary"
      >
        {revealed ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  )
}
