import { useEffect, useState } from 'react'
import { Button, Dialog, DangerConfirmDialog, Field, FieldLabel, Input } from '@woobe/ui'
import type { ProjectEnvironment } from '../types'
import { clearConfiguration, writeConfiguration, type ConfigurationKey } from '../configuration'

interface Props {
  projectId: string
  item: ConfigurationKey
  environment: ProjectEnvironment
  canWrite: boolean
  canClear: boolean
  onClose: () => void
  onSaved: () => void
}

export function ConfigurationValueEditor({ projectId, item, environment, canWrite, canClear, onClose, onSaved }: Props) {
  const [value, setValue] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [confirmDiscard, setConfirmDiscard] = useState(false)
  const [confirmClear, setConfirmClear] = useState(false)
  const configured = item.values[environment]?.configured ?? false
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (value) { event.preventDefault(); event.returnValue = '' } }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [value])
  const discard = () => { setValue(''); setConfirmDiscard(false); onClose() }
  const close = () => { if (pending) return; if (value) setConfirmDiscard(true); else discard() }
  const save = async (clear = false) => {
    setPending(true)
    setError('')
    try {
      if (clear) await clearConfiguration(projectId, item, environment)
      else await writeConfiguration(projectId, item, environment, value)
      setValue('')
      onSaved()
      onClose()
    } catch {
      setValue('')
      setError('The value was not saved. Refresh configuration before retrying; another operator may have changed it.')
    } finally { setPending(false) }
  }
  return <Dialog open onClose={close} title={`${configured ? 'Replace' : 'Set'} value · ${environment}`}>
    <div className="grid gap-ui-md p-ui-lg md:grid-cols-[1fr_2fr]">
      <div><h3 className="break-all font-mono text-product-label">{item.key}</h3>
        <p className="mt-ui-sm text-product-small text-muted-foreground">{item.description || 'Project configuration'}</p>
        <p className="mt-ui-sm text-product-small text-muted-foreground">{configured ? 'A value is configured. The editor starts empty.' : 'No value configured in this environment.'}</p>
      </div>
      <Field><FieldLabel htmlFor="configuration-value">New {item.kind} value</FieldLabel>
        {item.value_format === 'pem' || item.value_format === 'json'
          ? <textarea id="configuration-value" className="min-h-36 w-full rounded-control border border-border bg-background p-ui-sm font-mono text-product-small" value={value} onChange={e => setValue(e.target.value)} autoComplete="off" spellCheck={false} data-private="true" disabled={!canWrite || pending} />
          : <Input id="configuration-value" type={item.kind === 'secret' ? 'password' : 'text'} value={value} onChange={e => setValue(e.target.value)} autoComplete="new-password" spellCheck={false} data-private="true" disabled={!canWrite || pending} />}
        <p className="text-product-small text-muted-foreground">Saving configures {environment}; it does not run or deploy anything.</p>
      </Field>
      {error && <p role="alert" className="text-destructive md:col-span-2">{error}</p>}
      <div className="flex flex-wrap justify-end gap-ui-sm border-t border-border pt-ui-md md:col-span-2">
        {configured && canClear && <Button variant="outline" disabled={pending} onClick={() => setConfirmClear(true)}>Clear value</Button>}
        <Button variant="outline" disabled={pending} onClick={close}>Cancel</Button>
        {canWrite && <Button disabled={pending || !value} onClick={() => void save()}>{pending ? 'Saving…' : configured ? 'Replace value' : 'Save value'}</Button>}
      </div>
    </div>
    {confirmClear && <Dialog open layer="nestedModal" title={`Clear ${item.key} in ${environment}?`} onClose={() => setConfirmClear(false)}>
      <div className="space-y-ui-md p-ui-lg"><p>Consumers will be blocked until a new value is configured. In-flight use of the revoked value will also stop.</p>
        <div className="flex justify-end gap-ui-sm"><Button variant="outline" onClick={() => setConfirmClear(false)}>Cancel</Button><Button disabled={pending} onClick={() => void save(true)}>Clear value</Button></div>
      </div>
    </Dialog>}
    <DangerConfirmDialog open={confirmDiscard} layer="nestedModal" title="Discard unsaved value?" description="The entered value will be removed from this editor. Saved configuration stays unchanged." confirmLabel="Discard value" onClose={() => setConfirmDiscard(false)} onConfirm={discard} />
  </Dialog>
}
