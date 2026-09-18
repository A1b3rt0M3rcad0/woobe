import { Input, Select } from '@woobe/ui'

import { contractFields, coerceContractValue, type ContractFieldType } from './contractFields'

interface ContractValueFormProps {
  contract: unknown
  values: Record<string, unknown>
  disabled?: boolean
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

export function ContractValueForm({ contract, values, disabled = false, onChange }: ContractValueFormProps) {
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
        return (
          <div key={name} className="grid min-h-control grid-cols-[minmax(110px,0.8fr)_minmax(150px,1.4fr)] items-center gap-ui-sm py-ui-xs">
            <div className="min-w-0">
              <p className="truncate font-mono text-system-control text-accent-foreground">{name}</p>
              <p className="font-mono text-system-label text-muted-foreground">
                {type}{field.scope ? ` · ${field.scope}` : ''}{required ? ' · required' : ''}
              </p>
            </div>
            {type === 'boolean' ? (
              <Select
                value={values[name] === true ? 'true' : values[name] === false ? 'false' : ''}
                disabled={disabled}
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
                value={inputValue(values[name])}
                disabled={disabled}
                placeholder="Select value"
                options={enumValues.map((item) => ({ value: String(item), label: String(item) }))}
                onChange={(event) => setValue(name, coerceContractValue(type, event.target.value))}
                aria-label={name}
              />
            ) : (
              <Input
                value={inputValue(values[name])}
                disabled={disabled}
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
