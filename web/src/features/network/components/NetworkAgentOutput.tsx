import { useEffect, useState } from 'react'
import { HelpCircle } from 'lucide-react'

import { JsonEditor } from '@/components/ui/JsonEditor'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { OutputContractHelpModal } from '@/features/playground/components/OutputContractHelpModal'

const DEFAULT_SCHEMA = `{
  "message": "string",
  "confidence": "float"
}`

export function isNetworkOutputValid(value: unknown) {
  if (value && typeof value === 'object') return true
  if (typeof value !== 'string' || !value.trim()) return false
  try { JSON.parse(value); return true } catch { return false }
}

function schemaText(value: unknown) {
  return typeof value === 'string' ? value : value && typeof value === 'object' ? JSON.stringify(value, null, 2) : DEFAULT_SCHEMA
}

export function NetworkAgentOutput({ onValidity }: { onValidity: (value: boolean) => void }) {
  const { state, setField } = useAgentEditor()
  const [helpOpen, setHelpOpen] = useState(false)
  const enabled = state.responseFormat.enabled

  useEffect(() => onValidity(!enabled || isNetworkOutputValid(state.responseFormat.schema)), [enabled, onValidity, state.responseFormat.schema])

  const toggle = (next: boolean) => setField('responseFormat', {
    ...state.responseFormat,
    enabled: next,
    type: next ? 'json' : 'text',
    strict: true,
    schema: next && !state.responseFormat.schema ? DEFAULT_SCHEMA : state.responseFormat.schema,
  })

  return (
    <div className="p-4">
      <section className="rounded-xl border border-border bg-surface p-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">JSON Output</p>
        <div className="mb-4 flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm font-medium text-muted"><input type="checkbox" checked={enabled} onChange={(event) => toggle(event.target.checked)} className="h-4 w-4 rounded border-border bg-background" />Enable JSON output</label>
          <button type="button" onClick={() => setHelpOpen(true)} className="flex h-7 w-7 items-center justify-center rounded-full border border-border text-muted hover:border-primary/40 hover:text-primary-light" aria-label="Explain output contracts"><HelpCircle className="h-3.5 w-3.5" /></button>
        </div>
        <label className="mb-1.5 block text-xs font-medium text-muted">Output contract</label>
        <JsonEditor value={schemaText(state.responseFormat.schema)} onChange={(value) => setField('responseFormat', { ...state.responseFormat, strict: true, schema: value })} onValidJsonChange={() => onValidity(true)} editable disabled={!enabled} actions={['format', 'validate', 'clear']} minHeight={180} maxHeight={360} placeholder='{ "message": "string" }' />
        <p className="mt-2 text-[11px] leading-5 text-muted">Write the response shape directly. Type names such as <code>"string"</code>, <code>"number"</code> and <code>"float"</code> describe expected values.</p>
      </section>
      <OutputContractHelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
