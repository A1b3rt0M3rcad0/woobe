import { Plus, Trash2 } from 'lucide-react'
import { Button, Checkbox, Input, Select } from '@woobe/ui'

import {
  CONTRACT_FIELD_TYPE_OPTIONS,
  type ContractFieldRow,
  type ContractFieldType,
} from './contractFields'

interface ContractFieldBuilderProps {
  rows: ContractFieldRow[]
  kind: 'output' | 'external'
  disabled?: boolean
  onChange: (rows: ContractFieldRow[]) => void
}

const SCOPE_OPTIONS = [
  { value: 'run', label: 'Run' },
  { value: 'session', label: 'Session' },
]

const MODEL_OPTIONS = [
  { value: 'expose', label: 'Expose' },
  { value: 'hidden', label: 'Hidden' },
]

function nextFieldName(rows: ContractFieldRow[]) {
  let index = rows.length + 1
  let name = `field_${index}`
  const names = new Set(rows.map((row) => row.name))
  while (names.has(name)) {
    index += 1
    name = `field_${index}`
  }
  return name
}

export function ContractFieldBuilder({
  rows,
  kind,
  disabled = false,
  onChange,
}: ContractFieldBuilderProps) {
  const update = (index: number, patch: Partial<ContractFieldRow>) => {
    onChange(rows.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row))
  }

  const remove = (index: number) => onChange(rows.filter((_, rowIndex) => rowIndex !== index))

  const add = () => onChange([
    ...rows,
    {
      name: nextFieldName(rows),
      type: 'string',
      required: false,
      scope: 'run',
      expose: true,
    },
  ])

  return (
    <div className="min-w-0">
      <div
        className={
          kind === 'external'
            ? 'grid grid-cols-[minmax(120px,1.4fr)_110px_105px_72px_100px_32px] items-center gap-ui-xs border-b border-border px-ui-xs pb-ui-xs font-mono text-system-label uppercase tracking-system-label text-muted-foreground'
            : 'grid grid-cols-[minmax(140px,1.5fr)_120px_82px_32px] items-center gap-ui-xs border-b border-border px-ui-xs pb-ui-xs font-mono text-system-label uppercase tracking-system-label text-muted-foreground'
        }
      >
        <span>Name</span>
        <span>Type</span>
        {kind === 'external' ? <span>Scope</span> : null}
        <span className="text-center">Required</span>
        {kind === 'external' ? <span>Model</span> : null}
        <span />
      </div>

      <div className="divide-y divide-border/70">
        {rows.map((row, index) => (
          <div
            key={index}
            className={
              kind === 'external'
                ? 'grid min-h-control grid-cols-[minmax(120px,1.4fr)_110px_105px_72px_100px_32px] items-center gap-ui-xs px-ui-xs py-ui-xs'
                : 'grid min-h-control grid-cols-[minmax(140px,1.5fr)_120px_82px_32px] items-center gap-ui-xs px-ui-xs py-ui-xs'
            }
          >
            <Input
              value={row.name}
              disabled={disabled}
              spellCheck={false}
              onChange={(event) => update(index, { name: event.target.value })}
              aria-label={`Field ${index + 1} name`}
            />
            <Select
              value={row.type}
              disabled={disabled}
              options={CONTRACT_FIELD_TYPE_OPTIONS}
              onChange={(event) => update(index, { type: event.target.value as ContractFieldType })}
              aria-label={`Field ${row.name || index + 1} type`}
            />
            {kind === 'external' ? (
              <Select
                value={row.scope}
                disabled={disabled}
                options={SCOPE_OPTIONS}
                onChange={(event) => update(index, { scope: event.target.value as 'run' | 'session' })}
                aria-label={`Field ${row.name || index + 1} scope`}
              />
            ) : null}
            <div className="flex justify-center">
              <Checkbox
                checked={row.required}
                disabled={disabled}
                onChange={(event) => update(index, { required: event.target.checked })}
                aria-label={`Field ${row.name || index + 1} required`}
              />
            </div>
            {kind === 'external' ? (
              <Select
                value={row.expose ? 'expose' : 'hidden'}
                disabled={disabled}
                options={MODEL_OPTIONS}
                onChange={(event) => update(index, { expose: event.target.value === 'expose' })}
                aria-label={`Field ${row.name || index + 1} model visibility`}
              />
            ) : null}
            <Button
              type="button"
              size="iconSm"
              variant="ghost"
              disabled={disabled}
              onClick={() => remove(index)}
              aria-label={`Remove ${row.name || `field ${index + 1}`}`}
              className="text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="h-icon-sm w-icon-sm" />
            </Button>
          </div>
        ))}
      </div>

      <div className="border-t border-border/70 pt-ui-sm">
        <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={add}>
          <Plus className="h-icon-sm w-icon-sm" />
          Add field
        </Button>
      </div>
    </div>
  )
}
