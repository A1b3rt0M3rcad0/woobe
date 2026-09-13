import { useMemo } from 'react'
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
  SegmentedControl,
  WoobeDateTimePicker,
} from '@woobe/ui'
import { formatWoobeDateTime } from '@/components/ui/WoobeDateTimePicker'

export type ApiKeyExpirationPreset = '7d' | '30d' | '90d' | '365d' | 'custom' | 'never'

export interface ApiKeyExpirationValue {
  preset: ApiKeyExpirationPreset
  customDate: Date | null
}

interface ApiKeyExpirationFieldProps {
  value: ApiKeyExpirationValue
  onChange: (value: ApiKeyExpirationValue) => void
  error?: string | null
}

const EXPIRATIONS: Array<{ value: ApiKeyExpirationPreset; label: string }> = [
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
  { value: '90d', label: '90 days' },
  { value: '365d', label: '1 year' },
  { value: 'custom', label: 'Custom' },
  { value: 'never', label: 'No expiration' },
]

export const DEFAULT_API_KEY_EXPIRATION: ApiKeyExpirationValue = {
  preset: '90d',
  customDate: null,
}

export function resolveApiKeyExpiration(value: ApiKeyExpirationValue): Date | null {
  if (value.preset === 'never') return null
  if (value.preset === 'custom') return value.customDate

  const days = value.preset === '7d'
    ? 7
    : value.preset === '30d'
      ? 30
      : value.preset === '90d'
        ? 90
        : 365
  const expiresAt = new Date()
  expiresAt.setUTCDate(expiresAt.getUTCDate() + days)
  return expiresAt
}

export function ApiKeyExpirationField({ value, onChange, error }: ApiKeyExpirationFieldProps) {
  const selectedExpiration = useMemo(() => resolveApiKeyExpiration(value), [value])

  return (
    <Field>
      <FieldLabel>Expiration</FieldLabel>
      <div className="max-w-full overflow-x-auto">
        <SegmentedControl
          items={EXPIRATIONS}
          value={value.preset}
          onValueChange={(preset) => onChange({
            preset: preset as ApiKeyExpirationPreset,
            customDate: preset === 'custom' ? value.customDate : null,
          })}
          ariaLabel="API key expiration"
          size="compact"
        />
      </div>

      {value.preset === 'custom' ? (
        <WoobeDateTimePicker
          value={value.customDate}
          autoOpen
          onChange={(customDate) => onChange({ preset: 'custom', customDate })}
        />
      ) : value.preset === 'never' ? (
        <FieldDescription>This key will remain active until it is revoked.</FieldDescription>
      ) : selectedExpiration ? (
        <FieldDescription>
          Expires <span className="font-mono text-accent-foreground">{formatWoobeDateTime(selectedExpiration)}</span>
        </FieldDescription>
      ) : null}

      {error ? <FieldError>{error}</FieldError> : null}
    </Field>
  )
}
