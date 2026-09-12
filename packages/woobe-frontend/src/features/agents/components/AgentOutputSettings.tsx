import { useState } from 'react'
import { FileJson2, HelpCircle } from 'lucide-react'

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
    <div className="p-3">
      <section className="rounded-container border border-border bg-surface/[0.72]">
        <div className="flex items-start justify-between gap-3 border-b border-border p-3">
          <div className="flex min-w-0 items-start gap-2.5">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light"><FileJson2 className="h-3.5 w-3.5" /></span>
            <div className="min-w-0"><p className="font-mono text-[9px] font-bold text-slate-50">JSON output</p><p className="mt-0.5 font-sans text-[9px] leading-4 text-muted-foreground">Define the structured response contract consumed by downstream code.</p></div>
          </div>
          <button type="button" onClick={() => setHelpOpen(true)} className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border text-muted-foreground transition-colors hover:border-primary/35 hover:bg-control hover:text-primary-light" aria-label="Explain output contracts"><HelpCircle className="h-3.5 w-3.5" /></button>
        </div>

        <div className="space-y-3 p-3">
          <label className="flex min-h-[34px] items-center justify-between gap-3 rounded-container border border-border bg-background/20 px-3 py-2">
            <span><span className="block font-mono text-[9px] font-semibold text-slate-100">Enable JSON output</span><span className="mt-0.5 block font-sans text-[8px] text-muted-foreground">Strict validation remains enabled when the contract is active.</span></span>
            <input type="checkbox" checked={enabled} onChange={(event) => toggle(event.target.checked)} className="h-3.5 w-3.5 shrink-0 accent-primary" />
          </label>

          <div>
            <label className="mb-1.5 block font-mono text-[8px] font-medium uppercase tracking-[0.1em] text-muted-foreground">Output contract</label>
            <JsonEditor value={schemaText(state.responseFormat.schema)} onChange={(value) => setField('responseFormat', { ...state.responseFormat, strict: true, schema: value })} editable disabled={!enabled} actions={['format', 'validate', 'clear']} minHeight={180} maxHeight={360} placeholder='{ "message": "string" }' />
            {error ? <p role="alert" className="mt-2 border-l-2 border-l-red-400 bg-red-500/[0.04] px-2.5 py-2 font-sans text-[9px] leading-4 text-red-200">{error}</p> : null}
            <p className="mt-2 font-sans text-[9px] leading-4 text-muted-foreground">Type declarations such as <code>"string"</code>, <code>"number"</code> and <code>"float"</code> describe the expected values.</p>
          </div>
        </div>
      </section>
      <OutputContractHelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
