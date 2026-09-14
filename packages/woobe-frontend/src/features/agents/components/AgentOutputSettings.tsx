import { useState } from 'react'
import { FileJson2, HelpCircle } from 'lucide-react'
import { Alert, AlertDescription, Button, Checkbox, PanelHeader } from '@woobe/ui'

import { JsonEditor } from '@/components/ui/JsonEditor'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { OutputContractHelpModal } from '@/features/playground/components/OutputContractHelpModal'
import { outputContractError } from '../editorValidation'

const DEFAULT_SCHEMA = `{
  "message": "string",
  "confidence": "float"
}`

function schemaText(value: unknown) {
  return typeof value === 'string' ? value : value && typeof value === 'object' ? JSON.stringify(value, null, 2) : DEFAULT_SCHEMA
}

export function AgentOutputSettings() {
  const { state, setField } = useAgentEditor()
  const [helpOpen, setHelpOpen] = useState(false)
  const enabled = state.responseFormat.enabled
  const error = outputContractError(state)

  const toggle = (next: boolean) => setField('responseFormat', {
    ...state.responseFormat,
    enabled: next,
    type: next ? 'json' : 'text',
    strict: true,
    schema: next && !state.responseFormat.schema ? DEFAULT_SCHEMA : state.responseFormat.schema,
  })

  return (
    <div className="min-w-0 max-w-full p-ui-md">
      <section className="min-w-0 max-w-full rounded-container border border-border bg-surface/[0.72]">
        <PanelHeader
          icon={<FileJson2 className="h-icon w-icon" />}
          title="JSON output"
          description="Define the structured response contract consumed by downstream code."
          actions={(
            <Button type="button" variant="ghost" size="iconSm" onClick={() => setHelpOpen(true)} aria-label="Explain output contracts">
              <HelpCircle className="h-icon w-icon" />
            </Button>
          )}
        />

        <div className="grid min-w-0 gap-ui-md p-ui-md">
          <label className="flex min-h-control min-w-0 items-center justify-between gap-ui-md rounded-container border border-border bg-background/20 px-ui-md py-ui-sm">
            <span className="min-w-0">
              <span className="block font-mono text-system-label font-semibold text-accent-foreground">Enable JSON output</span>
              <span className="mt-ui-xs block font-sans text-product-caption text-muted-foreground">Strict validation remains enabled when the contract is active.</span>
            </span>
            <Checkbox checked={enabled} onChange={(event) => toggle(event.target.checked)} />
          </label>

          <div className="min-w-0 max-w-full">
            <label className="mb-ui-sm block font-mono text-system-label font-medium uppercase tracking-system-label text-muted-foreground">Output contract</label>
            <JsonEditor
              value={schemaText(state.responseFormat.schema)}
              onChange={(value) => setField('responseFormat', { ...state.responseFormat, strict: true, schema: value })}
              editable
              disabled={!enabled}
              actions={['format', 'validate', 'clear']}
              placeholder='{ "message": "string" }'
            />
            {error ? (
              <Alert variant="destructive" className="mt-ui-sm">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
            <p className="mt-ui-sm font-sans text-product-caption text-muted-foreground">
              Type declarations such as <code>"string"</code>, <code>"number"</code> and <code>"float"</code> describe the expected values.
            </p>
          </div>
        </div>
      </section>
      <OutputContractHelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
