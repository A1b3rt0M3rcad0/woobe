import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, Save } from 'lucide-react'
import { Button } from '@woobe/ui'

import { ContractValueForm } from './ContractValueForm'
import { contractFields } from './contractFields'

interface RuntimeContextPanelProps {
  environment: string
  contract: unknown
  savedValues?: Record<string, unknown>
  saving?: boolean
  onSave: (values: Record<string, unknown>) => void | Promise<void>
}

export function RuntimeContextPanel({ environment, contract, savedValues, saving = false, onSave }: RuntimeContextPanelProps) {
  const fields = contractFields(contract)
  const fieldNames = useMemo(() => new Set(Object.keys(fields)), [fields])
  const [open, setOpen] = useState(true)
  const [values, setValues] = useState<Record<string, unknown>>({})

  useEffect(() => {
    setValues(Object.fromEntries(
      Object.entries(savedValues ?? {}).filter(([name]) => fieldNames.has(name)),
    ))
  }, [environment, fieldNames, savedValues])

  if (!fieldNames.size) return null

  const save = () => onSave(Object.fromEntries(
    Object.entries(values).filter(([name]) => fieldNames.has(name)),
  ))

  return (
    <div className="shrink-0 border-b border-border bg-surface/35">
      <button
        type="button"
        className="flex min-h-control w-full items-center gap-ui-xs px-ui-md text-left"
        onClick={() => setOpen((current) => !current)}
      >
        {open ? <ChevronDown className="h-icon-sm w-icon-sm text-muted-foreground" /> : <ChevronRight className="h-icon-sm w-icon-sm text-muted-foreground" />}
        <span className="font-mono text-system-control font-medium text-accent-foreground">External Context</span>
        <span className="font-mono text-system-label uppercase text-muted-foreground">{environment}</span>
        <span className="ml-auto font-mono text-system-label text-muted-foreground">{fieldNames.size} field{fieldNames.size === 1 ? '' : 's'}</span>
      </button>
      {open ? (
        <div className="border-t border-border/70 px-ui-md pb-ui-sm pt-ui-xs">
          <ContractValueForm contract={contract} values={values} disabled={saving} onChange={setValues} />
          <div className="mt-ui-sm flex justify-end">
            <Button type="button" size="sm" variant="outline" loading={saving} onClick={() => void save()}>
              <Save className="h-icon-sm w-icon-sm" />
              Save values
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
