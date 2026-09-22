import { useState } from 'react'
import { FileText, Plus, Trash2 } from 'lucide-react'
import { Button, Checkbox, Dialog, Input, Select, Textarea } from '@woobe/ui'

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
  const [descriptionFieldIndex, setDescriptionFieldIndex] = useState<number | null>(null)

  const update = (index: number, patch: Partial<ContractFieldRow>) => {
    onChange(rows.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row))
  }

  const remove = (index: number) => {
    onChange(rows.filter((_, rowIndex) => rowIndex !== index))
    setDescriptionFieldIndex((current) => {
      if (current === index) return null
      if (current !== null && current > index) return current - 1
      return current
    })
  }

  const add = () => onChange([
    ...rows,
    {
      name: nextFieldName(rows),
      type: 'string',
      required: false,
      expose: kind === 'output',
      description: '',
    },
  ])

  if (kind === 'external') {
    const descriptionRow = descriptionFieldIndex === null ? null : rows[descriptionFieldIndex] ?? null

    return (
      <div className="min-w-0">
        <div className="grid grid-cols-[minmax(88px,1fr)_78px_42px_46px_28px_28px] items-center gap-ui-xs border-b border-border px-ui-xs pb-ui-xs font-mono text-system-label uppercase tracking-system-label text-muted-foreground">
          <span>Name</span>
          <span>Type</span>
          <span className="text-center" title="Required at runtime">Req.</span>
          <span className="text-center" title="Expose to model">Model</span>
          <span />
          <span />
        </div>

        <div className="divide-y divide-border/70">
          {rows.map((row, index) => (
            <div
              key={index}
              className="grid min-h-control grid-cols-[minmax(88px,1fr)_78px_42px_46px_28px_28px] items-center gap-ui-xs px-ui-xs py-ui-xs"
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
                onClick={() => setDescriptionFieldIndex(index)}
                aria-label={`Edit ${row.name || `field ${index + 1}`} description`}
                title={row.description?.trim() ? 'Edit description' : 'Add description'}
                className={row.description?.trim()
                  ? 'text-primary-light hover:text-primary-light'
                  : 'text-muted-foreground hover:text-slate-100'}
              >
                <FileText className="h-icon-sm w-icon-sm" />
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
          ))}
        </div>

        <div className="border-t border-border/70 pt-ui-sm">
          <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={add}>
            <Plus className="h-icon-sm w-icon-sm" />
            Add field
          </Button>
        </div>

        <Dialog
          open={descriptionRow !== null}
          onClose={() => setDescriptionFieldIndex(null)}
          title="Field description"
          className="max-w-lg"
          scrollMode="content"
        >
          {descriptionRow && descriptionFieldIndex !== null ? (
            <div className="grid gap-ui-md">
              <div className="rounded-control border border-border bg-background/35 px-ui-sm py-ui-sm">
                <p className="font-mono text-system-label uppercase tracking-system-label text-muted-foreground">
                  {descriptionRow.name || `Field ${descriptionFieldIndex + 1}`}
                </p>
                <p className="mt-ui-hairline font-sans text-product-caption text-muted-foreground">
                  {descriptionRow.expose
                    ? 'This description is sent with the value when the field is exposed to the model.'
                    : 'This description remains contract metadata while model exposure is disabled.'}
                </p>
              </div>

              <label className="grid gap-ui-xs">
                <span className="font-mono text-system-label font-medium text-muted-foreground">Description</span>
                <Textarea
                  value={descriptionRow.description ?? ''}
                  disabled={disabled}
                  rows={4}
                  density="compact"
                  spellCheck
                  placeholder="Explain what this field means so the Agent can use it correctly"
                  onChange={(event) => update(descriptionFieldIndex, { description: event.target.value })}
                  aria-label={`Field ${descriptionRow.name || descriptionFieldIndex + 1} description`}
                />
              </label>

              <div className="flex justify-end border-t border-border/70 pt-ui-sm">
                <Button type="button" size="sm" variant="outline" onClick={() => setDescriptionFieldIndex(null)}>
                  Done
                </Button>
              </div>
            </div>
          ) : null}
        </Dialog>
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
