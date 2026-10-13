import { useEffect, useState } from 'react'
import { Button, Dialog, Field, FieldLabel, Input } from '@woobe/ui'
import { writeConfigurationBatch, type ConfigurationKey } from '../configuration'
import type { ProjectEnvironment } from '../types'

export function ConfigurationBatchEditor({ projectId, environment, keys, onClose, onSaved }: {
  projectId: string; environment: ProjectEnvironment; keys: ConfigurationKey[]; onClose: () => void; onSaved: () => void
}) {
  const [values, setValues] = useState<Record<string, string>>({})
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const dirty = Object.values(values).some(Boolean)
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = '' } }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  const close = () => { if (pending || (dirty && !window.confirm('Discard the unsaved values?'))) return; setValues({}); onClose() }
  const save = async () => {
    setPending(true); setError('')
    try {
      await writeConfigurationBatch(projectId, environment, keys, values, crypto.randomUUID())
      setValues({}); onSaved(); onClose()
    } catch {
      setValues({})
      setError('The batch was not confirmed. Reload the metadata before retrying; values were removed from this editor.')
    } finally { setPending(false) }
  }
  return <Dialog open onClose={close} title={`Configure pending values · ${environment}`}>
    <div className="space-y-ui-md p-ui-lg">
      <p className="text-product-small text-muted-foreground">Fill only the keys you need. The server saves the submitted values together, or rejects the whole batch. Nothing is executed automatically.</p>
      <div className="grid max-h-[60vh] gap-ui-md overflow-y-auto md:grid-cols-2">
        {keys.map(key => <Field key={key.id} className="rounded-technical border border-border p-ui-md">
          <FieldLabel htmlFor={`batch-${key.id}`}>{key.key}</FieldLabel>
          <p className="text-product-small text-muted-foreground">{key.description || key.value_format}</p>
          {key.value_format === 'json' || key.value_format === 'pem'
            ? <textarea id={`batch-${key.id}`} className="min-h-24 w-full rounded-control border border-border bg-background p-ui-sm font-mono" value={values[key.id] ?? ''} onChange={event => setValues(current => ({ ...current, [key.id]: event.target.value }))} autoComplete="off" spellCheck={false} data-private="true" disabled={pending} />
            : <Input id={`batch-${key.id}`} type={key.kind === 'secret' ? 'password' : 'text'} value={values[key.id] ?? ''} onChange={event => setValues(current => ({ ...current, [key.id]: event.target.value }))} autoComplete="new-password" spellCheck={false} data-private="true" disabled={pending} />}
        </Field>)}
      </div>
      {error && <p role="alert">{error}</p>}
      <div className="flex justify-end gap-ui-sm border-t border-border pt-ui-md"><Button variant="outline" onClick={close} disabled={pending}>Cancel</Button><Button disabled={!dirty || pending} onClick={() => void save()}>{pending ? 'Saving…' : 'Save entered values'}</Button></div>
    </div>
  </Dialog>
}
