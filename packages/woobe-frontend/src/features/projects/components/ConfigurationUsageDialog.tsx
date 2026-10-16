import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Dialog, Field, FieldLabel, Select } from '@woobe/ui'
import { ApiError } from '@/lib/api/errors'
import { configurationKeyByName, configurationUsage, listConfigurationPolicies, grantConfigurationUse, revokeConfigurationUse,
  type ConfigurationKey, type ConfigurationConsumer, type ConfigurationUsage, type ConfigurationUsePolicy } from '../configuration'
import type { ProjectEnvironment } from '../types'

interface Props {
  projectId: string; item?: ConfigurationKey; keyName?: string; environment: ProjectEnvironment
  canApprove?: boolean; consumer?: { kind: string; id: string }; layer?: 'modal' | 'nestedModal'
  onEnvironmentChange?: (environment: ProjectEnvironment) => void; onClose: () => void
  onApprovalChange?: (approved: boolean) => void
}
const label = (environment: string) => environment[0].toUpperCase() + environment.slice(1)
const connectionLabel = (kind: string) => ({ provider_credential: 'Provider connection', tool: 'Tool connection', secret: 'Secret connection', mcp_oauth: 'MCP connection' }[kind] ?? 'Connection')
const fieldLabel = (path: string) => {
  const field = path.split('/').pop() ?? ''
  return { api_key: 'API key', token: 'Token', access_token: 'Access token', refresh_token: 'Refresh token', username: 'Username', password: 'Password', client_secret: 'Client secret' }[field] ?? field
}

export function ConfigurationUsageDialog({ projectId, item, keyName, environment, canApprove, consumer, layer = 'modal', onEnvironmentChange, onClose, onApprovalChange }: Props) {
  const [offset, setOffset] = useState(0)
  const [policyOffset, setPolicyOffset] = useState(0)
  const [showPolicies, setShowPolicies] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [revocation, setRevocation] = useState<ConfigurationUsePolicy | null>(null)
  const client = useQueryClient()
  const metadata = useQuery({ queryKey: ['configuration-access-key', projectId, keyName, environment],
    queryFn: () => configurationKeyByName(projectId, keyName!, environment), enabled: !item && !!keyName, retry: false })
  const key = item ?? metadata.data?.item
  const allowed = canApprove ?? !!metadata.data?.permissions['use-policy:write']
  const usageKey = ['configuration-usage', projectId, key?.id, environment, offset, consumer?.kind, consumer?.id]
  const usage = useQuery({ queryKey: usageKey,
    queryFn: () => configurationUsage(projectId, key!.id, offset, environment, consumer), enabled: !!key, retry: false })
  const policies = useQuery({ queryKey: ['configuration-policies', projectId, key?.id, policyOffset],
    queryFn: () => listConfigurationPolicies(projectId, key!.id, policyOffset), enabled: !!key && showPolicies, retry: false })
  useEffect(() => {
    if (!usage.isFetching && (usage.isSuccess || usage.isError)) onApprovalChange?.(!usage.isError
      && !!usage.data?.items.length && usage.data.items.every(row => row.approval?.state === 'approved'))
  }, [usage.data, usage.isFetching, usage.isSuccess, usage.isError, onApprovalChange])
  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['configuration-usage', projectId] }),
      client.invalidateQueries({ queryKey: ['configuration-policies', projectId] }),
      client.invalidateQueries({ queryKey: ['project-configuration', projectId] }),
      client.invalidateQueries({ queryKey: ['configuration-access-key', projectId] }),
      client.invalidateQueries({ queryKey: ['configuration-readiness', projectId] }),
      client.invalidateQueries({ queryKey: ['configuration-summary', projectId] }),
    ])
  }
  const save = async (row?: ConfigurationConsumer) => {
    if (!key || pending) return
    setPending(true); setError('')
    try {
      if (row) await grantConfigurationUse(projectId, key.id, row, environment, row.approval?.update_policy ?? undefined)
      else if (revocation) await revokeConfigurationUse(projectId, revocation)
      setRevocation(null)
      await refresh()
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        await refresh()
        const alreadyApproved = row && client.getQueryData<ConfigurationUsage>(usageKey)?.items.some(latest =>
          latest.consumer_kind === row.consumer_kind && latest.consumer_id === row.consumer_id
          && latest.destination === row.destination && latest.field_path === row.field_path
          && latest.definition_revision === row.definition_revision && latest.approval?.state === 'approved')
        setError(alreadyApproved ? '' : 'Access changed while this screen was open. Review the refreshed status before trying again.')
      } else setError(error instanceof ApiError && error.status === 403
        ? `You need permission to approve use in ${label(environment)}. Ask a project administrator.`
        : 'Could not save the approval. Refresh access status and try again.')
    } finally { setPending(false) }
  }
  return <Dialog open layer={layer} onClose={pending ? () => undefined : onClose} title={`Access approvals · ${key?.key ?? keyName ?? 'Configuration'}`}>
    <div className="space-y-ui-lg p-ui-lg">
      <p className="text-product-small text-muted-foreground">Save a value, then approve each connection that may use it. Approval applies only to the environment and destination shown.</p>
      {onEnvironmentChange ? <Field><FieldLabel htmlFor="configuration-usage-environment">Environment</FieldLabel><Select id="configuration-usage-environment" value={environment} disabled={pending || !!revocation} onChange={event => { setOffset(0); setError(''); onEnvironmentChange(event.target.value as ProjectEnvironment) }} options={['draft', 'staging', 'production'].map(value => ({ value, label: label(value) }))} /></Field>
        : <p className="text-product-label">Environment: {label(environment)}</p>}
      {key && <p className="text-product-small">{key.values[environment]?.configured ? 'Value saved.' : key.values[environment] ? 'Set a value in Environments before using this connection.' : 'Check the key value in Environments.'} Use approval is checked separately.</p>}
      {error && <p role="alert" className="text-product-small text-destructive">{error}</p>}
      {!key ? <p role="status">{metadata.isError ? 'This key is unavailable or access is restricted.' : 'Loading access status…'}</p>
        : usage.isPending ? <p role="status">Checking connection approvals…</p>
        : usage.isError ? <p role="alert">{usage.error instanceof ApiError && usage.error.status === 403 ? 'You need permission to review access approvals. Ask a project administrator.' : 'Could not check approvals. Refresh access status to retry.'}</p> : <>
          <ul className="space-y-ui-md">{usage.data?.items.map(row => {
            const approved = row.approval?.state === 'approved'
            return <li key={`${row.consumer_kind}:${row.consumer_id}:${row.definition_revision}:${row.field_path}`} className="space-y-ui-sm rounded-technical border border-border p-ui-md">
              <p className="text-product-label">{connectionLabel(row.consumer_kind)} · {fieldLabel(row.field_path)}</p>
              <p className="break-all text-product-small">{row.destination || 'Set a destination on this connection first.'}</p>
              <p role="status" className={`text-product-small font-medium ${approved ? 'text-primary' : 'text-muted-foreground'}`}>{approved ? `Use approved in ${label(environment)}` : row.approval?.state === 'approval_required' ? `Approval required in ${label(environment)}` : row.approval?.state === 'destination_required' ? 'Destination required' : 'Approval status unavailable'}</p>
              {approved ? allowed && row.approval?.policy && <Button variant="outline" size="sm" disabled={pending} onClick={() => setRevocation(row.approval!.policy)}>Revoke access</Button>
                : allowed && row.approval?.state === 'approval_required' && <>
                  <p className="text-product-small text-muted-foreground">Approving allows this connection to send the value to this destination and its child paths.</p>
                  <Button size="sm" disabled={pending} onClick={() => { void save(row) }}>{pending ? 'Saving…' : `Approve use in ${label(environment)}`}</Button>
                </>}
              {!allowed && !approved && <p className="text-product-small text-muted-foreground">Ask a project administrator to approve this connection.</p>}
              <details className="text-product-small text-muted-foreground"><summary className="cursor-pointer">Connection details</summary><p className="break-all">{row.consumer_id}</p><p className="break-all">{row.field_path} · revision {row.definition_revision}</p></details>
            </li>
          })}</ul>
          {!usage.data?.items.length && <p>No saved connections use this key yet. Save a connection first, then approve its use here.</p>}
          {(offset > 0 || (usage.data?.total ?? 0) > 50) && <div className="flex justify-end gap-ui-sm"><Button variant="outline" disabled={!offset || pending} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous connections</Button><Button variant="outline" disabled={offset + 50 >= (usage.data?.total ?? 0) || pending} onClick={() => setOffset(offset + 50)}>Next connections</Button></div>}
        </>}
      {revocation && <section className="space-y-ui-sm rounded-technical border border-border p-ui-md" aria-label="Confirm access revocation">
        <p className="text-product-label">Revoke this approval?</p><p className="break-all text-product-small">{revocation.destination}</p>
        <p className="text-product-small">This approval will stop working in {revocation.environments.map(label).join(', ')} for every connection and field it covers.</p>
        <div className="flex flex-wrap justify-end gap-ui-sm"><Button variant="outline" disabled={pending} onClick={() => setRevocation(null)}>Cancel</Button><Button disabled={pending} onClick={() => { void save() }}>Revoke approval</Button></div>
      </section>}
      {key && <details onToggle={event => setShowPolicies(event.currentTarget.open)} className="text-product-small">
        <summary className="cursor-pointer text-muted-foreground">All saved approvals</summary>
        {policies.isError ? <p>Saved approvals are unavailable.</p> : <ul className="space-y-ui-sm py-ui-md">{policies.data?.items.map(policy => <li key={policy.id} className="space-y-ui-xs"><p className="break-all">{policy.destination}</p><p>{policy.revoked ? 'Revoked' : policy.environments.map(label).join(', ')}</p>{allowed && !policy.revoked && <Button variant="outline" size="sm" disabled={pending} onClick={() => setRevocation(policy)}>Revoke access</Button>}</li>)}</ul>}
        {(policyOffset > 0 || (policies.data?.total ?? 0) > 50) && <div className="flex gap-ui-sm"><Button disabled={!policyOffset} onClick={() => setPolicyOffset(Math.max(0, policyOffset - 50))}>Previous approvals</Button><Button disabled={policyOffset + 50 >= (policies.data?.total ?? 0)} onClick={() => setPolicyOffset(policyOffset + 50)}>Next approvals</Button></div>}
      </details>}
      <div className="flex flex-wrap justify-end gap-ui-sm"><Button variant="outline" disabled={pending || usage.isFetching} onClick={() => { setError(''); void usage.refetch(); if (!item) void metadata.refetch() }}>Refresh access status</Button><Button onClick={onClose} disabled={pending}>Done</Button></div>
    </div>
  </Dialog>
}
