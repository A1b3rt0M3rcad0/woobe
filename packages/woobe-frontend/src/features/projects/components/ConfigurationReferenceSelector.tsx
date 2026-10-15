import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Input, Select } from '@woobe/ui'
import { listConfiguration } from '../configuration'
import { ConfigurationKeyDeclarationDialog } from './ConfigurationKeyDeclarationDialog'

export function ConfigurationReferenceSelector({ projectId, value, onChange, suggestedKey, disabled = false }: { projectId: string; value: string; onChange: (value: string) => void; suggestedKey?: string; disabled?: boolean }) {
  const [search, setSearch] = useState('')
  const [creating, setCreating] = useState(false)
  const client = useQueryClient()
  const query = useQuery({ queryKey: ['project-configuration', projectId, 'reference', search],
    queryFn: () => listConfiguration(projectId, 'draft', search), retry: false })
  const options = (query.data?.items ?? []).filter(item => item.kind === 'secret').map(item => ({ value: item.key,
    label: `${item.key} · ${item.material === 'present' ? 'Draft configured' : 'Value pending'}` }))
  if (value && !options.some(item => item.value === value)) options.unshift({ value, label: value })
  return <div className="grid gap-ui-sm sm:grid-cols-[1fr_2fr_auto]">
    <Input aria-label="Search configuration keys" value={search} disabled={disabled} onChange={event => setSearch(event.target.value)} placeholder="Search keys" />
    <Select aria-label="Project configuration key" value={value} onChange={event => onChange(event.target.value)}
      options={[{ value: '', label: query.isLoading ? 'Loading keys…' : 'Select a secret key' }, ...options]} disabled={disabled || query.isError} />
    {query.data?.permissions.declare && <Button type="button" variant="outline" disabled={disabled} onClick={() => setCreating(true)}>Declare key</Button>}
    {query.isError && <p role="alert" className="text-product-small text-muted-foreground sm:col-span-3">Configuration keys are unavailable or access is restricted.</p>}
    {query.data?.has_next && <p className="text-product-small text-muted-foreground sm:col-span-3">Search by name to find more keys.</p>}
    {creating && <ConfigurationKeyDeclarationDialog projectId={projectId} initialKey={suggestedKey} secretOnly onClose={() => setCreating(false)} onSaved={created => { onChange(created.key); void client.invalidateQueries({ queryKey: ['project-configuration', projectId] }) }} />}
  </div>
}
