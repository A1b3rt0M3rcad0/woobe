import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button, Dialog, DangerConfirmDialog, Field, FieldLabel, Input, Select } from '@woobe/ui'
import type { ProjectEnvironment } from '../types'
import { clearConfiguration, configurationKeyMetadata, writeConfiguration, type ConfigurationKey } from '../configuration'

interface Props {
  projectId: string
  item: ConfigurationKey
  environment: ProjectEnvironment
  onClose: () => void
  onSaved: (environment: ProjectEnvironment) => void
}

export function ConfigurationValueEditor({ projectId, item, environment, onClose, onSaved }: Props) {
  const [selectedEnvironment, setSelectedEnvironment] = useState(environment)
  const [nextEnvironment, setNextEnvironment] = useState<ProjectEnvironment | null>(null)
  const [value, setValue] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [confirmDiscard, setConfirmDiscard] = useState(false)
  const [confirmClear, setConfirmClear] = useState(false)
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const metadata = useQuery({
    queryKey: ['configuration-key-editor', projectId, item.id, selectedEnvironment],
    queryFn: () => configurationKeyMetadata(projectId, item, selectedEnvironment),
    staleTime: 0, refetchOnMount: 'always', retry: false,
  })
  const currentItem = metadata.data?.item ?? item
  const configured = currentItem.values[selectedEnvironment]?.configured ?? false
  const canWrite = metadata.isSuccess && !metadata.isFetching && !!metadata.data.permissions['value:write']
  const canClear = metadata.isSuccess && !metadata.isFetching && !!metadata.data.permissions['value:clear']
  const switchEnvironment = (target: ProjectEnvironment) => {
    setValue(''); setError(''); setConfirmClear(false); setNextEnvironment(null); setSelectedEnvironment(target)
  }
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (value) { event.preventDefault(); event.returnValue = '' } }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [value])
  const discard = () => { setValue(''); setConfirmDiscard(false); onClose() }
  const close = () => { if (pending) return; if (value) setConfirmDiscard(true); else discard() }
  const save = async (clear = false) => {
    if (pending || !(clear ? canClear : canWrite)) return
    setPending(true)
    setError('')
    try {
      if (clear) await clearConfiguration(projectId, currentItem, selectedEnvironment)
      else await writeConfiguration(projectId, currentItem, selectedEnvironment, value)
      if (!mounted.current) return
      setValue('')
      onSaved(selectedEnvironment)
      onClose()
    } catch {
      if (!mounted.current) return
      setValue('')
      setError('The value was not saved. Refresh configuration before retrying; another operator may have changed it.')
      await metadata.refetch()
    } finally { if (mounted.current) { setPending(false); setConfirmClear(false) } }
  }
  return <Dialog open onClose={close} title={`${configured ? 'Replace' : 'Set'} value · ${selectedEnvironment}`}>
    <div className="grid gap-ui-md p-ui-lg md:grid-cols-[1fr_2fr]">
      <Field className="md:col-span-2"><FieldLabel htmlFor="configuration-value-environment">Environment</FieldLabel>
        <Select id="configuration-value-environment" value={selectedEnvironment} disabled={pending || nextEnvironment !== null} onChange={event => {
          const target = event.target.value as ProjectEnvironment
          if (target === selectedEnvironment) return
          if (value) setNextEnvironment(target)
          else switchEnvironment(target)
        }} options={['draft', 'staging', 'production'].map(option => ({ value: option, label: option[0].toUpperCase() + option.slice(1) }))} />
      </Field>
      <div><h3 className="break-all font-mono text-product-label">{item.key}</h3>
        <p className="mt-ui-sm text-product-small text-muted-foreground">{item.description || 'Project configuration'}</p>
        <p className="mt-ui-sm text-product-small text-muted-foreground">{configured ? 'A value is configured. The editor starts empty.' : 'No value configured in this environment.'}</p>
      </div>
      <Field><FieldLabel htmlFor="configuration-value">New {item.kind} value</FieldLabel>
        {item.value_format === 'pem' || item.value_format === 'json'
          ? <textarea id="configuration-value" className="min-h-36 w-full rounded-control border border-border bg-background p-ui-sm font-mono text-product-small" value={value} onChange={e => setValue(e.target.value)} autoComplete="off" spellCheck={false} data-private="true" disabled={!canWrite || pending} />
          : <Input id="configuration-value" type={item.kind === 'secret' ? 'password' : 'text'} value={value} onChange={e => setValue(e.target.value)} autoComplete="new-password" spellCheck={false} data-private="true" disabled={!canWrite || pending} />}
        <p className="text-product-small text-muted-foreground">Saving configures {selectedEnvironment}; it does not run or deploy anything.</p>
      </Field>
      {metadata.isFetching && <p role="status" className="md:col-span-2">Loading this environment’s configuration and permissions…</p>}
      {metadata.isError && <div role="alert" className="md:col-span-2"><p>This environment’s configuration is unavailable. Choose another environment or retry.</p><Button variant="outline" onClick={() => void metadata.refetch()}>Retry</Button></div>}
      {metadata.isSuccess && !canWrite && !canClear && <p role="status" className="md:col-span-2">You do not have permission to change values in this environment.</p>}
      {error && <p role="alert" className="text-destructive md:col-span-2">{error}</p>}
      <div className="flex flex-wrap justify-end gap-ui-sm border-t border-border pt-ui-md md:col-span-2">
        {configured && canClear && <Button variant="outline" disabled={pending} onClick={() => setConfirmClear(true)}>Clear value</Button>}
        <Button variant="outline" disabled={pending} onClick={close}>Cancel</Button>
        {canWrite && <Button disabled={pending || !value} onClick={() => void save()}>{pending ? 'Saving…' : configured ? 'Replace value' : 'Save value'}</Button>}
      </div>
    </div>
    {confirmClear && <Dialog open layer="nestedModal" title={`Clear ${item.key} in ${selectedEnvironment}?`} onClose={() => setConfirmClear(false)}>
      <div className="space-y-ui-md p-ui-lg"><p>Consumers will be blocked until a new value is configured. In-flight use of the revoked value will also stop.</p>
        <div className="flex justify-end gap-ui-sm"><Button variant="outline" onClick={() => setConfirmClear(false)}>Cancel</Button><Button disabled={pending} onClick={() => void save(true)}>Clear value</Button></div>
      </div>
    </Dialog>}
    <DangerConfirmDialog open={confirmDiscard} layer="nestedModal" title="Discard unsaved value?" description="The entered value will be removed from this editor. Saved configuration stays unchanged." confirmLabel="Discard value" onClose={() => setConfirmDiscard(false)} onConfirm={discard} />
    <DangerConfirmDialog open={nextEnvironment !== null} layer="nestedModal" title="Switch environment?" description="The unsaved value will be discarded. Enter a new value for the environment you select." confirmLabel="Switch environment" onClose={() => setNextEnvironment(null)} onConfirm={() => { if (nextEnvironment) switchEnvironment(nextEnvironment) }} />
  </Dialog>
}
