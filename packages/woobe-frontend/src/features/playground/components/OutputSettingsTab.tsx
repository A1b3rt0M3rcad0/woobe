import { useState } from 'react'
import { CircleHelp } from 'lucide-react'
import { JsonEditor } from '@/components/ui/JsonEditor'
import { useAgentEditor } from '../AgentEditorContext'
import { OutputContractHelpModal } from './OutputContractHelpModal'
import { cn } from '@/lib/utils'

const DEFAULT_SCHEMA = `{
  "message": "string",
  "confidence": "float"
}`

function schemaToString(schema: unknown): string {
  if (typeof schema === 'string') return schema
  if (schema && typeof schema === 'object') return JSON.stringify(schema, null, 2)
  return ''
}

function hasMaterializedSchema(schema: unknown): boolean {
  if (typeof schema === 'string') return schema.trim().length > 0
  return Boolean(schema && typeof schema === 'object')
}

function schemaError(schema: unknown): string | null {
  if (!hasMaterializedSchema(schema)) return 'Define an Output contract before saving or running with JSON output.'
  if (typeof schema !== 'string') {
    return schema && typeof schema === 'object' && !Array.isArray(schema)
      ? null
      : 'Output contract must be a JSON object.'
  }
  try {
    const parsed = JSON.parse(schema)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return 'Output contract must be a JSON object.'
    return null
  } catch {
    return 'Output contract contains invalid JSON.'
  }
}

function HelpButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted transition-colors hover:bg-accent/60 hover:text-primary-light focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60"
      aria-label={label}
      title={label}
    >
      <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" />
    </button>
  )
}

export function OutputSettingsTab({ standalone = false }: { standalone?: boolean }) {
  const { state, setField } = useAgentEditor()
  const { responseFormat } = state
  const [showHelp, setShowHelp] = useState(false)

  const setMode = (mode: 'text' | 'json') => {
    const enabled = mode === 'json'
    setField('responseFormat', {
      ...responseFormat,
      enabled,
      type: mode,
      strict: true,
      schema: enabled && !hasMaterializedSchema(responseFormat.schema)
        ? DEFAULT_SCHEMA
        : responseFormat.schema,
    })
  }

  const handleSchemaChange = (value: string) => {
    setField('responseFormat', { ...responseFormat, strict: true, schema: value })
  }

  if (standalone) {
    const error = responseFormat.enabled && responseFormat.type === 'json' ? schemaError(responseFormat.schema) : null
    return (
      <>
        <section aria-label="Output" className="space-y-5 p-4">
          <div>
            <p className="text-xs font-semibold text-white">Output</p>
            <p className="mt-1 text-[11px] leading-4 text-muted">Choose free-form text or enforce a structured JSON contract for this Agent.</p>
          </div>

          <div className="grid grid-cols-2 rounded-lg border border-border bg-background/35 p-1" role="group" aria-label="Output mode">
            {(['text', 'json'] as const).map(mode => {
              const active = responseFormat.type === mode && responseFormat.enabled === (mode === 'json')
              return (
                <button
                  key={mode}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setMode(mode)}
                  className={cn(
                    'h-9 rounded-md text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60',
                    active ? 'bg-surface text-white shadow-sm' : 'text-muted hover:text-white',
                  )}
                >
                  {mode === 'text' ? 'Text' : 'JSON'}
                </button>
              )
            })}
          </div>

          {responseFormat.enabled && responseFormat.type === 'json' ? (
            <div>
              <div className="mb-2 flex items-center gap-0.5">
                <label className="block text-xs font-medium text-white">Output contract</label>
                <HelpButton label="Explain output contracts" onClick={() => setShowHelp(true)} />
              </div>
              <JsonEditor
                value={schemaToString(responseFormat.schema)}
                onChange={handleSchemaChange}
                editable
                actions={['format', 'validate', 'clear']}
                minHeight={200}
                maxHeight={420}
                error={error}
                placeholder='{ "message": "string" }'
              />
              <p className="mt-2 text-[11px] leading-relaxed text-muted">
                Type names such as <code>"string"</code>, <code>"number"</code> and <code>"float"</code> define expected output types. They are not literal values.
              </p>
            </div>
          ) : (
            <div className="rounded-lg border border-border/80 bg-background/30 p-3">
              <p className="text-xs font-medium text-white">Free-form text</p>
              <p className="mt-1 text-[11px] leading-4 text-muted">The runtime returns natural text without applying a structured output contract. Any previously configured JSON contract is preserved if you switch back.</p>
            </div>
          )}
        </section>
        <OutputContractHelpModal open={showHelp} onClose={() => setShowHelp(false)} />
      </>
    )
  }

  return (
    <div className="p-4">
      <div className="rounded-xl border border-border bg-surface">
        <div className="space-y-3 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">JSON Output</p>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="json-enabled"
              checked={responseFormat.enabled}
              onChange={(e) => setMode(e.target.checked ? 'json' : 'text')}
              className="h-4 w-4 rounded border-border bg-background"
            />
            <label htmlFor="json-enabled" className="text-sm font-medium text-muted">
              Enable JSON output
            </label>
          </div>
          <div>
            <div className="mb-1 flex items-center gap-0.5">
              <label className="block text-xs font-medium text-muted">Output contract</label>
              <HelpButton label="Explain output contracts" onClick={() => setShowHelp(true)} />
            </div>
            <JsonEditor
              value={schemaToString(responseFormat.schema)}
              onChange={handleSchemaChange}
              editable
              disabled={!responseFormat.enabled}
              actions={['format', 'validate', 'clear']}
              minHeight={180}
              placeholder='{ "message": "string" }'
            />
            <p className="mt-2 text-[11px] leading-relaxed text-muted">
              Type names such as <code>"string"</code>, <code>"number"</code> and <code>"float"</code> define expected output types. They are not literal values.
            </p>
          </div>
        </div>
      </div>

      <OutputContractHelpModal open={showHelp} onClose={() => setShowHelp(false)} />
    </div>
  )
}
