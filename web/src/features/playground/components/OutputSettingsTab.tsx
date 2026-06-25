import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { JsonEditor } from '@/components/ui/JsonEditor'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { useAgentEditor } from '../AgentEditorContext'
import { useLivePlaygroundSessionId } from '../lib/playground-session-store'
import { buildDraftRuntimePreview } from '../lib/build-draft-runtime-preview'
import { OutputContractHelpModal } from './OutputContractHelpModal'

const DEFAULT_SCHEMA = `{
  "message": "string",
  "confidence": "float"
}`

type HelpSection = 'contract' | 'preview'

function schemaToString(schema: unknown): string {
  if (typeof schema === 'string') return schema
  if (schema && typeof schema === 'object') return JSON.stringify(schema, null, 2)
  return DEFAULT_SCHEMA
}

function sourceLabel(source: 'current_draft' | 'draft_unsaved') {
  return source === 'draft_unsaved' ? 'Draft with unsaved changes' : 'Current draft'
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
  const { projectId = '', agentId = '' } = useParams<{ projectId: string; agentId: string }>()
  const sessionId = useLivePlaygroundSessionId(null)
  const { state, setField, toSnapshot, activeSource } = useAgentEditor()
  const { responseFormat } = state
  const [helpSection, setHelpSection] = useState<HelpSection | null>(null)

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
    sessionId,
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
            <div className="mb-1 flex items-center gap-1.5">
              <label className="block text-xs font-medium text-muted">Output contract</label>
              <HelpButton label="Explain output contracts" onClick={() => setHelpSection('contract')} />
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
              <div className="flex items-center gap-1.5">
                <p className="text-xs font-semibold text-muted uppercase tracking-wider">Draft Runtime Preview</p>
                <HelpButton label="Explain draft runtime preview" onClick={() => setHelpSection('preview')} />
              </div>
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

      <OutputContractHelpModal
        open={helpSection !== null}
        initialSection={helpSection ?? 'contract'}
        onClose={() => setHelpSection(null)}
      />
    </div>
  )
}
