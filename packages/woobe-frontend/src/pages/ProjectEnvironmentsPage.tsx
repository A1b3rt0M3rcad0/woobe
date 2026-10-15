import { ConfigurationBatchEditor } from '@/features/projects/components/ConfigurationBatchEditor'
import { ConfigurationEnvironmentComparison } from '@/features/projects/components/ConfigurationEnvironmentComparison'
import { ConfigurationLegacyPanel } from '@/features/projects/components/ConfigurationLegacyPanel'
import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Field, FieldLabel, Input, Select } from '@woobe/ui'
import { ResourcePage } from '@/components/common/ResourcePage'
import { ApiError } from '@/lib/api/errors'
import { configurationReturnPath, listConfiguration, type ConfigurationKey } from '@/features/projects/configuration'
import { ConfigurationKeyDeclarationDialog } from '@/features/projects/components/ConfigurationKeyDeclarationDialog'
import { ConfigurationKeyDeletionDialog } from '@/features/projects/components/ConfigurationKeyDeletionDialog'
import { ConfigurationUsageDialog } from '@/features/projects/components/ConfigurationUsageDialog'
import { ConfigurationValueEditor } from '@/features/projects/components/ConfigurationValueEditor'
import type { ProjectEnvironment } from '@/features/projects/types'

export default function ProjectEnvironmentsPage() {
  const { projectId } = useParams()
  return projectId ? <EnvironmentWorkspace key={projectId} projectId={projectId} /> : null
}

function EnvironmentWorkspace({ projectId }: { projectId: string }) {
  const [params, setParams] = useSearchParams()
  const returnTo = configurationReturnPath(params.get('returnTo'), projectId, window.location.origin)
  const selected = params.get('environment')
  const environment: ProjectEnvironment = selected === 'staging' || selected === 'production' ? selected : 'draft'
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const [offset, setOffset] = useState(0)
  const [editing, setEditing] = useState<{ item: ConfigurationKey; environment: ProjectEnvironment } | null>(null)
  const [editingDefinition, setEditingDefinition] = useState<ConfigurationKey | null>(null)
  const [deleting, setDeleting] = useState<ConfigurationKey | null>(null)
  const [usage, setUsage] = useState<ConfigurationKey | null>(null)
  const [creating, setCreating] = useState(false)
  const [batch, setBatch] = useState<ConfigurationKey[] | null>(null)
  const [view, setView] = useState<'keys' | 'compare' | 'legacy'>('keys')
  useEffect(() => { setEditing(null); setEditingDefinition(null); setDeleting(null); setBatch(null); setUsage(null); setCreating(false) }, [projectId, environment])
  const client = useQueryClient()
  const query = useQuery({ queryKey: ['project-configuration', projectId, environment, search, status, offset],
    queryFn: () => listConfiguration(projectId, environment, search, status, offset), retry: false })
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ['project-configuration', projectId] })
    void client.invalidateQueries({ queryKey: ['configuration-readiness', projectId] })
    void client.invalidateQueries({ queryKey: ['configuration-summary', projectId] })
    void client.invalidateQueries({ queryKey: ['configuration-key-editor', projectId] })
    void client.invalidateQueries({ queryKey: ['configuration-deletion', projectId] })
  }
  const permissions = query.data?.permissions ?? {}
  const selectEnvironment = (value: ProjectEnvironment) => { setOffset(0); setEditing(null); setParams({ environment: value, ...(returnTo ? { returnTo } : {}) }) }
  return <ResourcePage title="Environments" description="Declare shared configuration, then set values for each environment.">
    {returnTo && <a href={returnTo} className="text-product-small text-primary underline underline-offset-2">Return to execution · no automatic Run</a>}
    <div className="flex flex-wrap items-end justify-between gap-ui-md rounded-technical border border-border bg-card p-ui-md">
      <div className="flex flex-wrap items-end gap-ui-sm">
        <Field><FieldLabel htmlFor="configuration-environment">Environment</FieldLabel><Select id="configuration-environment" value={environment} onChange={event => selectEnvironment(event.target.value as ProjectEnvironment)} options={['draft', 'staging', 'production'].map(value => ({ value, label: value[0].toUpperCase() + value.slice(1) }))} /></Field>
        <Field><FieldLabel htmlFor="configuration-search">Search keys</FieldLabel><Input id="configuration-search" value={search} onChange={e => { setSearch(e.target.value); setOffset(0) }} placeholder="Name or description" /></Field>
        <Field><FieldLabel htmlFor="configuration-status">Status</FieldLabel><Select id="configuration-status" value={status} onChange={event => { setStatus(event.target.value); setOffset(0) }} options={['all', 'configured', 'missing', 'attention', 'legacy'].map(value => ({ value, label: value[0].toUpperCase() + value.slice(1) }))} /></Field>
      </div>
      {permissions.declare && <Button onClick={() => setCreating(true)}>Add key</Button>}
    </div>
    <div className="flex flex-wrap gap-ui-sm" aria-label="Configuration views">{(['keys', 'compare', 'legacy'] as const).map(item => <Button key={item} variant={view === item ? 'default' : 'outline'} onClick={() => { setView(item); setOffset(0); setStatus('all') }}>{item === 'keys' ? 'Keys' : item === 'compare' ? 'Compare environments' : 'Legacy mappings'}</Button>)}</div>
    {view === 'compare' ? <ConfigurationEnvironmentComparison projectId={projectId} search={search} /> : view === 'legacy' ? <ConfigurationLegacyPanel key={`${projectId}:${environment}`} projectId={projectId} environment={environment} canConvert={!!permissions.migrate && !!permissions['value:write']} onSaved={refresh} /> : query.isLoading ? <p role="status">Loading configuration…</p> : query.isError ? <div role="alert" className="rounded-technical border border-border p-ui-lg">
      <p>{query.error instanceof ApiError && query.error.status === 403 ? 'You do not have access to this environment’s configuration.' : 'Configuration is unavailable. Readiness cannot be confirmed.'}</p>
      <Button variant="outline" onClick={() => void query.refetch()}>Retry</Button>
    </div> : <>
      <div className="flex flex-wrap items-center justify-between gap-ui-sm"><p className="text-product-small text-muted-foreground">{query.data?.total ?? 0} keys · {environment} · Values are never displayed</p>{permissions['value:write'] && query.data?.items.some(item => item.material !== 'present') && <Button variant="outline" onClick={() => setBatch(query.data!.items.filter(item => item.material !== 'present'))}>Configure pending on this page</Button>}</div>
      <div className="overflow-x-auto rounded-technical border border-border bg-card">
        <table className="w-full text-left text-product-small"><thead className="border-b border-border bg-muted/30"><tr>{['Key', 'Format', 'Status', 'Used by', 'Actions'].map(label => <th key={label} className="p-ui-md font-medium">{label}</th>)}</tr></thead>
          <tbody>{query.data?.items.map(item => <tr key={item.id} className="border-b border-border last:border-0">
            <td className="p-ui-md"><span className="font-mono">{item.key}</span><p className="max-w-xl text-muted-foreground">{item.description}</p></td>
            <td className="p-ui-md">{item.kind} · {item.value_format}</td><td className="p-ui-md">{item.material === 'present' ? 'Configured' : item.material.replaceAll('_', ' ')}</td>
            <td className="p-ui-md"><Button variant="ghost" size="sm" onClick={() => setUsage(item)}>{item.used_by_count} consumers</Button></td>
            <td className="p-ui-md"><div className="flex flex-wrap gap-ui-sm">
              {(permissions['value:write'] || permissions['value:clear']) && <Button variant="outline" size="sm" onClick={() => setEditing({ item, environment })}>{item.material === 'present' ? 'Manage value' : 'Set value'}</Button>}
              {permissions.declare && <>
                <Button variant="outline" size="sm" onClick={() => setEditingDefinition(item)}>Edit key</Button>
                <Button variant="outline" size="sm" disabled={item.used_by_count > 0} title={item.used_by_count > 0 ? 'This key is in use. Edit it instead of deleting it.' : 'Check usage before deleting this key'} onClick={() => setDeleting(item)} aria-label={`Delete ${item.key}`}>Delete</Button>
                {item.used_by_count > 0 && <span className="self-center text-product-small text-muted-foreground">In use · edit only</span>}
              </>}
            </div></td>
          </tr>)}</tbody></table>
        {!query.data?.items.length && <p className="p-ui-lg text-muted-foreground">No configuration keys match this view.</p>}
      </div>
      <div className="flex justify-end gap-ui-sm"><Button variant="outline" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</Button><Button variant="outline" disabled={!query.data?.has_next} onClick={() => setOffset(offset + 50)}>Next</Button></div>
    </>}
    {batch && <ConfigurationBatchEditor key={`${projectId}:${environment}:batch`} projectId={projectId} environment={environment} keys={batch} onClose={() => setBatch(null)} onSaved={refresh} />}
    {editing && <ConfigurationValueEditor key={`${projectId}:${editing.item.id}`} projectId={projectId} item={editing.item} environment={editing.environment} onClose={() => setEditing(null)} onSaved={selected => { refresh(); selectEnvironment(selected) }} />}
    {creating && <ConfigurationKeyDeclarationDialog projectId={projectId} environment={environment} onClose={() => setCreating(false)} onSaved={refresh} onConfigure={(item, selected) => { setSearch(item.key); setStatus('all'); setOffset(0); setEditing({ item, environment: selected }) }} />}
    {editingDefinition && <ConfigurationKeyDeclarationDialog key={editingDefinition.id} projectId={projectId} item={editingDefinition} onClose={() => setEditingDefinition(null)} onSaved={refresh} />}
    {deleting && <ConfigurationKeyDeletionDialog key={deleting.id} projectId={projectId} item={deleting} environment={environment} onClose={() => setDeleting(null)} onSaved={refresh} />}
    {usage && <ConfigurationUsageDialog projectId={projectId} item={usage} environment={environment} canApprove={!!permissions['use-policy:write']} onClose={() => setUsage(null)} />}
  </ResourcePage>
}

