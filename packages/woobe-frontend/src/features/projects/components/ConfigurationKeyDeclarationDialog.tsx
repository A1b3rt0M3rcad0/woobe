import { useState } from 'react'
import { Button, Dialog, Field, FieldLabel, Input, Select } from '@woobe/ui'
import { declareConfiguration, updateConfiguration, type ConfigurationKey } from '../configuration'
import type { ProjectEnvironment } from '../types'

interface Props {
  projectId: string
  item?: ConfigurationKey
  environment?: ProjectEnvironment
  onClose: () => void
  onSaved: () => void
  onConfigure?: (item: ConfigurationKey, environment: ProjectEnvironment) => void
}

export function ConfigurationKeyDeclarationDialog({ projectId, item, environment = 'draft', onClose, onSaved, onConfigure }: Props) {
  const [key, setKey] = useState(item?.key ?? '')
  const [kind, setKind] = useState<'secret' | 'value'>(item?.kind ?? 'secret')
  const [format, setFormat] = useState<ConfigurationKey['value_format']>(item?.value_format ?? 'token')
  const [description, setDescription] = useState(item?.description ?? '')
  const [selectedEnvironment, setSelectedEnvironment] = useState(environment)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const save = async () => {
    setPending(true)
    setError('')
    try {
      const result = item
        ? await updateConfiguration(projectId, item, { description, value_format: format })
        : await declareConfiguration(projectId, { key, kind, value_format: format, description })
      onSaved()
      if (!item && onConfigure) onConfigure({ ...result, values: {}, material: 'missing', used_by_count: 0 }, selectedEnvironment)
      onClose()
    }
    catch { setError(item ? 'Changes were not saved. Refresh the key and check its format and your permissions.' : 'Key could not be declared. Check its name and your permissions, then refresh.') }
    finally { setPending(false) }
  }
  const close = () => { if (!pending) onClose() }
  return <Dialog open onClose={close} title={item ? <span className="block truncate" title={item.key}>Edit key · {item.key}</span> : 'Declare configuration key'} variant="workspace" className="max-w-2xl [scrollbar-gutter:auto]" scrollMode="content" contentClassName="[scrollbar-gutter:auto]"><div className="grid min-w-0 gap-ui-md p-ui-panel-inset sm:grid-cols-2">
    <Field className="min-w-0 sm:col-span-2"><FieldLabel htmlFor="configuration-key">Key</FieldLabel><Input id="configuration-key" className="min-w-0 font-mono" value={key} onChange={e => setKey(e.target.value)} placeholder="PRIMARY_PROVIDER_API_KEY" readOnly={!!item} disabled={pending} /></Field>
    <Field><FieldLabel htmlFor="configuration-kind">Kind</FieldLabel><Select id="configuration-kind" value={kind} disabled={!!item || pending} onChange={event => setKind(event.target.value as 'secret' | 'value')} options={[{ value: 'secret', label: 'Secret' }, { value: 'value', label: 'Value' }]} /></Field>
    <Field><FieldLabel htmlFor="configuration-format">Format</FieldLabel><Select id="configuration-format" value={format} disabled={pending} onChange={event => setFormat(event.target.value as ConfigurationKey['value_format'])} options={['string', 'token', 'json', 'pem', 'url'].map(value => ({ value, label: value.toUpperCase() }))} /></Field>
    <Field className="min-w-0 sm:col-span-2"><FieldLabel htmlFor="configuration-description">Description</FieldLabel><Input id="configuration-description" value={description} disabled={pending} onChange={e => setDescription(e.target.value)} maxLength={2048} /></Field>
    {!item && onConfigure && <Field className="min-w-0 sm:col-span-2"><FieldLabel htmlFor="configuration-create-environment">Environment for the value</FieldLabel><Select id="configuration-create-environment" value={selectedEnvironment} disabled={pending} onChange={event => setSelectedEnvironment(event.target.value as ProjectEnvironment)} options={['draft', 'staging', 'production'].map(value => ({ value, label: value[0].toUpperCase() + value.slice(1) }))} /></Field>}
    <p className="text-product-small text-muted-foreground sm:col-span-2">{item ? 'The key name and kind stay unchanged so existing references keep working. Format changes must be compatible with stored values.' : onConfigure ? 'The key is shared across environments. Next, set its value for the environment selected here. Cancelling that step leaves the key declared without a new value.' : 'Declare the key now. An authorized operator can configure values later.'}</p>
    {error && <p role="alert" className="sm:col-span-2">{error}</p>}
    <div className="flex flex-wrap justify-end gap-ui-sm sm:col-span-2"><Button variant="outline" disabled={pending} onClick={close}>Cancel</Button><Button disabled={pending || !/^[A-Za-z_][A-Za-z0-9_]{0,127}$/.test(key)} onClick={() => void save()}>{pending ? 'Saving…' : item ? 'Save changes' : onConfigure ? 'Create and set value' : 'Declare key'}</Button></div>
  </div></Dialog>
}

