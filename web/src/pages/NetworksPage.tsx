import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Activity, ArrowRight, Network, PencilLine, Plus, Search, X } from 'lucide-react'
import { toast } from 'sonner'

import { useCreateNetwork, useNetworks, useUpdateNetworkMetadata } from '@/features/network/hooks'
import type { NetworkResource } from '@/features/network/types'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'

function environmentLabel(network: NetworkResource) {
  if (network.production_version_id) return 'Production'
  if (network.staging_version_id) return 'Staging'
  return network.draft_revision > 0 ? `Draft r${network.draft_revision}` : 'Draft setup'
}

function NetworkModal({
  title,
  initialName = '',
  initialDescription = '',
  pending,
  onClose,
  onSubmit,
}: {
  title: string
  initialName?: string
  initialDescription?: string
  pending: boolean
  onClose: () => void
  onSubmit: (input: { name: string; description: string }) => Promise<void>
}) {
  const [name, setName] = useState(initialName)
  const [description, setDescription] = useState(initialDescription)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const normalizedName = name.trim()
    if (!normalizedName) {
      toast.error('Network name is required')
      return
    }
    await onSubmit({ name: normalizedName, description: description.trim() })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <form onSubmit={(event) => void submit(event)} className="w-full max-w-lg rounded-2xl border border-border bg-surface shadow-2xl">
        <div className="flex items-start border-b border-border p-5">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-light">Network</p>
            <h2 className="mt-1 text-base font-semibold text-white">{title}</h2>
          </div>
          <button type="button" onClick={onClose} className="ml-auto rounded-lg p-2 text-muted hover:bg-background hover:text-white"><X className="h-4 w-4" /></button>
        </div>
        <div className="space-y-4 p-5">
          <label className="block">
            <span className="text-xs font-medium text-slate-200">Name</span>
            <input autoFocus value={name} onChange={(event) => setName(event.target.value)} maxLength={255} className="mt-2 w-full rounded-xl border border-border bg-background/70 px-3 py-2.5 text-sm text-white outline-none focus:border-primary/60" placeholder="Customer Support" />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-200">Description</span>
            <textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={4000} rows={4} className="mt-2 w-full resize-none rounded-xl border border-border bg-background/70 px-3 py-2.5 text-sm text-white outline-none focus:border-primary/60" placeholder="Operational purpose of this Network" />
          </label>
        </div>
        <div className="flex justify-end gap-2 border-t border-border p-4">
          <button type="button" onClick={onClose} className="rounded-lg border border-border px-3 py-2 text-xs text-muted hover:text-white">Cancel</button>
          <button type="submit" disabled={pending} className="rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-white disabled:opacity-50">{pending ? 'Saving…' : 'Save Network'}</button>
        </div>
      </form>
    </div>
  )
}

export default function NetworksPage() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useWorkspace()
  const networksQuery = useNetworks(projectId)
  const createMutation = useCreateNetwork(projectId)
  const [search, setSearch] = useState('')
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<NetworkResource | null>(null)
  const updateMutation = useUpdateNetworkMetadata(projectId, editing?.id)

  const networks = useMemo(() => {
    const query = search.trim().toLowerCase()
    const items = networksQuery.data ?? []
    if (!query) return items
    return items.filter((item) => `${item.name} ${item.description}`.toLowerCase().includes(query))
  }, [networksQuery.data, search])

  const openNetwork = (networkId: string) => {
    navigate(`/organizations/${organizationId}/projects/${projectId}/networks/${networkId}`)
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-primary-light">Build</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-white">Networks</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">Independent agent compositions inside {currentProject?.name ?? 'this Project'}, each with its own Draft, Staging, Production, sessions and Runs.</p>
        </div>
        <button type="button" onClick={() => setCreating(true)} className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white"><Plus className="h-4 w-4" />Create Network</button>
      </header>

      <div className="flex items-center rounded-xl border border-border bg-surface/60 px-3">
        <Search className="h-4 w-4 text-muted" />
        <input value={search} onChange={(event) => setSearch(event.target.value)} className="w-full bg-transparent px-3 py-2.5 text-sm text-white outline-none" placeholder="Search Networks" />
      </div>

      {networksQuery.isLoading ? (
        <div className="rounded-2xl border border-border bg-surface/60 p-8 text-center text-sm text-muted">Loading Networks…</div>
      ) : networksQuery.isError ? (
        <div className="rounded-2xl border border-red-500/25 bg-red-500/5 p-8 text-center">
          <p className="text-sm font-medium text-red-200">Unable to load Networks</p>
          <button type="button" onClick={() => void networksQuery.refetch()} className="mt-3 rounded-lg border border-border px-3 py-2 text-xs text-white">Retry</button>
        </div>
      ) : (networksQuery.data?.length ?? 0) === 0 ? (
        <div className="flex min-h-[360px] flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-surface/40 p-8 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-primary/25 bg-primary/10 text-primary-light"><Network className="h-6 w-6" /></div>
          <h2 className="mt-4 text-base font-semibold text-white">Create the first Network</h2>
          <p className="mt-2 max-w-md text-sm leading-6 text-muted">Opening this page does not create resources. Create a Network explicitly, then choose its entry Agent and composition.</p>
          <button type="button" onClick={() => setCreating(true)} className="mt-5 inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white"><Plus className="h-4 w-4" />Create Network</button>
        </div>
      ) : networks.length === 0 ? (
        <div className="rounded-2xl border border-border bg-surface/60 p-8 text-center text-sm text-muted">No Networks match this search.</div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
          {networks.map((network) => {
            const draftDefinition = network.draft_definition as { nodes?: unknown[] }
            const agentCount = Number((network as NetworkResource & { agent_count?: number }).agent_count ?? draftDefinition.nodes?.length ?? 0)
            return (
              <article key={network.id} className="group rounded-2xl border border-border bg-surface/65 p-5 transition hover:border-primary/35 hover:bg-surface">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-background/70 text-primary-light"><Network className="h-5 w-5" /></div>
                  <div className="min-w-0 flex-1">
                    <h2 className="truncate text-sm font-semibold text-white">{network.name}</h2>
                    <p className="mt-1 line-clamp-2 min-h-10 text-xs leading-5 text-muted">{network.description || 'No description configured.'}</p>
                  </div>
                  <button type="button" onClick={() => setEditing(network)} className="rounded-lg border border-transparent p-2 text-muted hover:border-border hover:bg-background hover:text-white" title="Edit Network metadata"><PencilLine className="h-4 w-4" /></button>
                </div>
                <div className="mt-5 grid grid-cols-3 gap-2 text-center">
                  <div className="rounded-xl border border-border bg-background/45 px-2 py-3"><p className="text-sm font-semibold text-white">{agentCount}</p><p className="mt-1 text-[9px] uppercase tracking-wider text-muted">Agents</p></div>
                  <div className="rounded-xl border border-border bg-background/45 px-2 py-3"><p className="truncate text-xs font-semibold text-white">{environmentLabel(network)}</p><p className="mt-1 text-[9px] uppercase tracking-wider text-muted">State</p></div>
                  <div className="rounded-xl border border-border bg-background/45 px-2 py-3"><p className="text-sm font-semibold text-white">r{network.draft_revision}</p><p className="mt-1 text-[9px] uppercase tracking-wider text-muted">Draft</p></div>
                </div>
                <button type="button" onClick={() => openNetwork(network.id)} className="mt-4 flex w-full items-center justify-between rounded-xl border border-border bg-background/45 px-3 py-2.5 text-xs font-medium text-slate-200 hover:border-primary/30 hover:text-white"><span className="inline-flex items-center gap-2"><Activity className="h-4 w-4 text-primary-light" />Open workspace</span><ArrowRight className="h-4 w-4" /></button>
              </article>
            )
          })}
        </div>
      )}

      {creating ? <NetworkModal title="Create Network" pending={createMutation.isPending} onClose={() => setCreating(false)} onSubmit={async (input) => {
        try {
          const created = await createMutation.mutateAsync(input)
          setCreating(false)
          openNetwork(created.id)
        } catch (error) {
          toast.error(error instanceof Error ? error.message : 'Unable to create Network')
        }
      }} /> : null}

      {editing ? <NetworkModal title="Edit Network" initialName={editing.name} initialDescription={editing.description} pending={updateMutation.isPending} onClose={() => setEditing(null)} onSubmit={async (input) => {
        try {
          await updateMutation.mutateAsync(input)
          setEditing(null)
          toast.success('Network metadata updated')
        } catch (error) {
          toast.error(error instanceof Error ? error.message : 'Unable to update Network')
        }
      }} /> : null}
    </div>
  )
}
