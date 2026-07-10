import { useMemo } from 'react'
import {
  formatWoobeDateTime,
  WoobeDateTimePicker,
} from '@/components/ui/WoobeDateTimePicker'

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
    <div>
      <p className="text-xs font-medium text-muted">Expiration</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {EXPIRATIONS.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => onChange({
              preset: item.value,
              customDate: item.value === 'custom' ? value.customDate : null,
            })}
            className={`rounded-lg border px-3 py-2 text-xs transition-colors ${value.preset === item.value ? 'border-primary/35 bg-primary/10 text-primary-light' : 'border-border/80 bg-background/45 text-muted hover:text-white'}`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {value.preset === 'custom' ? (
        <div className="mt-3">
          <WoobeDateTimePicker
            value={value.customDate}
            autoOpen
            onChange={(customDate) => onChange({ preset: 'custom', customDate })}
          />
        </div>
      ) : value.preset === 'never' ? (
        <p className="mt-3 text-[11px] text-muted">This key will remain active until it is revoked.</p>
      ) : selectedExpiration ? (
        <p className="mt-3 text-[11px] text-muted">
          Expires <span className="text-white">{formatWoobeDateTime(selectedExpiration)}</span>
        </p>
      ) : null}

      {error && <p className="mt-1.5 text-xs text-red-300">{error}</p>}
    </div>
  )
}
