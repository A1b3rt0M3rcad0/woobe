import { useState } from 'react'
import { FileJson2, HelpCircle } from 'lucide-react'
import { PanelHeader } from '@woobe/ui'

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
    <div className="p-ui-md">
      <section className="rounded-container border border-border bg-surface/[0.72]">
        <PanelHeader
          icon={<FileJson2 className="h-3.5 w-3.5" />}
          title="JSON output"
          description="Define the structured response contract consumed by downstream code."
          actions={<button type="button" onClick={() => setHelpOpen(true)} className="flex h-control-segment w-control-segment items-center justify-center rounded-control border border-border text-muted-foreground transition-colors hover:border-primary/35 hover:bg-control hover:text-primary-light" aria-label="Explain output contracts"><HelpCircle className="h-3.5 w-3.5" /></button>}
        />

        <div className="space-y-ui-md p-ui-md">
          <label className="flex min-h-control items-center justify-between gap-ui-md rounded-container border border-border bg-background/20 px-ui-md py-ui-sm">
            <span><span className="block font-mono text-system-label font-semibold text-slate-100">Enable JSON output</span><span className="mt-ui-xs block font-sans text-product-caption text-muted-foreground">Strict validation remains enabled when the contract is active.</span></span>
            <input type="checkbox" checked={enabled} onChange={(event) => toggle(event.target.checked)} className="h-3.5 w-3.5 shrink-0 accent-primary" />
          </label>

          <div>
            <label className="mb-ui-sm block font-mono text-system-meta font-medium uppercase tracking-[0.1em] text-muted-foreground">Output contract</label>
            <JsonEditor value={schemaText(state.responseFormat.schema)} onChange={(value) => setField('responseFormat', { ...state.responseFormat, strict: true, schema: value })} editable disabled={!enabled} actions={['format', 'validate', 'clear']} placeholder='{ "message": "string" }' />
            {error ? <p role="alert" className="mt-ui-sm border-l-2 border-l-red-400 bg-red-500/[0.04] px-ui-sm py-ui-sm font-sans text-product-caption text-red-200">{error}</p> : null}
            <p className="mt-ui-sm font-sans text-product-caption text-muted-foreground">Type declarations such as <code>"string"</code>, <code>"number"</code> and <code>"float"</code> describe the expected values.</p>
          </div>
        </div>
      </section>
      <OutputContractHelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
