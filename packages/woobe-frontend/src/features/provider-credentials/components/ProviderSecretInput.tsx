import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { Button, Input, InputGroup } from '@woobe/ui'

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
    <InputGroup
      end={(
        <Button
          type="button"
          variant="ghost"
          size="iconSm"
          onClick={() => setRevealed((current) => !current)}
          aria-label={revealed ? 'Hide API key' : 'Show API key'}
          className="text-muted-foreground"
        >
          {revealed ? <EyeOff className="h-icon w-icon" /> : <Eye className="h-icon w-icon" />}
        </Button>
      )}
    >
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
        className={`font-mono ${revealed ? '' : '[-webkit-text-security:disc]'}`}
      />
    </InputGroup>
  )
}
