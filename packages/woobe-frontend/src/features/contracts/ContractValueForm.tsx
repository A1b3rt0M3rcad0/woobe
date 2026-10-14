import { Input, Select } from '@woobe/ui'

import { contractFields, coerceContractValue, type ContractFieldType } from './contractFields'

interface ContractValueFormProps {
  contract: unknown
  values: Record<string, unknown>
  lockedValues?: Record<string, unknown>
  disabled?: boolean
  density?: 'default' | 'compact'
  onChange: (values: Record<string, unknown>) => void
}

function fieldType(field: { schema?: Record<string, unknown> }): ContractFieldType {
  const type = field.schema?.type
  return type === 'integer' || type === 'number' || type === 'boolean' ? type : 'string'
}

function inputValue(value: unknown) {
  if (value == null) return ''
  return typeof value === 'string' || typeof value === 'number' ? String(value) : ''
}

export function ContractValueForm({ contract, values, lockedValues = {}, disabled = false, density = 'default', onChange }: ContractValueFormProps) {
  const fields = contractFields(contract)
  const entries = Object.entries(fields)

  if (!entries.length) {
    return <p className="font-sans text-product-small text-muted-foreground">No External Context fields are declared for this target.</p>
  }

  const setValue = (name: string, value: unknown) => {
    const next = { ...values }
    if (value === undefined || value === '') delete next[name]
    else next[name] = value
    onChange(next)
  }

  return (
    <div className="divide-y divide-border/70 border-y border-border/70">
      {entries.map(([name, field]) => {
        const type = fieldType(field)
        const enumValues = Array.isArray(field.schema?.enum) ? field.schema?.enum : null
        const consumers = field && typeof field === 'object' && 'consumers' in field && field.consumers && typeof field.consumers === 'object' && !Array.isArray(field.consumers)
          ? field.consumers as Record<string, { required?: boolean }>
          : {}
        const required = Boolean(field.required) || Object.values(consumers).some((consumer) => Boolean(consumer?.required))
        const scope = field.scope === 'session' ? 'session' : 'run'
        const locked = scope === 'session' && Object.prototype.hasOwnProperty.call(lockedValues, name)
        const value = locked ? lockedValues[name] : values[name]
        return (
          <div
            key={name}
            className={density === 'compact'
              ? 'grid min-w-0 gap-ui-xs py-ui-sm'
              : 'grid min-h-control grid-cols-[minmax(110px,0.8fr)_minmax(150px,1.4fr)] items-center gap-ui-sm py-ui-xs'}
          >
            <div className="min-w-0">
              <p className="truncate font-mono text-system-control text-accent-foreground">{name}</p>
              <p className="font-mono text-system-label text-muted-foreground">
                {type}{required ? ' · required' : ''}{scope === 'session' ? locked ? ' · SESSION · fixed' : ' · SESSION · set once' : ' · RUN'}
              </p>
              {field.description ? (
                <p className="mt-ui-hairline font-sans text-product-caption leading-4 text-muted-foreground">
                  {field.description}
                </p>
              ) : null}
            </div>
            {type === 'boolean' ? (
              <Select
                value={value === true ? 'true' : value === false ? 'false' : ''}
                disabled={disabled || locked}
                options={[
                  { value: '', label: required ? 'Select value' : 'Unset' },
                  { value: 'true', label: 'True' },
                  { value: 'false', label: 'False' },
                ]}
                onChange={(event) => setValue(name, coerceContractValue(type, event.target.value))}
                aria-label={name}
              />
            ) : enumValues?.length ? (
              <Select
                value={inputValue(value)}
                disabled={disabled || locked}
                placeholder="Select value"
                options={enumValues.map((item) => ({ value: String(item), label: String(item) }))}
                onChange={(event) => setValue(name, coerceContractValue(type, event.target.value))}
                aria-label={name}
              />
            ) : (
              <Input
                value={inputValue(value)}
                disabled={disabled || locked}
                  type={type === 'integer' || type === 'number' ? 'number' : 'text'}
                step={type === 'number' ? 'any' : undefined}
                placeholder={required ? 'Required value' : 'Optional'}
                onChange={(event) => setValue(name, coerceContractValue(type, event.target.value))}
                aria-label={name}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
