import { useParams } from 'react-router-dom'
import { JsonEditor } from '@/components/ui/JsonEditor'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { useAgentEditor } from '../AgentEditorContext'
import { buildDraftRuntimePreview } from '../lib/build-draft-runtime-preview'

const DEFAULT_SCHEMA = `{
  "message": "string",
  "confidence": "float"
}`

function schemaToString(schema: unknown): string {
  if (typeof schema === 'string') return schema
  if (schema && typeof schema === 'object') return JSON.stringify(schema, null, 2)
  return DEFAULT_SCHEMA
}

function sourceLabel(source: 'current_draft' | 'draft_unsaved') {
  return source === 'draft_unsaved' ? 'Draft with unsaved changes' : 'Current draft'
}

export function OutputSettingsTab() {
  const { projectId = '', agentId = '' } = useParams<{ projectId: string; agentId: string }>()
  const { state, setField, toSnapshot, activeSource } = useAgentEditor()
  const { responseFormat } = state

  const handleToggle = (enabled: boolean) => {
    setField('responseFormat', {
      ...responseFormat,
      enabled,
      type: enabled ? 'json' : 'text',
    })
  }

  const handleStrictToggle = (strict: boolean) => {
    setField('responseFormat', { ...responseFormat, strict })
  }

  const handleSchemaChange = (value: string) => {
    setField('responseFormat', { ...responseFormat, schema: value })
  }

  const draftRuntimePreview = buildDraftRuntimePreview({
    projectId,
    agentId,
    sessionId: null,
    activeSource,
    snapshot: toSnapshot(),
  })

  return (
    <div className="p-4 space-y-4">
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
            <label className="block text-xs font-medium text-muted mb-1">Output contract</label>
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
              Contract values such as <code>"string"</code>, <code>"number"</code> and <code>"float"</code> are type declarations.
              The model output must return real values, for example <code>{'{ "confidence": 0.87 }'}</code>, not <code>{'{ "confidence": "number" }'}</code>.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="json-strict"
              checked={responseFormat.strict}
              onChange={(e) => handleStrictToggle(e.target.checked)}
              disabled={!responseFormat.enabled}
              className="h-4 w-4 rounded border-border bg-background"
            />
            <label htmlFor="json-strict" className="text-sm font-medium text-muted">
              Strict mode
            </label>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface">
        <div className="p-4 space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-muted uppercase tracking-wider">Draft Runtime Preview</p>
              <p className="mt-1 text-[11px] leading-relaxed text-muted">
                Exact current draft configuration sent as <code>snapshot_override</code> when this agent runs in the playground.
              </p>
            </div>
            <span className="shrink-0 rounded-full border border-border bg-background px-2 py-0.5 text-[10px] text-muted">
              {sourceLabel(activeSource)}
            </span>
          </div>
          <JsonCodeBlock
            value={draftRuntimePreview}
            title="Draft runtime payload"
            maxHeight={560}
            actions={['copy', 'format', 'expand']}
          />
        </div>
      </div>
    </div>
  )
}
