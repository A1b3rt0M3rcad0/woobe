import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Network, PencilLine, Plus } from 'lucide-react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourceCard } from '@/components/common/OperationalResourceCard'
import { RuntimeEnvironmentPill } from '@/components/common/RuntimeEnvironmentPill'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSearch,
  ResourceSectionHeader,
  ResourceTabs,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { useCreateNetwork, useNetworkRuntimeEnvironments, useNetworks, useUpdateNetworkMetadata } from '@/features/network/hooks'
import type { NetworkResource } from '@/features/network/types'

type NetworkMaturityFilter = 'all' | 'draft' | 'staging' | 'production'

function networkMaturity(network: NetworkResource): Exclude<NetworkMaturityFilter, 'all'> {
  if (network.production_version_id) return 'production'
  if (network.staging_version_id) return 'staging'
  return 'draft'
}

function networkAgentCount(network: NetworkResource) {
  const draftDefinition = network.draft_definition as { nodes?: unknown[] }
  return Number(network.agent_count ?? draftDefinition.nodes?.length ?? 0)
}

function networkDelegationCount(network: NetworkResource) {
  const draftDefinition = network.draft_definition as { edges?: unknown[] }
  return Number(draftDefinition.edges?.length ?? 0)
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Not recorded'
}

function NetworkOperationalCard({
  network,
  projectId,
  onOpen,
  onEdit,
}: {
  network: NetworkResource
  projectId: string
  onOpen: () => void
  onEdit: () => void
}) {
  const runtimeQuery = useNetworkRuntimeEnvironments(network.id, projectId)
  const runtimeStates = runtimeQuery.data
  const runtimeUnknown = runtimeQuery.isError && !runtimeStates
  const agentCount = networkAgentCount(network)
  const delegationCount = networkDelegationCount(network)
  const hasStaging = Boolean(network.staging_version_id)
  const hasProduction = Boolean(network.production_version_id)

  return (
    <div className="relative h-full">
      <ResourceCard
        aria-label={`Open Network workspace for ${network.name}`}
        onClick={onOpen}
        icon={<Network className="h-4 w-4" />}
        title={network.name}
        subtitle={network.description || 'No description configured.'}
        metadata={(
          <>
            <RuntimeEnvironmentPill
              environment="draft"
              enabled={runtimeStates?.draft.enabled}
              loading={runtimeQuery.isLoading && !runtimeStates}
              unknown={runtimeUnknown}
            />
            <RuntimeEnvironmentPill
              environment="staging"
              enabled={runtimeStates?.staging.enabled}
              available={hasStaging}
              loading={runtimeQuery.isLoading && !runtimeStates}
              unknown={runtimeUnknown}
            />
            <RuntimeEnvironmentPill
              environment="production"
              enabled={runtimeStates?.production.enabled}
              available={hasProduction}
              loading={runtimeQuery.isLoading && !runtimeStates}
              unknown={runtimeUnknown}
            />
          </>
        )}
        footer={(
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1 pr-8">
            <span>{agentCount} {agentCount === 1 ? 'Agent' : 'Agents'}</span>
            <span aria-hidden="true">·</span>
            <span>{delegationCount} {delegationCount === 1 ? 'delegation' : 'delegations'}</span>
            <span aria-hidden="true">·</span>
            <span>{network.draft_revision > 0 ? `Draft r${network.draft_revision}` : 'Draft setup'}</span>
            <span aria-hidden="true">·</span>
            <span>Updated · {formatDate(network.updated_at || network.created_at)}</span>
          </span>
        )}
        className="h-full w-full pr-12"
      />
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="absolute bottom-2 right-2 h-7 w-7 text-muted hover:text-white"
        onClick={onEdit}
        aria-label={`Edit Network ${network.name}`}
        title="Edit Network metadata"
      >
        <PencilLine className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
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
    <Dialog open onClose={onClose} title={title}>
      <form onSubmit={(event) => void submit(event)} className="space-y-5">
        <label className="block" htmlFor="network-name">
          <span className="text-xs font-medium text-slate-200">Name</span>
          <Input
            id="network-name"
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={255}
            className="mt-2"
            placeholder="Customer Support"
          />
        </label>

        <label className="block" htmlFor="network-description">
          <span className="text-xs font-medium text-slate-200">Description</span>
          <textarea
            id="network-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            maxLength={4000}
            rows={4}
            className="mt-2 w-full resize-none rounded-lg border border-border bg-transparent px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
            placeholder="Operational purpose of this Network"
          />
        </label>

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={pending}>Save Network</Button>
        </div>
      </form>
    </Dialog>
  )
}

export default function NetworksPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>()
  const navigate = useNavigate()
  const networksQuery = useNetworks(projectId)
  const createMutation = useCreateNetwork(projectId)
  const [query, setQuery] = useState('')
  const [maturityFilter, setMaturityFilter] = useState<NetworkMaturityFilter>('all')
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<NetworkResource | null>(null)
  const updateMutation = useUpdateNetworkMetadata(projectId, editing?.id)

  const items = networksQuery.data ?? []

  const maturityCounts = useMemo(() => ({
    all: items.length,
    draft: items.filter((network) => networkMaturity(network) === 'draft').length,
    staging: items.filter((network) => networkMaturity(network) === 'staging').length,
    production: items.filter((network) => networkMaturity(network) === 'production').length,
  }), [items])

  const visibleNetworks = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return items.filter((network) => {
      const matchesMaturity = maturityFilter === 'all' || networkMaturity(network) === maturityFilter
      const matchesQuery = !normalizedQuery || [
        network.name,
        network.description,
        `draft r${network.draft_revision}`,
        networkMaturity(network),
      ].some((value) => value.toLowerCase().includes(normalizedQuery))
      return matchesMaturity && matchesQuery
    })
  }, [items, maturityFilter, query])

  if (!workspaceId || !projectId) return <ErrorState message="Project not found" />

  const hasFilters = Boolean(query.trim()) || maturityFilter !== 'all'
  const resultCount = hasFilters ? `${visibleNetworks.length} of ${items.length}` : items.length

  const openNetwork = (networkId: string) => {
    navigate(`/workspaces/${workspaceId}/projects/${projectId}/networks/${networkId}`)
  }

  const clearFilters = () => {
    setQuery('')
    setMaturityFilter('all')
  }

  return (
    <ResourcePage
      title="Networks"
      description="Create and operate versioned Agent compositions for this Project."
      action={(
        <Button type="button" onClick={() => setCreating(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Network
        </Button>
      )}
    >
      <ResourceToolbar>
        <ResourceTabs
          value={maturityFilter}
          onChange={setMaturityFilter}
          label="Filter Networks by environment maturity"
          tabs={[
            { value: 'all', label: 'All', count: maturityCounts.all },
            { value: 'draft', label: 'Draft', count: maturityCounts.draft },
            { value: 'staging', label: 'Staging', count: maturityCounts.staging },
            { value: 'production', label: 'Production', count: maturityCounts.production },
          ]}
        />
        <ResourceSearch
          value={query}
          onChange={setQuery}
          placeholder="Search Networks..."
          label="Search Networks"
        />
      </ResourceToolbar>

      <section>
        <ResourceSectionHeader
          title="Networks"
          description="Open a Network to configure its Agents, environments and releases."
          count={resultCount}
        />

        {networksQuery.isLoading ? (
          <LoadingState message="Loading Networks" variant="panel" layout="compact-cards" />
        ) : networksQuery.isError ? (
          <ErrorState
            error={networksQuery.error}
            onRetry={networksQuery.refetch}
            className="rounded-xl border border-border/80 bg-surface/40 py-10"
          />
        ) : visibleNetworks.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {visibleNetworks.map((network) => (
              <NetworkOperationalCard
                key={network.id}
                network={network}
                projectId={projectId}
                onOpen={() => openNetwork(network.id)}
                onEdit={() => setEditing(network)}
              />
            ))}
          </div>
        ) : (
          <ResourceEmptyState
            icon={<Network className="h-4 w-4" />}
            title={items.length === 0 ? 'Create your first Network' : 'No Networks found'}
            description={items.length === 0
              ? 'Create a Network, then configure its entry Agent and composition.'
              : 'Adjust the search or clear the active maturity filter.'}
            action={items.length === 0 ? (
              <Button type="button" size="sm" onClick={() => setCreating(true)}>
                Create Network
              </Button>
            ) : hasFilters ? (
              <Button type="button" size="sm" variant="outline" onClick={clearFilters}>
                Clear filters
              </Button>
            ) : undefined}
          />
        )}
      </section>

      {creating ? (
        <NetworkModal
          title="Create Network"
          pending={createMutation.isPending}
          onClose={() => setCreating(false)}
          onSubmit={async (input) => {
            try {
              const created = await createMutation.mutateAsync(input)
              setCreating(false)
              openNetwork(created.id)
            } catch (error) {
              toast.error(error instanceof Error ? error.message : 'Unable to create Network')
            }
          }}
        />
      ) : null}

      {editing ? (
        <NetworkModal
          title="Edit Network"
          initialName={editing.name}
          initialDescription={editing.description}
          pending={updateMutation.isPending}
          onClose={() => setEditing(null)}
          onSubmit={async (input) => {
            try {
              await updateMutation.mutateAsync(input)
              setEditing(null)
              toast.success('Network metadata updated')
            } catch (error) {
              toast.error(error instanceof Error ? error.message : 'Unable to update Network')
            }
          }}
        />
      ) : null}
    </ResourcePage>
  )
}
