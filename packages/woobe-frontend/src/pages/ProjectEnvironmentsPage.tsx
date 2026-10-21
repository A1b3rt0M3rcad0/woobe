import { ConfigurationEnvironmentComparison } from '@/features/projects/components/ConfigurationEnvironmentComparison'
import { ConfigurationLegacyPanel } from '@/features/projects/components/ConfigurationLegacyPanel'
import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useQueries, useQueryClient } from '@tanstack/react-query'
import { Button, Field, FieldLabel, Input, Select } from '@woobe/ui'
import { ResourcePage } from '@/components/common/ResourcePage'
import { ApiError } from '@/lib/api/errors'
import { configurationReturnPath, listConfiguration, type ConfigurationKey, type ConfigurationPage } from '@/features/projects/configuration'
import { ConfigurationKeyDeclarationDialog } from '@/features/projects/components/ConfigurationKeyDeclarationDialog'
import { ConfigurationKeyDeletionDialog } from '@/features/projects/components/ConfigurationKeyDeletionDialog'
import { ConfigurationUsageDialog } from '@/features/projects/components/ConfigurationUsageDialog'
import { ConfigurationValueEditor } from '@/features/projects/components/ConfigurationValueEditor'
import type { ProjectEnvironment } from '@/features/projects/types'

export default function ProjectEnvironmentsPage() {
  const { projectId } = useParams()
  return projectId ? <EnvironmentWorkspace key={projectId} projectId={projectId} /> : null
}

const environments: ProjectEnvironment[] = ['draft', 'staging', 'production']
const environmentLabel = (environment: ProjectEnvironment) => environment[0].toUpperCase() + environment.slice(1)
const materialLabels = { present: 'Value saved', missing: 'Not set', invalid_format: 'Invalid format', revoked: 'Revoked', unavailable: 'Unavailable' }

function EnvironmentWorkspace({ projectId }: { projectId: string }) {
  const [params] = useSearchParams()
  const returnTo = configurationReturnPath(params.get('returnTo'), projectId, window.location.origin)
  const selected = params.get('environment')
  const initialEnvironment: ProjectEnvironment = selected === 'staging' || selected === 'production' ? selected : 'draft'
  const [preferredEnvironment, setPreferredEnvironment] = useState(initialEnvironment)
  const requestedKey = params.get('key')
  const initialSearch = requestedKey && /^[A-Za-z_][A-Za-z0-9_]{0,127}$/.test(requestedKey) ? requestedKey : ''
  const [search, setSearch] = useState(initialSearch)
  const [offset, setOffset] = useState(0)
  const [editing, setEditing] = useState<{ item: ConfigurationKey; environment: ProjectEnvironment } | null>(null)
  const [editingDefinition, setEditingDefinition] = useState<ConfigurationKey | null>(null)
  const [deleting, setDeleting] = useState<ConfigurationKey | null>(null)
  const [usage, setUsage] = useState<{ item: ConfigurationKey; environment: ProjectEnvironment } | null>(null)
  const [creating, setCreating] = useState(false)
  const [view, setView] = useState<'keys' | 'compare' | 'legacy'>('keys')
  useEffect(() => { setPreferredEnvironment(initialEnvironment) }, [initialEnvironment])
  const client = useQueryClient()
  // Each response is authorized independently. All requests use the same shared
  // declaration ordering/page; denied environments never borrow another's state.
  const queries = useQueries({ queries: environments.map(environment => ({
    queryKey: ['project-configuration', projectId, environment, search, 'all', offset],
    queryFn: () => listConfiguration(projectId, environment, search, 'all', offset), retry: false,
  })) })
  const sourceIndex = queries.findIndex(query => query.isSuccess)
  const catalog = queries[sourceIndex]?.data
  const sourceEnvironment = environments[sourceIndex] ?? 'draft'
  const permissionsFor = (environment: ProjectEnvironment): ConfigurationPage['permissions'] => {
    const query = queries[environments.indexOf(environment)]
    return query.isSuccess ? query.data.permissions : {}
  }
  const canDeclare = environments.some(environment => permissionsFor(environment).declare)
  const canManageValues = environments.some(environment => permissionsFor(environment)['value:write'] || permissionsFor(environment)['value:clear'])
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ['project-configuration', projectId] })
    void client.invalidateQueries({ queryKey: ['configuration-readiness', projectId] })
    void client.invalidateQueries({ queryKey: ['configuration-summary', projectId] })
    void client.invalidateQueries({ queryKey: ['configuration-key-editor', projectId] })
    void client.invalidateQueries({ queryKey: ['configuration-deletion', projectId] })
  }
  return <ResourcePage title="Environments" description="Set a value, then approve which connections can use it in each environment.">
    {returnTo && <a href={returnTo} className="text-product-small text-primary underline underline-offset-2">Back to previous screen</a>}
    <div className="flex flex-wrap items-end justify-between gap-ui-md rounded-technical border border-border bg-card p-ui-md">
      <div className="flex flex-wrap items-end gap-ui-sm">
        <Field><FieldLabel htmlFor="configuration-search">Search keys</FieldLabel><Input id="configuration-search" value={search} onChange={e => { setSearch(e.target.value); setOffset(0) }} placeholder="Name or description" /></Field>
      </div>
      {canDeclare && <Button onClick={() => setCreating(true)}>Add key</Button>}
    </div>
    <div className="flex flex-wrap gap-ui-sm" aria-label="Configuration views">{(['keys', 'compare', 'legacy'] as const).map(item => <Button key={item} variant={view === item ? 'default' : 'outline'} onClick={() => { setView(item); setOffset(0) }}>{item === 'keys' ? 'Keys' : item === 'compare' ? 'Compare environments' : 'Legacy mappings'}</Button>)}</div>
    {view === 'compare' ? <ConfigurationEnvironmentComparison projectId={projectId} search={search} /> : view === 'legacy' ? <>
      <Field className="max-w-xs"><FieldLabel htmlFor="configuration-legacy-environment">Environment for legacy mappings</FieldLabel><Select id="configuration-legacy-environment" value={preferredEnvironment} onChange={event => setPreferredEnvironment(event.target.value as ProjectEnvironment)} options={environments.map(value => ({ value, label: environmentLabel(value) }))} /></Field>
      <ConfigurationLegacyPanel key={`${projectId}:${preferredEnvironment}`} projectId={projectId} environment={preferredEnvironment} canConvert={!!permissionsFor(preferredEnvironment).migrate && !!permissionsFor(preferredEnvironment)['value:write']} onSaved={refresh} />
    </> : !catalog && queries.some(query => query.isPending) ? <p role="status">Loading configuration…</p> : !catalog ? <div role="alert" className="rounded-technical border border-border p-ui-lg">
      <p>{queries.some(query => query.error instanceof ApiError && query.error.status === 403) ? 'You do not have access to this project’s configuration.' : 'Configuration is unavailable. Readiness cannot be confirmed.'}</p>
      <Button variant="outline" onClick={() => queries.forEach(query => void query.refetch())}>Retry</Button>
    </div> : <>
      <p className="text-product-small text-muted-foreground">{catalog.total} keys · 1. Save a value · 2. Approve connection use · Values are never displayed.</p>
      {queries.some(query => query.isError) && <p role="status" className="text-product-small text-muted-foreground">Some environments are unavailable or restricted.</p>}
      <div className="min-w-0 overflow-x-auto rounded-technical border border-border bg-card" role="region" aria-label="Configuration keys" tabIndex={0}>
        <table className="w-full min-w-[64rem] table-fixed text-left text-product-small"><thead className="border-b border-border bg-muted/30"><tr>
          <th className="w-56 p-ui-md font-medium">Key</th><th className="w-28 p-ui-md font-medium">Format</th>
          {environments.map(environment => <th key={environment} scope="col" className="w-32 p-ui-md font-medium">{environmentLabel(environment)}</th>)}
          <th className="w-32 p-ui-md font-medium">Connections</th><th className="w-56 p-ui-md font-medium">Actions</th>
        </tr></thead>
          <tbody>{catalog.items.map(item => <tr key={item.id} className="border-b border-border last:border-0">
            <td className="p-ui-md"><div role="region" aria-label={`Key ${item.key}`} tabIndex={0} className="overflow-x-auto whitespace-nowrap font-mono focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/30" title={item.key}>{item.key}</div><p className="mt-ui-xs break-words text-muted-foreground [overflow-wrap:anywhere]">{item.description}</p></td>
            <td className="p-ui-md">{item.kind} · {item.value_format}</td>
            {queries.map((query, index) => {
              const metadata = query.data?.items.find(key => key.id === item.id)
              const status = query.isPending ? 'Loading…' : query.isError ? 'Unavailable or restricted' : metadata ? materialLabels[metadata.material] : 'Unavailable on this page'
              const approval = metadata?.approval
              const approvalLabel = approval?.state === 'approved' ? 'Use approved' : approval?.state === 'approval_required'
                ? `Approval required${approval.approved_connection_count ? ` · ${approval.approved_connection_count}/${approval.connection_count} approved` : ''}`
                : approval?.state === 'no_connections' ? 'No connections yet' : null
              return <td key={environments[index]} className="p-ui-md" aria-label={`${environmentLabel(environments[index])} status: ${status}`}><p>{status}</p>{!query.isError && approvalLabel && <p className={`mt-ui-xs text-product-caption ${approval?.state === 'approval_required' ? 'text-primary' : 'text-muted-foreground'}`}>{approvalLabel}</p>}</td>
            })}
            <td className="p-ui-md">{item.used_by_count} {item.used_by_count === 1 ? 'connection' : 'connections'}</td>
            <td className="p-ui-md"><div className="flex flex-wrap gap-ui-sm">
              {canManageValues && <Button variant="outline" size="sm" onClick={() => setEditing({ item, environment: preferredEnvironment })}>Manage values</Button>}
              {item.used_by_count > 0 && <Button variant="outline" size="sm" onClick={() => setUsage({ item, environment: preferredEnvironment })}>Manage approvals</Button>}
              {canDeclare && <>
                <Button variant="outline" size="sm" onClick={() => setEditingDefinition(item)}>Edit key</Button>
                <Button variant="outline" size="sm" disabled={item.used_by_count > 0} title={item.used_by_count > 0 ? 'This key is in use. Edit it instead of deleting it.' : 'Check usage before deleting this key'} onClick={() => setDeleting(item)} aria-label={`Delete ${item.key}`}>Delete</Button>
                {item.used_by_count > 0 && <span className="self-center text-product-small text-muted-foreground">In use · edit only</span>}
              </>}
            </div></td>
          </tr>)}</tbody></table>
        {!catalog.items.length && <p className="p-ui-lg text-muted-foreground">No configuration keys match this view.</p>}
      </div>
      <div className="flex justify-end gap-ui-sm"><Button variant="outline" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</Button><Button variant="outline" disabled={!catalog.has_next} onClick={() => setOffset(offset + 50)}>Next</Button></div>
    </>}
    {editing && <ConfigurationValueEditor key={`${projectId}:${editing.item.id}`} projectId={projectId} item={editing.item} environment={editing.environment} onClose={() => setEditing(null)} onSaved={selected => { refresh(); setPreferredEnvironment(selected) }} />}
    {creating && <ConfigurationKeyDeclarationDialog projectId={projectId} environment={preferredEnvironment} onClose={() => setCreating(false)} onSaved={refresh} onConfigure={(item, selected) => { setSearch(item.key); setOffset(0); setEditing({ item, environment: selected }) }} />}
    {editingDefinition && <ConfigurationKeyDeclarationDialog key={editingDefinition.id} projectId={projectId} item={editingDefinition} onClose={() => setEditingDefinition(null)} onSaved={refresh} />}
    {deleting && <ConfigurationKeyDeletionDialog key={deleting.id} projectId={projectId} item={deleting} environment={sourceEnvironment} onClose={() => setDeleting(null)} onSaved={refresh} />}
    {usage && <ConfigurationUsageDialog projectId={projectId} item={usage.item} environment={usage.environment} onEnvironmentChange={environment => setUsage({ ...usage, environment })} canApprove={!!permissionsFor(usage.environment)['use-policy:write']} onClose={() => setUsage(null)} />}
  </ResourcePage>
}

