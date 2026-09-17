import { Braces } from 'lucide-react'
import { Alert, AlertDescription, PanelHeader } from '@woobe/ui'

import { JsonEditor } from '@/components/ui/JsonEditor'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { externalContextContractError } from '../editorValidation'

const DEFAULT_CONTRACT = `{
  "fields": {}
}`

const EXAMPLE_CONTRACT = `{
  "fields": {
    "customer_id": {
      "schema": { "type": "string" },
      "required": true,
      "scope": "session",
      "model": { "expose": false },
      "description": "Stable customer identifier supplied by the application"
    }
  }
}`

function contractText(value: unknown) {
  if (typeof value === 'string') return value
  return value && typeof value === 'object'
    ? JSON.stringify(value, null, 2)
    : DEFAULT_CONTRACT
}

export function AgentExternalContextSettings() {
  const { state, setField } = useAgentEditor()
  const error = externalContextContractError(state)

  return (
    <div className="min-w-0 max-w-full p-ui-md">
      <section className="min-w-0 max-w-full rounded-container border border-border bg-surface/[0.72]">
        <PanelHeader
          icon={<Braces className="h-icon w-icon" />}
          title="External Context"
          description="Declare trusted values the application may supply to this Agent at Run or Session scope."
        />

        <div className="grid min-w-0 gap-ui-md p-ui-md">
          <div className="min-w-0 max-w-full">
            <label className="mb-ui-sm block font-mono text-system-label font-medium uppercase tracking-system-label text-muted-foreground">
              Contract
            </label>
            <JsonEditor
              value={contractText(state.externalContextContract)}
              onChange={(value) => setField('externalContextContract', value)}
              editable
              actions={['format', 'validate', 'clear']}
              placeholder={EXAMPLE_CONTRACT}
            />
            {error ? (
              <Alert variant="destructive" className="mt-ui-sm">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
          </div>

          <div className="rounded-container border border-border bg-background/20 px-ui-md py-ui-sm font-sans text-product-caption text-muted-foreground">
            <p>
              The boundary is strict: undeclared request fields are rejected. Each field may use <code>run</code> or <code>session</code> scope, be required or optional, define a default, and explicitly opt into model visibility with <code>model.expose</code>.
            </p>
            <p className="mt-ui-xs">
              This contract has no independent version. It is frozen inside the Agent Release and compatibility is derived from Release-to-Release changes.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
