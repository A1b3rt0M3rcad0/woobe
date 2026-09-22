import { Braces } from 'lucide-react'
import { Alert, AlertDescription, Checkbox, PanelHeader } from '@woobe/ui'

import { ContractFieldBuilder } from '@/features/contracts/ContractFieldBuilder'
import { externalContractFromRows, externalContractRows } from '@/features/contracts/contractFields'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { externalContextContractError } from '../editorValidation'

export function AgentExternalContextSettings() {
  const { state, setField } = useAgentEditor()
  const enabled = state.externalContextContract !== null
  const rows = externalContractRows(state.externalContextContract)
  const error = externalContextContractError(state)

  const toggle = (next: boolean) => {
    setField('externalContextContract', next ? externalContractFromRows(rows) : null)
  }

  return (
    <div className="min-w-0 max-w-full p-ui-sm 2xl:p-ui-md">
      <section className="min-w-0 max-w-full rounded-container border border-border bg-surface/[0.72]">
        <PanelHeader
          icon={<Braces className="h-icon w-icon" />}
          title="External Context"
          description="Declare the typed values applications may supply to this Agent."
          actions={(
            <label className="flex items-center gap-ui-sm font-mono text-system-label text-muted-foreground">
              {enabled ? 'Enabled' : 'Disabled'}
              <Checkbox checked={enabled} onChange={(event) => toggle(event.target.checked)} />
            </label>
          )}
        />

        <div className="grid min-w-0 gap-ui-md p-ui-sm 2xl:p-ui-md">
          {enabled ? (
            <ContractFieldBuilder
              kind="external"
              rows={rows}
              onChange={(next) => setField('externalContextContract', externalContractFromRows(next))}
            />
          ) : (
            <p className="font-sans text-product-small text-muted-foreground">
              This Agent does not declare an External Context contract. Enable it to add fields that applications may supply to each Run.
            </p>
          )}

          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          {enabled ? (
            <p className="font-sans text-product-caption text-muted-foreground">
              The request boundary is strict. Field type, requirement and model visibility are compiled into the Release contract automatically.
            </p>
          ) : null}
        </div>
      </section>
    </div>
  )
}
