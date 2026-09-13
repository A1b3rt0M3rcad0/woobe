import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { Button } from '@woobe/ui'
import { Input } from '@/components/ui/Input'

interface ProviderSecretInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  autoFocus?: boolean
}

export function ProviderSecretInput({ value, onChange, placeholder = 'Paste your API key', disabled = false, autoFocus = false }: ProviderSecretInputProps) {
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
        className={`pr-10 font-mono text-system-control ${revealed ? '' : '[-webkit-text-security:disc]'}`}
      />
      <Button
        type="button"
        variant="ghost"
        size="iconSm"
        onClick={() => setRevealed((current) => !current)}
        aria-label={revealed ? 'Hide API key' : 'Show API key'}
        className="absolute right-ui-xs top-1/2 -translate-y-1/2 text-muted-foreground"
      >
        {revealed ? <EyeOff className="h-icon w-icon" /> : <Eye className="h-icon w-icon" />}
      </Button>
    </div>
  )
}
