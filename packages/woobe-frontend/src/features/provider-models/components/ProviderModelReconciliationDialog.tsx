import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { applyProviderModels, previewProviderModels } from '../api'
import { ProviderDiscoveryErrorNotice } from './ProviderDiscoveryErrorNotice'

export function ProviderModelReconciliationDialog({ projectId, credentialId, onClose }: {
  projectId: string; credentialId: string; onClose: () => void
}) {
  const [capability, setCapability] = useState<'generation' | 'embedding'>('generation')
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [confirm, setConfirm] = useState(false)
  const queryClient = useQueryClient()
  const scope = { project_id: projectId, provider_credential_id: credentialId, environment: 'draft', capability }
  const preview = useQuery({ queryKey: ['provider-model-reconciliation', scope], queryFn: () => previewProviderModels(scope),
    retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false })
  const apply = useMutation({
    mutationFn: () => applyProviderModels(scope, preview.data!, preview.data!.items.filter((_, index) => selected.has(index))),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['provider-models'] })
      queryClient.invalidateQueries({ queryKey: ['available-provider-models'] })
      setSelected(new Set())
      setConfirm(false)
    },
  })
  return <Dialog open layer="nestedModal" onClose={apply.isPending ? () => undefined : onClose} title="Compare with provider">
    <div className="space-y-ui-md p-ui-lg">
      <p className="text-product-body text-muted-foreground">Review current provider evidence and select definitions to install. Existing Releases retain their published bindings. Adopt the resulting Model explicitly on an Agent Draft.</p>
      <label className="block">Operation <select aria-label="Catalog operation" value={capability} disabled={apply.isPending} onChange={event => {
        setCapability(event.target.value as 'generation' | 'embedding'); setSelected(new Set()); setConfirm(false)
      }} className="block w-full min-w-0 max-w-full rounded-control border bg-background p-ui-sm">
        <option value="generation">Language generation</option><option value="embedding">Embeddings · Vector Snapshots require 1536 dimensions</option>
      </select></label>
      {preview.isPending && <p>Loading provider catalog…</p>}
      {preview.error && <ProviderDiscoveryErrorNotice projectId={projectId} error={preview.error} onRetry={() => { void preview.refetch() }} />}
      {preview.data && <div className="max-h-[55vh] overflow-auto"><table className="w-full text-left text-product-caption">
        <thead><tr><th>Select</th><th>Model / operation</th><th>Change / source</th><th>Input / output price per 1M tokens</th></tr></thead>
        <tbody>{preview.data.items.map((item, index) => <tr key={`${item.model_id}:${item.installed_model_id}`} className="border-t">
          <td><input type="checkbox" aria-label={`Select ${item.label}`} disabled={!item.proposed_spec || item.change_kind === 'unchanged' || apply.isPending || apply.isSuccess} checked={selected.has(index)} onChange={event => {
            const next = new Set(selected); if (event.target.checked) next.add(index); else next.delete(index)
            setSelected(next); setConfirm(false)
          }} /></td>
          <td className="p-ui-sm">{item.label}<div className="font-mono text-muted-foreground">{item.proposed_spec?.operations?.join(', ') || item.model_id}</div></td>
          <td>{item.state}<div className="text-muted-foreground">{item.proposed_spec?.source || 'Unknown'}</div></td>
          <td>{[item.installed_spec, item.proposed_spec].map((spec, side) => <div key={side}>{side === 0 ? 'Installed' : 'Provider + overrides'}: {spec?.pricing?.currency || 'USD'} {spec?.pricing?.input_cost_per_1m_tokens ?? 'Unknown'} / {spec?.pricing?.output_cost_per_1m_tokens ?? 'Unknown'}</div>)}</td>
        </tr>)}</tbody>
      </table></div>}
      {apply.error && <p role="alert">{apply.error.message} Refresh the comparison before retrying.</p>}
      {apply.data && <div role="status">{apply.data.items.map(item => <p key={item.model_id}>{item.model_id}: {item.result}{item.evidence_updated ? ' · catalog evidence updated' : ''} · {item.provider_model_id}</p>)}<p>{apply.data.adoption}</p></div>}
      {confirm && <p role="alert">Apply {selected.size} selected definitions using the reviewed evidence?</p>}
      <div className="flex flex-wrap justify-end gap-ui-sm">
        <Button variant="outline" disabled={apply.isPending} onClick={() => { setSelected(new Set()); setConfirm(false); apply.reset(); void preview.refetch() }}>Refresh comparison</Button>
        <Button disabled={!selected.size || apply.isPending || preview.isFetching} onClick={() => confirm ? apply.mutate() : setConfirm(true)}>{apply.isPending ? 'Applying…' : confirm ? 'Confirm selected changes' : 'Apply selected'}</Button>
      </div>
    </div>
  </Dialog>
}
