import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@woobe/ui'
import type { ProviderCredential } from '../types'
import { listConfiguration } from '@/features/projects/configuration'
import { ConfigurationValueEditor } from '@/features/projects/components/ConfigurationValueEditor'
import { ConfigurationUsageDialog } from '@/features/projects/components/ConfigurationUsageDialog'

/** Reuses the central configuration editors. It never reads a secret value. */
export function ProviderConnectionConfiguration({ credential }: { credential: ProviderCredential }) {
  const reference = credential.authentication?.fields.api_key
  const legacy = reference?.source === 'legacy_configuration'
  const key = legacy ? undefined : reference?.key
  const client = useQueryClient()
  const [editor, setEditor] = useState<'value' | 'usage' | null>(null)
  const query = useQuery({ queryKey: ['project-configuration', credential.project_id, 'connection', key],
    queryFn: () => listConfiguration(credential.project_id, 'draft', key), enabled: Boolean(key), retry: false })
  if (legacy || !reference) return <p className="text-sm text-muted-foreground">This connection uses legacy credential storage. Configure its migration in Project → Environments.</p>
  if (!key) return <p className="text-sm text-muted-foreground">The API key reference is unavailable. Review the connection in Environments.</p>
  const item = query.data?.items.find(item => item.key === key)
  const permissions = query.data?.permissions ?? {}
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ['project-configuration', credential.project_id] })
    void client.invalidateQueries({ queryKey: ['configuration-readiness', credential.project_id] })
  }
  return <section aria-label="Draft credential setup" className="space-y-3 rounded-control border border-border bg-background/30 p-4">
    <div><h3 className="text-sm font-medium text-foreground">Draft API key</h3><p className="mt-1 break-all font-mono text-xs text-muted-foreground">{key}</p></div>
    {query.isLoading ? <p role="status" className="text-sm text-muted-foreground">Checking the key’s configuration…</p> : query.isError || !item ? <div role="alert" className="text-sm text-muted-foreground"><p>Configuration is unavailable or your access is restricted. An authorized operator can finish it in Environments.</p><Button size="sm" variant="outline" onClick={() => { void query.refetch() }}>Retry configuration</Button></div> : <>
      <p className="text-sm text-muted-foreground">{item.material === 'present' ? 'A value is saved in Draft. This does not confirm provider access.' : item.material === 'missing' ? 'No value is saved in Draft yet. The connection stores a reference, not the API key itself.' : `Draft value needs attention (${item.material.replaceAll('_', ' ')}).`}</p>
      <div className="flex flex-wrap gap-2">
        {!!permissions['value:write'] && <Button type="button" size="sm" variant="outline" onClick={() => setEditor('value')}>{item.material === 'present' ? 'Replace Draft API key' : 'Set Draft API key'}</Button>}
        <Button type="button" size="sm" variant="outline" onClick={() => setEditor('usage')}>Review destination access</Button>
      </div>
      {!permissions['value:write'] && <p className="text-sm text-muted-foreground">Ask an operator with Draft value permissions to set the API key.</p>}
      <p className="text-xs leading-5 text-muted-foreground">Before browsing models or testing, save the value and approve this connection’s destination. Staging and Production keep separate values and approvals.</p>
      {editor === 'value' && <ConfigurationValueEditor projectId={credential.project_id} item={item} environment="draft" canWrite={!!permissions['value:write']} canClear={!!permissions['value:clear']} onClose={() => setEditor(null)} onSaved={refresh} />}
      {editor === 'usage' && <ConfigurationUsageDialog projectId={credential.project_id} item={item} environment="draft" canApprove={!!permissions['use-policy:write']} onClose={() => { setEditor(null); refresh() }} />}
    </>}
  </section>
}
