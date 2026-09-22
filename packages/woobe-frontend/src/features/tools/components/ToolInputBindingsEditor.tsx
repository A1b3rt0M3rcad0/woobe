import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import type { ToolInputBindings } from '@/features/tools/types'

export interface ToolInputDescriptor {
  name: string
  type: string
  required: boolean
}

interface ToolInputBindingsEditorProps {
  schema?: Record<string, unknown> | null
  bindings?: ToolInputBindings
  disabled?: boolean
  onChange: (bindings: ToolInputBindings) => void
}

const SOURCE_OPTIONS = [
  { value: 'agent', label: 'Agent' },
  { value: 'context', label: 'External Context' },
  { value: 'project_environment', label: 'Project Environment' },
]

function schemaType(value: unknown): string {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return 'Any'
  const raw = (value as Record<string, unknown>).type
  if (Array.isArray(raw)) return raw.map(String).join(' | ')
  return typeof raw === 'string' && raw.trim() ? raw : 'Any'
}

export function toolInputDescriptors(schema?: Record<string, unknown> | null): ToolInputDescriptor[] {
  if (!schema || typeof schema !== 'object') return []
  const rawProperties = schema.properties
  if (!rawProperties || typeof rawProperties !== 'object' || Array.isArray(rawProperties)) return []
  const required = new Set(Array.isArray(schema.required) ? schema.required.map(String) : [])
  return Object.entries(rawProperties as Record<string, unknown>).map(([name, definition]) => ({
    name,
    type: schemaType(definition),
    required: required.has(name),
  }))
}

export function normalizeToolInputBindings(bindings?: ToolInputBindings): ToolInputBindings {
  return Object.fromEntries(
    Object.entries(bindings || {})
      .map(([target, binding]) => [
        target.trim(),
        {
          source: {
            kind: binding?.source?.kind === 'project_environment' ? 'project_environment' as const : 'context' as const,
            field: String(binding?.source?.field || '').trim(),
          },
        },
      ] as const)
      .filter(([target, binding]) => Boolean(target) && Boolean(binding.source.field)),
  )
}

export function toolInputBindingsForSchema(
  schema: Record<string, unknown> | null | undefined,
  bindings?: ToolInputBindings,
): ToolInputBindings {
  const allowed = new Set(toolInputDescriptors(schema).map((input) => input.name))
  return Object.fromEntries(
    Object.entries(normalizeToolInputBindings(bindings))
      .filter(([target]) => allowed.has(target)),
  )
}

export function invalidToolInputBindingTargets(bindings?: ToolInputBindings): string[] {
  return Object.entries(bindings || {})
    .filter(([target, binding]) => !target.trim() || !String(binding?.source?.field || '').trim())
    .map(([target]) => target)
}

export function ToolInputBindingsEditor({
  schema,
  bindings = {},
  disabled = false,
  onChange,
}: ToolInputBindingsEditorProps) {
  const inputs = toolInputDescriptors(schema)

  const setSource = (name: string, source: string) => {
    if (source === 'context' || source === 'project_environment') {
      onChange({
        ...bindings,
        [name]: {
          source: {
            kind: source,
            field: bindings[name]?.source?.field || name,
          },
        },
      })
      return
    }
    const next = { ...bindings }
    delete next[name]
    onChange(next)
  }

  const setBindingField = (name: string, field: string) => {
    const binding = bindings[name]
    if (!binding) return
    onChange({
      ...bindings,
      [name]: {
        source: {
          kind: binding.source.kind,
          field,
        },
      },
    })
  }

  if (!inputs.length) return null

  return (
    <div className="overflow-hidden rounded-xl border border-border/75 bg-background/20">
      <div className="grid grid-cols-[minmax(110px,1fr)_76px_150px_minmax(150px,1.1fr)] items-center gap-2 border-b border-border/70 bg-background/30 px-3 py-2 font-mono text-[9px] uppercase tracking-wide text-muted">
        <span>Input</span>
        <span>Type</span>
        <span>Source</span>
        <span>Binding</span>
      </div>

      <div className="divide-y divide-border/70">
        {inputs.map((input) => {
          const binding = bindings[input.name]
          const runtimeBound = Boolean(binding)
          return (
            <div
              key={input.name}
              className="grid min-h-[48px] grid-cols-[minmax(110px,1fr)_76px_150px_minmax(150px,1.1fr)] items-center gap-2 px-3 py-2"
            >
              <div className="min-w-0">
                <p className="truncate font-mono text-[11px] font-medium text-white">{input.name}</p>
                {input.required ? <p className="mt-0.5 text-[9px] text-muted">required</p> : null}
              </div>
              <span className="truncate font-mono text-[10px] capitalize text-muted">{input.type}</span>
              <Select
                value={binding?.source.kind || 'agent'}
                options={SOURCE_OPTIONS}
                disabled={disabled}
                onChange={(event) => setSource(input.name, event.target.value)}
                aria-label={`${input.name} input source`}
                className="text-xs"
              />
              {runtimeBound && binding ? (
                <Input
                  value={binding.source.field}
                  disabled={disabled}
                  spellCheck={false}
                  onChange={(event) => setBindingField(input.name, event.target.value)}
                  placeholder={binding.source.kind === 'project_environment' ? 'Project Environment key' : 'External Context field'}
                  aria-label={`${input.name} ${binding.source.kind === 'project_environment' ? 'Project Environment key' : 'External Context field'}`}
                  className="font-mono text-xs"
                />
              ) : (
                <span className="px-2 font-mono text-[10px] text-muted">Model-provided</span>
              )}
            </div>
          )
        })}
      </div>

      <div className="border-t border-border/70 px-3 py-2">
        <p className="text-[10px] leading-4 text-muted">
          Runtime bindings are removed from the model-visible Tool schema. External Context comes from the immutable Run snapshot; Project Environment comes from the selected draft/staging/production execution environment and is never exposed to the model.
        </p>
      </div>
    </div>
  )
}
