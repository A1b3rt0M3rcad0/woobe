import { useState } from 'react'
import { FileJson2, HelpCircle } from 'lucide-react'
import { Alert, AlertDescription, Button, Checkbox, PanelHeader } from '@woobe/ui'

import { ContractFieldBuilder } from '@/features/contracts/ContractFieldBuilder'
import { outputSchemaFromRows, outputSchemaRows } from '@/features/contracts/contractFields'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { OutputContractHelpModal } from '@/features/playground/components/OutputContractHelpModal'
import { outputContractError } from '../editorValidation'

export function AgentOutputSettings() {
  const { state, setField } = useAgentEditor()
  const [helpOpen, setHelpOpen] = useState(false)
  const enabled = state.responseFormat.enabled
  const rows = outputSchemaRows(state.responseFormat.schema)
  const error = outputContractError(state)

  const toggle = (next: boolean) => setField('responseFormat', {
    ...state.responseFormat,
    enabled: next,
    type: next ? 'json' : 'text',
    strict: true,
    schema: next ? outputSchemaFromRows(rows) : state.responseFormat.schema,
  })

  return (
    <div className="min-w-0 max-w-full p-ui-sm 2xl:p-ui-md">
      <section className="min-w-0 max-w-full rounded-container border border-border bg-surface/[0.72]">
        <PanelHeader
          icon={<FileJson2 className="h-icon w-icon" />}
          title="Output Contract"
          description="Define the typed structured response consumed by downstream code."
          actions={(
            <div className="flex items-center gap-ui-sm">
              <label className="flex items-center gap-ui-sm font-mono text-system-label text-muted-foreground">
                {enabled ? 'Enabled' : 'Disabled'}
                <Checkbox checked={enabled} onChange={(event) => toggle(event.target.checked)} />
              </label>
              <Button type="button" variant="ghost" size="iconSm" onClick={() => setHelpOpen(true)} aria-label="Explain output contracts">
                <HelpCircle className="h-icon w-icon" />
              </Button>
            </div>
          )}
        />

        <div className="grid min-w-0 gap-ui-md p-ui-sm 2xl:p-ui-md">
          {enabled ? (
            <ContractFieldBuilder
              kind="output"
              rows={rows}
              onChange={(next) => setField('responseFormat', {
                ...state.responseFormat,
                enabled: true,
                type: 'json',
                strict: true,
                schema: outputSchemaFromRows(next),
              })}
            />
          ) : (
            <p className="font-sans text-product-small text-muted-foreground">
              Structured output is disabled. Enable it to define response fields without writing JSON Schema.
            </p>
          )}

          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
        </div>
      </section>
      <OutputContractHelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
