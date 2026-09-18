import { useEffect, useMemo, useState } from 'react'
import { Save } from 'lucide-react'
import { Button, Dialog } from '@woobe/ui'

import { ContractValueForm } from './ContractValueForm'
import { contractFields } from './contractFields'

interface RuntimeContextPanelProps {
  open: boolean
  onClose: () => void
  environment: string
  contract: unknown
  savedValues?: Record<string, unknown>
  saving?: boolean
  onSave: (values: Record<string, unknown>) => void | Promise<void>
}

export function RuntimeContextPanel({
  open,
  onClose,
  environment,
  contract,
  savedValues,
  saving = false,
  onSave,
}: RuntimeContextPanelProps) {
  const fields = contractFields(contract)
  const fieldNames = useMemo(() => new Set(Object.keys(fields)), [fields])
  const [values, setValues] = useState<Record<string, unknown>>({})

  useEffect(() => {
    if (!open) return
    setValues(Object.fromEntries(
      Object.entries(savedValues ?? {}).filter(([name]) => fieldNames.has(name)),
    ))
  }, [environment, fieldNames, open, savedValues])

  const save = () => onSave(Object.fromEntries(
    Object.entries(values).filter(([name]) => fieldNames.has(name)),
  ))

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="External Context"
      className="max-w-2xl"
      scrollMode="content"
    >
      <div className="grid gap-ui-md">
        <div className="rounded-container border border-border bg-background/35 px-ui-md py-ui-sm">
          <div className="flex items-center justify-between gap-ui-md">
            <div>
              <p className="font-mono text-system-control font-semibold text-accent-foreground">
                Runtime values
              </p>
              <p className="mt-ui-hairline font-sans text-product-caption text-muted-foreground">
                Values are validated against the selected Agent contract before the Run is accepted.
              </p>
            </div>
            <span className="shrink-0 font-mono text-system-label uppercase text-muted-foreground">
              {environment}
            </span>
          </div>
        </div>

        <ContractValueForm
          contract={contract}
          values={values}
          disabled={saving}
          onChange={setValues}
        />

        <div className="flex justify-end gap-ui-sm border-t border-border/70 pt-ui-md">
          <Button type="button" size="sm" variant="ghost" disabled={saving} onClick={onClose}>
            Close
          </Button>
          <Button type="button" size="sm" variant="outline" loading={saving} onClick={() => void save()}>
            <Save className="h-icon-sm w-icon-sm" />
            Save values
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
