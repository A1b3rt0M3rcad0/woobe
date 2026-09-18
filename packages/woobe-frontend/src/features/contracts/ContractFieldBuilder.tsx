import { Plus, Trash2 } from 'lucide-react'
import { Button, Checkbox, Input, Select, Textarea } from '@woobe/ui'

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
      expose: kind === 'output',
      description: '',
    },
  ])

  if (kind === 'external') {
    return (
      <div className="min-w-0 space-y-ui-sm">
        {rows.map((row, index) => (
          <section
            key={index}
            className="min-w-0 rounded-container border border-border/80 bg-background/25 p-ui-sm"
          >
            <div className="mb-ui-sm flex items-start justify-between gap-ui-sm">
              <div className="min-w-0">
                <p className="font-mono text-system-meta uppercase tracking-[0.08em] text-muted-foreground">
                  Field {index + 1}
                </p>
                <p className="mt-ui-hairline truncate font-mono text-system-control font-semibold text-slate-100">
                  {row.name || 'Unnamed field'}
                </p>
              </div>
              <Button
                type="button"
                size="iconSm"
                variant="ghost"
                disabled={disabled}
                onClick={() => remove(index)}
                aria-label={`Remove ${row.name || `field ${index + 1}`}`}
                className="shrink-0 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="h-icon-sm w-icon-sm" />
              </Button>
            </div>

            <div className="grid min-w-0 gap-ui-sm">
              <label className="grid min-w-0 gap-ui-xs">
                <span className="font-mono text-system-label font-medium text-muted-foreground">Name</span>
                <Input
                  value={row.name}
                  disabled={disabled}
                  spellCheck={false}
                  onChange={(event) => update(index, { name: event.target.value })}
                  aria-label={`Field ${index + 1} name`}
                />
              </label>

              <label className="grid min-w-0 gap-ui-xs">
                <span className="font-mono text-system-label font-medium text-muted-foreground">Description</span>
                <Textarea
                  value={row.description ?? ''}
                  disabled={disabled}
                  rows={2}
                  density="compact"
                  spellCheck
                  placeholder="Explain what this field means so the Agent can use it correctly"
                  onChange={(event) => update(index, { description: event.target.value })}
                  aria-label={`Field ${row.name || index + 1} description`}
                  className="resize-none"
                />
              </label>

              <div className="grid min-w-0 grid-cols-2 gap-ui-sm">
                <label className="grid min-w-0 gap-ui-xs">
                  <span className="font-mono text-system-label font-medium text-muted-foreground">Type</span>
                  <Select
                    value={row.type}
                    disabled={disabled}
                    options={CONTRACT_FIELD_TYPE_OPTIONS}
                    onChange={(event) => update(index, { type: event.target.value as ContractFieldType })}
                    aria-label={`Field ${row.name || index + 1} type`}
                  />
                </label>

                <label className="grid min-w-0 gap-ui-xs">
                  <span className="font-mono text-system-label font-medium text-muted-foreground">Scope</span>
                  <Select
                    value={row.scope}
                    disabled={disabled}
                    options={SCOPE_OPTIONS}
                    onChange={(event) => update(index, { scope: event.target.value as 'run' | 'session' })}
                    aria-label={`Field ${row.name || index + 1} scope`}
                  />
                </label>
              </div>

              <p className="font-sans text-product-caption leading-4 text-muted-foreground">
                {row.scope === 'session'
                  ? 'Session values persist across Runs in the current Session.'
                  : 'Run values must be supplied for each execution and are not reused automatically.'}
              </p>

              <div className="grid gap-ui-xs rounded-control border border-border/70 bg-surface/35 p-ui-sm">
                <label className="flex min-w-0 items-start justify-between gap-ui-sm">
                  <span className="min-w-0">
                    <span className="block font-mono text-system-control text-slate-100">Required at runtime</span>
                    <span className="mt-ui-hairline block font-sans text-product-caption leading-4 text-muted-foreground">
                      Reject the Run when this value cannot be resolved.
                    </span>
                  </span>
                  <Checkbox
                    checked={row.required}
                    disabled={disabled}
                    onChange={(event) => update(index, { required: event.target.checked })}
                    aria-label={`Field ${row.name || index + 1} required`}
                  />
                </label>

                <div className="border-t border-border/60" />

                <label className="flex min-w-0 items-start justify-between gap-ui-sm">
                  <span className="min-w-0">
                    <span className="block font-mono text-system-control text-slate-100">Expose to model</span>
                    <span className="mt-ui-hairline block font-sans text-product-caption leading-4 text-muted-foreground">
                      Include this value and its description in model-visible Runtime Context.
                    </span>
                  </span>
                  <Checkbox
                    checked={row.expose}
                    disabled={disabled}
                    onChange={(event) => update(index, { expose: event.target.checked })}
                    aria-label={`Field ${row.name || index + 1} model visibility`}
                  />
                </label>
              </div>
            </div>
          </section>
        ))}

        <div className="pt-ui-xs">
          <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={add}>
            <Plus className="h-icon-sm w-icon-sm" />
            Add field
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-w-0">
      <div className="grid grid-cols-[minmax(100px,1fr)_90px_54px_24px] items-center gap-ui-xs border-b border-border px-ui-xs pb-ui-xs font-mono text-system-label uppercase tracking-system-label text-muted-foreground">
        <span>Name</span>
        <span>Type</span>
        <span className="text-center">Required</span>
        <span />
      </div>

      <div className="divide-y divide-border/70">
        {rows.map((row, index) => (
          <div
            key={index}
            className="grid min-h-control grid-cols-[minmax(100px,1fr)_90px_54px_24px] items-center gap-ui-xs px-ui-xs py-ui-xs"
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
              className="pl-ui-xs pr-5"
              onChange={(event) => update(index, { type: event.target.value as ContractFieldType })}
              aria-label={`Field ${row.name || index + 1} type`}
            />
            <div className="flex justify-center">
              <Checkbox
                checked={row.required}
                disabled={disabled}
                onChange={(event) => update(index, { required: event.target.checked })}
                aria-label={`Field ${row.name || index + 1} required`}
              />
            </div>
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
