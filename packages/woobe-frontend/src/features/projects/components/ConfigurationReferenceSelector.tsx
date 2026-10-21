import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Input, Select } from '@woobe/ui'
import { listConfiguration } from '../configuration'
import { ConfigurationKeyDeclarationDialog } from './ConfigurationKeyDeclarationDialog'
import { ConfigurationUsageDialog } from './ConfigurationUsageDialog'
import type { ProjectEnvironment } from '../types'

export function ConfigurationReferenceSelector({ projectId, value, onChange, consumer, showHelp = true }: { projectId: string; value: string; onChange: (value: string) => void; consumer?: { kind: string; id: string }; showHelp?: boolean }) {
  const [search, setSearch] = useState('')
  const [creating, setCreating] = useState(false)
  const [accessOpen, setAccessOpen] = useState(false)
  const [accessEnvironment, setAccessEnvironment] = useState<ProjectEnvironment>('draft')
  const client = useQueryClient()
  const query = useQuery({ queryKey: ['project-configuration', projectId, 'reference', search],
    queryFn: () => listConfiguration(projectId, 'draft', search), retry: false })
  const options = (query.data?.items ?? []).filter(item => item.kind === 'secret').map(item => ({ value: item.key,
    label: `${item.key} · ${item.material === 'present' ? 'Draft value saved' : 'Value pending'}` }))
  if (value && !options.some(item => item.value === value)) options.unshift({ value, label: value })
  return <div className="grid gap-ui-sm sm:grid-cols-[1fr_2fr_auto]">
    <Input aria-label="Search configuration keys" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search keys" />
    <Select aria-label="Project configuration key" value={value} onChange={event => onChange(event.target.value)}
      options={[{ value: '', label: query.isLoading ? 'Loading keys…' : 'Select a secret key' }, ...options]} disabled={query.isError} />
    {query.data?.permissions.declare && <Button type="button" variant="outline" onClick={() => setCreating(true)}>Declare key</Button>}
    {query.isError && <p role="alert" className="text-product-small text-muted-foreground sm:col-span-3">Configuration keys are unavailable or access is restricted.</p>}
    {query.data?.has_next && <p className="text-product-small text-muted-foreground sm:col-span-3">Search by name to find more keys.</p>}
    {showHelp && <p className="text-product-small text-muted-foreground sm:col-span-3">Before use: save this connection, set the key value, then approve use in Environments → Manage approvals.</p>}
    {consumer && value && <Button type="button" variant="outline" className="justify-self-start sm:col-span-3" onClick={() => setAccessOpen(true)}>Manage approvals</Button>}
    {accessOpen && consumer && <ConfigurationUsageDialog projectId={projectId} keyName={value} environment={accessEnvironment} onEnvironmentChange={setAccessEnvironment} consumer={consumer} layer="nestedModal" onClose={() => setAccessOpen(false)} />}
    {creating && <ConfigurationKeyDeclarationDialog projectId={projectId} onClose={() => setCreating(false)} onSaved={() => { void client.invalidateQueries({ queryKey: ['project-configuration', projectId] }) }} />}
  </div>
}
