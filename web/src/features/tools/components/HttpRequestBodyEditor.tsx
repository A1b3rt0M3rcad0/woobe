import { useMemo, useState } from 'react'
import { Braces, Plus, WandSparkles, X } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { toast } from 'sonner'

type BodyMode = 'fields' | 'raw'
type BodyFieldType = 'text' | 'number' | 'boolean' | 'parameter' | 'json'

interface BodyField {
  key: string
  type: BodyFieldType
  value: string
}

interface HttpRequestBodyEditorProps {
  value: string
  onChange: (value: string) => void
}

const FIELD_TYPES = [
  { value: 'text', label: 'Text' },
  { value: 'parameter', label: 'Agent parameter' },
  { value: 'number', label: 'Number' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'json', label: 'JSON' },
]

function parseObject(value: string): Record<string, unknown> | null {
  if (!value.trim()) return {}
  try {
    const parsed = JSON.parse(value)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : null
  } catch {
    return null
  }
}

function inferField(key: string, value: unknown): BodyField {
  if (typeof value === 'string') {
    const parameter = value.match(/^\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}$/)
    return parameter
      ? { key, type: 'parameter', value: parameter[1] }
      : { key, type: 'text', value }
  }
  if (typeof value === 'number') return { key, type: 'number', value: String(value) }
  if (typeof value === 'boolean') return { key, type: 'boolean', value: String(value) }
  return { key, type: 'json', value: JSON.stringify(value, null, 2) }
}

function fieldsFromValue(value: string): BodyField[] | null {
  const parsed = parseObject(value)
  return parsed ? Object.entries(parsed).map(([key, item]) => inferField(key, item)) : null
}

function fieldValue(field: BodyField): unknown {
  if (field.type === 'parameter') return `{{${field.value.trim() || 'parameter'}}}`
  if (field.type === 'number') {
    const parsed = Number(field.value)
    return Number.isFinite(parsed) ? parsed : 0
  }
  if (field.type === 'boolean') return field.value === 'true'
  if (field.type === 'json') {
    try { return JSON.parse(field.value || 'null') } catch { return field.value }
  }
  return field.value
}

function serializeFields(fields: BodyField[]): string {
  const body = Object.fromEntries(
    fields
      .filter((field) => field.key.trim())
      .map((field) => [field.key.trim(), fieldValue(field)]),
  )
  return JSON.stringify(body, null, 2)
}

export function HttpRequestBodyEditor({ value, onChange }: HttpRequestBodyEditorProps) {
  const parsedFields = useMemo(() => fieldsFromValue(value), [value])
  const [mode, setMode] = useState<BodyMode>(parsedFields ? 'fields' : 'raw')
  const fields = parsedFields || []

  const useFieldsMode = () => {
    if (!parsedFields) {
      toast.error('The current body must be a JSON object before using the field editor.')
      return
    }
    setMode('fields')
  }

  const updateFields = (next: BodyField[]) => onChange(serializeFields(next))

  const addField = () => {
    const used = new Set(fields.map((field) => field.key))
    let index = fields.length + 1
    let key = `field_${index}`
    while (used.has(key)) {
      index += 1
      key = `field_${index}`
    }
    updateFields([...fields, { key, type: 'parameter', value: key }])
  }

  const updateField = (index: number, patch: Partial<BodyField>) => {
    updateFields(fields.map((field, current) => current === index ? { ...field, ...patch } : field))
  }

  const removeField = (index: number) => updateFields(fields.filter((_, current) => current !== index))

  const formatRaw = () => {
    try {
      onChange(JSON.stringify(JSON.parse(value || '{}'), null, 2))
      toast.success('JSON formatted')
    } catch {
      toast.error('Body is not valid JSON')
    }
  }

  const insertParameterExample = () => {
    if (!value.trim()) {
      onChange(JSON.stringify({ parameter: '{{parameter}}' }, null, 2))
      return
    }
    onChange(`${value}\n{{parameter}}`)
  }

  return (
    <div className="space-y-3 rounded-xl border border-border/80 bg-background/45 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Request body</p>
          <p className="mt-1 text-[11px] text-muted">Build a JSON object visually or edit the raw payload.</p>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-border/80 bg-background/60 p-1">
          <Button type="button" size="sm" variant={mode === 'fields' ? 'secondary' : 'ghost'} onClick={useFieldsMode}>Fields</Button>
          <Button type="button" size="sm" variant={mode === 'raw' ? 'secondary' : 'ghost'} onClick={() => setMode('raw')}>Raw JSON</Button>
        </div>
      </div>

      {mode === 'fields' ? (
        <div className="space-y-2">
          {fields.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border/80 p-4 text-center text-xs text-muted">
              No body fields yet.
            </div>
          ) : fields.map((field, index) => (
            <div key={`${field.key}-${index}`} className="grid gap-2 rounded-lg border border-border/70 bg-surface/50 p-2 md:grid-cols-[minmax(120px,0.8fr)_150px_minmax(160px,1.4fr)_32px]">
              <Input
                value={field.key}
                onChange={(event) => updateField(index, { key: event.target.value })}
                placeholder="Field name"
                className="font-mono text-xs"
              />
              <Select
                value={field.type}
                onChange={(event) => updateField(index, {
                  type: event.target.value as BodyFieldType,
                  value: event.target.value === 'boolean' ? 'false' : field.value,
                })}
                options={FIELD_TYPES}
              />
              {field.type === 'boolean' ? (
                <Select
                  value={field.value === 'true' ? 'true' : 'false'}
                  onChange={(event) => updateField(index, { value: event.target.value })}
                  options={[{ value: 'false', label: 'false' }, { value: 'true', label: 'true' }]}
                />
              ) : (
                <Input
                  value={field.value}
                  onChange={(event) => updateField(index, { value: event.target.value })}
                  placeholder={field.type === 'parameter' ? 'parameter_name' : field.type === 'json' ? '{"nested":true}' : 'Value'}
                  className={field.type === 'parameter' || field.type === 'json' ? 'font-mono text-xs' : undefined}
                />
              )}
              <Button type="button" size="sm" variant="ghost" className="text-red-300" onClick={() => removeField(index)}>
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
          <Button type="button" size="sm" variant="outline" onClick={addField}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Add body field
          </Button>
          <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 p-2 text-[11px] leading-5 text-muted">
            Agent parameters are saved as <code>{'{{parameter_name}}'}</code> and automatically become inputs in the route contract.
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <Textarea
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder={'{\n  "query": "{{query}}",\n  "limit": 10\n}'}
            className="min-h-[180px] font-mono text-xs"
          />
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" onClick={formatRaw}>
              <WandSparkles className="mr-1.5 h-3.5 w-3.5" />
              Format JSON
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={insertParameterExample}>
              <Braces className="mr-1.5 h-3.5 w-3.5" />
              Insert parameter
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
