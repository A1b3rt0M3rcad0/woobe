import { useState } from 'react'
import { Button, Dialog, Field, FieldLabel, Input, Select } from '@woobe/ui'
import { declareConfiguration, type ConfigurationKey } from '../configuration'

export function ConfigurationKeyDeclarationDialog({ projectId, onClose, onSaved, initialKey = '', secretOnly = false }: { projectId: string; onClose: () => void; onSaved: (key: ConfigurationKey) => void; initialKey?: string; secretOnly?: boolean }) {
  const [key, setKey] = useState(initialKey)
  const [kind, setKind] = useState<'secret' | 'value'>('secret')
  const [format, setFormat] = useState<ConfigurationKey['value_format']>('token')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const save = async () => {
    setPending(true)
    try { const created = await declareConfiguration(projectId, { key, kind, value_format: format, description }); onSaved(created); onClose() }
    catch { setError('Key could not be declared. Check its name and your permissions, then refresh.') }
    finally { setPending(false) }
  }
  return <Dialog open onClose={onClose} title="Declare configuration key"><div className="grid gap-ui-md p-ui-lg md:grid-cols-2">
    <Field><FieldLabel htmlFor="configuration-key">Key</FieldLabel><Input id="configuration-key" value={key} onChange={e => setKey(e.target.value)} placeholder="PRIMARY_PROVIDER_API_KEY" /></Field>
    <Field><FieldLabel htmlFor="configuration-kind">Kind</FieldLabel><Select id="configuration-kind" value={kind} disabled={secretOnly} onChange={event => setKind(event.target.value as 'secret' | 'value')} options={[{ value: 'secret', label: 'Secret' }, { value: 'value', label: 'Value' }]} /></Field>
    <Field><FieldLabel htmlFor="configuration-format">Format</FieldLabel><Select id="configuration-format" value={format} onChange={event => setFormat(event.target.value as ConfigurationKey['value_format'])} options={['string', 'token', 'json', 'pem', 'url'].map(value => ({ value, label: value.toUpperCase() }))} /></Field>
    <Field><FieldLabel htmlFor="configuration-description">Description</FieldLabel><Input id="configuration-description" value={description} onChange={e => setDescription(e.target.value)} maxLength={2048} /></Field>
    <p className="text-product-small text-muted-foreground md:col-span-2">Declare the key now. An authorized operator can configure values later.</p>
    {error && <p role="alert" className="md:col-span-2">{error}</p>}
    <div className="flex justify-end gap-ui-sm md:col-span-2"><Button variant="outline" onClick={onClose}>Cancel</Button><Button disabled={pending || !/^[A-Za-z_][A-Za-z0-9_]{0,127}$/.test(key)} onClick={() => void save()}>Declare key</Button></div>
  </div></Dialog>
}

