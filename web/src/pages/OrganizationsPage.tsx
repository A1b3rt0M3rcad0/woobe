import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, Plus } from 'lucide-react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourceCard } from '@/components/common/OperationalResourceCard'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSearch,
  ResourceSectionHeader,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { Button } from '@/components/ui/Button'
import { CreateOrganizationDialog } from '@/components/forms/CreateOrganizationDialog'
import { useCreateOrganization } from '@/features/organizations/hooks'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'

const SEARCH_THRESHOLD = 5

function getInitials(name: string) {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'OR'
}

export default function OrganizationsPage() {
  const { organizations, selectOrganization, isLoadingOrganizations, workspaceError } = useWorkspace()
  const createOrg = useCreateOrganization()
  const navigate = useNavigate()
  const [showCreate, setShowCreate] = useState(false)
  const [query, setQuery] = useState('')

  const visibleOrganizations = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return organizations

    return organizations.filter((org) => (
      org.name.toLowerCase().includes(normalizedQuery)
      || org.slug.toLowerCase().includes(normalizedQuery)
    ))
  }, [organizations, query])

  const handleCreate = async (data: { name: string; slug: string }) => {
    try {
      const org = await createOrg.mutateAsync(data)
      toast.success('Organization created')
      setShowCreate(false)
      selectOrganization({ id: org.id, name: org.name, slug: org.slug })
      navigate(`/organizations/${org.id}/projects`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create organization')
    }
  }

  const handleSelect = (org: { id: string; name: string; slug: string }) => {
    selectOrganization(org)
    navigate(`/organizations/${org.id}/projects`)
  }

  const showSearch = organizations.length >= SEARCH_THRESHOLD
  const hasSearchMiss = Boolean(query.trim()) && visibleOrganizations.length === 0
  const resultCount = query.trim() ? `${visibleOrganizations.length} of ${organizations.length}` : organizations.length

  return (
    <ResourcePage
      title="Organizations"
      description="Select the commercial workspace you want to operate."
      action={(
        <Button type="button" onClick={() => setShowCreate(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Organization
        </Button>
      )}
    >
      {showSearch && (
        <ResourceToolbar>
          <ResourceSearch
            value={query}
            onChange={setQuery}
            placeholder="Search Organizations..."
            label="Search Organizations"
          />
        </ResourceToolbar>
      )}

      <section>
        <ResourceSectionHeader
          title="Organizations"
          description="Organizations own Projects, members, plans and usage."
          count={resultCount}
        />

        {isLoadingOrganizations ? (
          <LoadingState message="Loading Organizations" variant="panel" layout="compact-cards" />
        ) : workspaceError ? (
          <ErrorState error={workspaceError} className="rounded-xl border border-border/80 bg-surface/40 py-10" />
        ) : organizations.length === 0 ? (
          <ResourceEmptyState
            icon={<Building2 className="h-4 w-4" />}
            title="Create your first Organization"
            description="Organizations are the commercial workspace for Projects, members, plans and usage."
            action={(
              <Button type="button" size="sm" onClick={() => setShowCreate(true)}>
                Create Organization
              </Button>
            )}
          />
        ) : hasSearchMiss ? (
          <ResourceEmptyState
            icon={<Building2 className="h-4 w-4" />}
            title="No Organizations found"
            description="Adjust your search or clear the current term."
            action={(
              <Button type="button" size="sm" variant="outline" onClick={() => setQuery('')}>
                Clear search
              </Button>
            )}
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {visibleOrganizations.map((org) => (
              <ResourceCard
                key={org.id}
                aria-label={`Open Projects for ${org.name}`}
                onClick={() => handleSelect(org)}
                icon={<span className="text-xs font-semibold">{getInitials(org.name)}</span>}
                title={org.name}
                subtitle={`/${org.slug}`}
                footer="Open Projects"
              />
            ))}
          </div>
        )}
      </section>

      <CreateOrganizationDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={handleCreate}
        loading={createOrg.isPending}
      />
    </ResourcePage>
  )
}
