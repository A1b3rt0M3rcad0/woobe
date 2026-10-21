import { Button, Field, FieldLabel, Input, Select } from '@woobe/ui'
import { useId } from 'react'
import { ConfigurationReferenceSelector } from '@/features/projects/components/ConfigurationReferenceSelector'
import type { RemoteAuthentication } from '../types'

export function ConfigurationAuthenticationEditor({ projectId, value, onChange, toolId }: {
  projectId: string; value: RemoteAuthentication; onChange: (value: RemoteAuthentication) => void; toolId?: string
}) {
  const instance = useId()
  const typeId = `${instance}-authentication-type`
  const headerId = `${instance}-new-header`
  const changeType = (type: RemoteAuthentication['type']) => {
    const names = type === 'api_key' ? ['api_key'] : type === 'bearer' ? ['token'] : type === 'basic' ? ['username', 'password'] : []
    onChange({ type, fields: Object.fromEntries(names.map(name => [name, { source: 'project_environment' as const, key: '' }])) })
  }
  return <section className="space-y-ui-md rounded-technical border border-border bg-card p-ui-md" aria-label="Connection authentication">
    <div className="grid gap-ui-md md:grid-cols-[1fr_2fr]">
      <Field><FieldLabel htmlFor={typeId}>Authentication</FieldLabel><Select id={typeId} value={value.type} onChange={event => changeType(event.target.value as RemoteAuthentication['type'])} options={[
        { value: 'none', label: 'None (public connection)' }, { value: 'api_key', label: 'API key (X-Api-Key)' },
        { value: 'bearer', label: 'Bearer token' }, { value: 'basic', label: 'Basic authentication' }, { value: 'headers', label: 'Named headers' },
      ]} /></Field>
      <p className="text-product-small text-muted-foreground">{value.type === 'none' ? 'This public connection uses no project keys.' : 'Before testing or running: save this tool, set key values, then approve use in Environments → Manage approvals.'}</p>
    </div>
    {Object.entries(value.fields).map(([field, reference]) => <div key={field} className="grid items-center gap-ui-sm md:grid-cols-[10rem_1fr_auto]">
      <span className="font-mono text-product-small">{field}</span>
      <ConfigurationReferenceSelector projectId={projectId} showHelp={false} consumer={toolId ? { kind: 'tool', id: toolId } : undefined} value={reference.key} onChange={key => onChange({ ...value, fields: { ...value.fields, [field]: { source: 'project_environment', key } } })} />
      {value.type === 'headers' && <Button type="button" variant="ghost" onClick={() => onChange({ ...value, fields: Object.fromEntries(Object.entries(value.fields).filter(([name]) => name !== field)) })}>Remove</Button>}
    </div>)}
    {value.type === 'headers' && <Field><FieldLabel htmlFor={headerId}>Add header name</FieldLabel><Input id={headerId} placeholder="X-Client-Token" onKeyDown={event => {
      if (event.key !== 'Enter') return
      event.preventDefault()
      const field = event.currentTarget.value.trim()
      if (!/^[A-Za-z][A-Za-z0-9_-]{0,127}$/.test(field) || Object.keys(value.fields).length >= 16) return
      onChange({ ...value, fields: { ...value.fields, [field]: { source: 'project_environment', key: '' } } })
      event.currentTarget.value = ''
    }} /><p className="text-product-small text-muted-foreground">Press Enter to add the name, then select its key.</p></Field>}
  </section>
}
