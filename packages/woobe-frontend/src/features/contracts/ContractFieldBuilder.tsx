import { useState } from 'react'
import { ChevronDown, ChevronRight, Plus, Trash2 } from 'lucide-react'
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
  const [expandedExternalIndex, setExpandedExternalIndex] = useState<number | null>(null)

  const update = (index: number, patch: Partial<ContractFieldRow>) => {
    onChange(rows.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row))
  }

  const remove = (index: number) => {
    onChange(rows.filter((_, rowIndex) => rowIndex !== index))
    setExpandedExternalIndex((current) => {
      if (current === index) return null
      if (current !== null && current > index) return current - 1
      return current
    })
  }

  const add = () => {
    const nextIndex = rows.length
    onChange([
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
    if (kind === 'external') setExpandedExternalIndex(nextIndex)
  }

  if (kind === 'external') {
    return (
      <div className="min-w-0">
        <div className="mb-ui-xs flex items-center justify-between gap-ui-sm">
          <span className="font-mono text-system-meta text-muted-foreground">
            {rows.length} field{rows.length === 1 ? '' : 's'}
          </span>
          <Button type="button" size="xs" variant="ghost" disabled={disabled} onClick={add}>
            <Plus className="h-icon-sm w-icon-sm" />
            Add field
          </Button>
        </div>

        <div className="overflow-hidden rounded-control border border-border/80 bg-background/20">
          <div className="grid grid-cols-[minmax(88px,1fr)_72px_72px_34px_38px_28px_28px] items-center gap-ui-xs border-b border-border/70 bg-surface/35 px-ui-xs py-ui-xs font-mono text-system-meta uppercase tracking-[0.06em] text-muted-foreground">
            <span>Name</span>
            <span>Type</span>
            <span>Scope</span>
            <span className="text-center" title="Required at runtime">Req.</span>
            <span className="text-center" title="Expose to model">Model</span>
            <span />
            <span />
          </div>

          <div className="divide-y divide-border/70">
            {rows.map((row, index) => {
              const expanded = expandedExternalIndex === index
              return (
                <div key={index} className="min-w-0 bg-background/10">
                  <div className="grid min-h-control grid-cols-[minmax(88px,1fr)_72px_72px_34px_38px_28px_28px] items-center gap-ui-xs px-ui-xs py-ui-xs">
                    <Input
                      value={row.name}
                      disabled={disabled}
                      spellCheck={false}
                      className="!h-control-sm !px-ui-xs"
                      onChange={(event) => update(index, { name: event.target.value })}
                      aria-label={`Field ${index + 1} name`}
                    />

                    <Select
                      value={row.type}
                      disabled={disabled}
                      options={CONTRACT_FIELD_TYPE_OPTIONS}
                      className="!h-control-sm !pl-ui-xs !pr-5"
                      onChange={(event) => update(index, { type: event.target.value as ContractFieldType })}
                      aria-label={`Field ${row.name || index + 1} type`}
                    />

                    <Select
                      value={row.scope}
                      disabled={disabled}
                      options={SCOPE_OPTIONS}
                      className="!h-control-sm !pl-ui-xs !pr-5"
                      onChange={(event) => update(index, { scope: event.target.value as 'run' | 'session' })}
                      aria-label={`Field ${row.name || index + 1} scope`}
                    />

                    <div className="flex justify-center" title="Required at runtime">
                      <Checkbox
                        checked={row.required}
                        disabled={disabled}
                        onChange={(event) => update(index, { required: event.target.checked })}
                        aria-label={`Field ${row.name || index + 1} required`}
                      />
                    </div>

                    <div className="flex justify-center" title="Expose to model">
                      <Checkbox
                        checked={row.expose}
                        disabled={disabled}
                        onChange={(event) => update(index, { expose: event.target.checked })}
                        aria-label={`Field ${row.name || index + 1} model visibility`}
                      />
                    </div>

                    <Button
                      type="button"
                      size="iconXs"
                      variant="ghost"
                      disabled={disabled}
                      onClick={() => setExpandedExternalIndex(expanded ? null : index)}
                      aria-label={expanded ? `Collapse ${row.name || `field ${index + 1}`}` : `Edit details for ${row.name || `field ${index + 1}`}`}
                      aria-expanded={expanded}
                      title={expanded ? 'Collapse details' : 'Edit description and field details'}
                      className="text-muted-foreground hover:text-slate-100"
                    >
                      {expanded
                        ? <ChevronDown className="h-icon-sm w-icon-sm" />
                        : <ChevronRight className="h-icon-sm w-icon-sm" />}
                    </Button>

                    <Button
                      type="button"
                      size="iconXs"
                      variant="ghost"
                      disabled={disabled}
                      onClick={() => remove(index)}
                      aria-label={`Remove ${row.name || `field ${index + 1}`}`}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="h-icon-sm w-icon-sm" />
                    </Button>
                  </div>

                  {expanded ? (
                    <div className="grid min-w-0 gap-ui-xs border-t border-border/60 bg-surface/20 px-ui-sm py-ui-sm">
                      <label className="grid min-w-0 gap-ui-xs">
                        <span className="flex items-center justify-between gap-ui-sm font-mono text-system-label text-muted-foreground">
                          <span>Description</span>
                          <span className="font-sans text-product-caption">
                            {row.expose ? 'Visible to the model with the value' : 'Metadata only while model exposure is off'}
                          </span>
                        </span>
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

                      <p className="font-sans text-product-caption leading-4 text-muted-foreground">
                        {row.scope === 'session'
                          ? 'Session · persisted for the current Session and reused across later Runs.'
                          : 'Run · supplied for one execution and not reused automatically.'}
                        {row.required ? ' Required · the Run is rejected when unresolved.' : ''}
                      </p>
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>

          {rows.length === 0 ? (
            <div className="px-ui-sm py-ui-md text-center font-sans text-product-caption text-muted-foreground">
              No External Context fields yet.
            </div>
          ) : null}
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
