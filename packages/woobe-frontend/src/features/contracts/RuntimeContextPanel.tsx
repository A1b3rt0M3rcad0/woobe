import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, Save } from 'lucide-react'
import { Button, Dialog } from '@woobe/ui'

import { ContractValueForm } from './ContractValueForm'
import { contractFields } from './contractFields'

interface RuntimeContextPanelProps {
  open?: boolean
  onClose?: () => void
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
  const fields = useMemo(() => contractFields(contract), [contract])
  const fieldNames = useMemo(() => new Set(Object.keys(fields)), [fields])
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [inlineOpen, setInlineOpen] = useState(true)
  const modalMode = open !== undefined && onClose !== undefined

  useEffect(() => {
    if (modalMode && !open) return
    setValues(Object.fromEntries(
      Object.entries(savedValues ?? {}).filter(([name]) => fieldNames.has(name)),
    ))
  }, [environment, fieldNames, modalMode, open, savedValues])

  const save = () => onSave(Object.fromEntries(
    Object.entries(values).filter(([name]) => fieldNames.has(name)),
  ))

  const form = (
    <>
      <ContractValueForm
        contract={contract}
        values={values}
        disabled={saving}
        onChange={setValues}
      />
      <div className="mt-ui-sm flex justify-end">
        <Button type="button" size="sm" variant="outline" loading={saving} onClick={() => void save()}>
          <Save className="h-icon-sm w-icon-sm" />
          Save values
        </Button>
      </div>
    </>
  )

  if (modalMode) {
    return (
      <Dialog
        open={Boolean(open)}
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

          {form}

          <div className="flex justify-end border-t border-border/70 pt-ui-md">
            <Button type="button" size="sm" variant="ghost" disabled={saving} onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </Dialog>
    )
  }

  if (!fieldNames.size) return null

  return (
    <div className="shrink-0 border-b border-border bg-surface/35">
      <button
        type="button"
        className="flex min-h-control w-full items-center gap-ui-xs px-ui-md text-left"
        onClick={() => setInlineOpen((current) => !current)}
      >
        {inlineOpen
          ? <ChevronDown className="h-icon-sm w-icon-sm text-muted-foreground" />
          : <ChevronRight className="h-icon-sm w-icon-sm text-muted-foreground" />}
        <span className="font-mono text-system-control font-medium text-accent-foreground">
          External Context
        </span>
        <span className="font-mono text-system-label uppercase text-muted-foreground">
          {environment}
        </span>
        <span className="ml-auto font-mono text-system-label text-muted-foreground">
          {fieldNames.size} field{fieldNames.size === 1 ? '' : 's'}
        </span>
      </button>
      {inlineOpen ? (
        <div className="border-t border-border/70 px-ui-md pb-ui-sm pt-ui-xs">
          {form}
        </div>
      ) : null}
    </div>
  )
}
