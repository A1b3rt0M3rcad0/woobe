import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button, Dialog } from '@woobe/ui'
import { configurationUsage, listConfigurationPolicies, grantConfigurationUse, revokeConfigurationUse,
  type ConfigurationKey, type ConfigurationConsumer, type ConfigurationUsePolicy } from '../configuration'
import type { ProjectEnvironment } from '../types'

interface Props { projectId: string; item: ConfigurationKey; environment: ProjectEnvironment; canApprove: boolean; onClose: () => void }

export function ConfigurationUsageDialog({ projectId, item, environment, canApprove, onClose }: Props) {
  const [offset, setOffset] = useState(0)
  const [policyOffset, setPolicyOffset] = useState(0)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [approval, setApproval] = useState<ConfigurationConsumer | null>(null)
  const [revocation, setRevocation] = useState<ConfigurationUsePolicy | null>(null)
  const usage = useQuery({ queryKey: ['configuration-usage', projectId, item.id, offset], queryFn: () => configurationUsage(projectId, item.id, offset), retry: false })
  const policies = useQuery({ queryKey: ['configuration-policies', projectId, item.id, policyOffset], queryFn: () => listConfigurationPolicies(projectId, item.id, policyOffset), retry: false })
  const save = async () => {
    setPending(true); setError('')
    try {
      if (approval) {
        const existing = policies.data?.items.find(p => p.consumer_kind === approval.consumer_kind && p.consumer_scope === approval.consumer_id && p.destination === approval.destination)
        await grantConfigurationUse(projectId, item.id, approval, environment, existing)
      } else if (revocation) await revokeConfigurationUse(projectId, revocation)
      setApproval(null); setRevocation(null)
      await policies.refetch()
    } catch { setError('Approval could not be updated. Refresh the list and check your environment permissions before retrying.') }
    finally { setPending(false) }
  }
  return <Dialog open onClose={onClose} title={`Usage · ${item.key}`}>
    <div className="space-y-ui-lg p-ui-lg">
      <section className="space-y-ui-sm"><h3 className="text-product-label">Consumers</h3>
        {usage.isLoading ? <p>Loading consumers…</p> : usage.isError ? <p role="alert">Consumer information is unavailable.</p> : <>
          <ul className="divide-y divide-border">{usage.data?.items.map(row => <li key={`${row.consumer_kind}:${row.consumer_id}:${row.definition_revision}:${row.field_path}`} className="flex flex-wrap items-center justify-between gap-ui-md py-ui-sm">
            <div className="min-w-0"><p className="break-all">{row.consumer_kind} · {row.consumer_id}</p>
              <p className="break-all font-sans text-product-small text-muted-foreground">{row.field_path} · revision {row.definition_revision}</p>
              <p className="break-all text-product-small">{row.destination || 'Destination resolved by the selected definition'}</p></div>
            {canApprove && row.destination && <Button variant="outline" size="sm" disabled={!policies.data || pending} onClick={() => setApproval(row)}>Approve for {environment}</Button>}
          </li>)}</ul>
          {!usage.data?.items.length && <p>No registered consumers.</p>}
          <div className="flex justify-end gap-ui-sm"><Button variant="outline" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous consumers</Button><Button variant="outline" disabled={offset + 50 >= (usage.data?.total ?? 0)} onClick={() => setOffset(offset + 50)}>Next consumers</Button></div>
        </>}
      </section>
      <section className="space-y-ui-sm border-t border-border pt-ui-md"><h3 className="text-product-label">Approved destinations</h3>
        {policies.isLoading ? <p>Loading approvals…</p> : policies.isError ? <p role="alert">Approval information is unavailable.</p> : <>
          <ul className="divide-y divide-border">{policies.data?.items.map(row => <li key={row.id} className="flex flex-wrap justify-between gap-ui-sm py-ui-sm"><div><p className="break-all">{row.destination}</p><p className="text-product-small text-muted-foreground">{row.revoked ? 'Revoked' : row.environments.join(', ')} · {row.consumer_kind} · {row.consumer_scope}</p></div>
            {canApprove && !row.revoked && <Button variant="outline" size="sm" onClick={() => setRevocation(row)}>Revoke</Button>}</li>)}</ul>
          {!policies.data?.items.length && <p>No approved destinations.</p>}
          <div className="flex justify-end gap-ui-sm"><Button variant="outline" disabled={!policyOffset} onClick={() => setPolicyOffset(Math.max(0, policyOffset - 50))}>Previous approvals</Button><Button variant="outline" disabled={policyOffset + 50 >= (policies.data?.total ?? 0)} onClick={() => setPolicyOffset(policyOffset + 50)}>Next approvals</Button></div>
        </>}
      </section>
    </div>
    {(approval || revocation) && <Dialog open layer="nestedModal" onClose={() => { if (!pending) { setApproval(null); setRevocation(null); setError('') } }} title={approval ? `Approve use in ${environment}?` : 'Revoke this approval?'}>
      <div className="space-y-ui-md p-ui-lg"><p className="break-all font-sans">{approval?.destination ?? revocation?.destination}</p>
        <p>{approval ? 'This consumer will be allowed to send the configured value to this destination and its child paths. Review the host and path before approving.' : `New calls using this approval will stop in ${revocation?.environments.join(', ')}. Existing Runs must obtain new authorization.`}</p>
        {error && <p role="alert" className="text-destructive">{error}</p>}
        <div className="flex justify-end gap-ui-sm"><Button variant="outline" disabled={pending} onClick={() => { setApproval(null); setRevocation(null); setError('') }}>Cancel</Button><Button disabled={pending} onClick={() => void save()}>{pending ? 'Saving…' : approval ? 'Approve use' : 'Revoke approval'}</Button></div>
      </div>
    </Dialog>}
  </Dialog>
}
