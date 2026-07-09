import { useState } from 'react'
import { JsonEditor } from '@/components/ui/JsonEditor'
import { useAgentEditor } from '../AgentEditorContext'
import { OutputContractHelpModal } from './OutputContractHelpModal'

const DEFAULT_SCHEMA = `{
  "message": "string",
  "confidence": "float"
}`

function schemaToString(schema: unknown): string {
  if (typeof schema === 'string') return schema
  if (schema && typeof schema === 'object') return JSON.stringify(schema, null, 2)
  return DEFAULT_SCHEMA
}

function hasMaterializedSchema(schema: unknown): boolean {
  if (typeof schema === 'string') return schema.trim().length > 0
  return Boolean(schema && typeof schema === 'object')
}

function HelpButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-border bg-background text-[10px] font-semibold text-muted transition-colors hover:border-primary/50 hover:text-primary"
      aria-label={label}
      title={label}
    >
      ?
    </button>
  )
}

export function OutputSettingsTab() {
  const { state, setField } = useAgentEditor()
  const { responseFormat } = state
  const [showHelp, setShowHelp] = useState(false)

  const handleToggle = (enabled: boolean) => {
    setField('responseFormat', {
      ...responseFormat,
      enabled,
      type: enabled ? 'json' : 'text',
      strict: true,
      schema: enabled && !hasMaterializedSchema(responseFormat.schema)
        ? DEFAULT_SCHEMA
        : responseFormat.schema,
    })
  }

  const handleSchemaChange = (value: string) => {
    setField('responseFormat', { ...responseFormat, strict: true, schema: value })
  }

  return (
    <div className="p-4">
      <div className="rounded-xl border border-border bg-surface">
        <div className="p-4 space-y-3">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider">JSON Output</p>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="json-enabled"
              checked={responseFormat.enabled}
              onChange={(e) => handleToggle(e.target.checked)}
              className="h-4 w-4 rounded border-border bg-background"
            />
            <label htmlFor="json-enabled" className="text-sm font-medium text-muted">
              Enable JSON output
            </label>
          </div>
          <div>
            <div className="mb-1 flex items-center gap-1.5">
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
