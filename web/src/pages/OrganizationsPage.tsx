import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, MailPlus, Plus } from 'lucide-react'
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
import { Card, CardContent } from '@/components/ui/Card'
import { CreateOrganizationDialog } from '@/components/forms/CreateOrganizationDialog'
import {
  useAcceptOrganizationInvite,
  useCreateOrganization,
  usePendingOrganizationInvites,
} from '@/features/organizations/hooks'
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
  const { data: pendingInvites = [], isLoading: isLoadingInvites } = usePendingOrganizationInvites()
  const acceptInvite = useAcceptOrganizationInvite()
  const navigate = useNavigate()
  const [showCreate, setShowCreate] = useState(false)
  const [query, setQuery] = useState('')
  const [acceptingInviteId, setAcceptingInviteId] = useState<string | null>(null)

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

  const handleAcceptInvite = async (inviteId: string) => {
    setAcceptingInviteId(inviteId)
    try {
      const org = await acceptInvite.mutateAsync(inviteId)
      toast.success(`Joined ${org.name}`)
      selectOrganization({ id: org.id, name: org.name, slug: org.slug })
      navigate(`/organizations/${org.id}/projects`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to accept invitation')
    } finally {
      setAcceptingInviteId(null)
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
      {(isLoadingInvites || pendingInvites.length > 0) && (
        <section>
          <ResourceSectionHeader
            title="Invitations"
            description="Accept an invitation to join an Organization. Project access is granted separately."
            count={pendingInvites.length}
          />
          {isLoadingInvites ? (
            <LoadingState message="Loading invitations" variant="panel" layout="compact-cards" />
          ) : (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {pendingInvites.map((invite) => (
                <Card key={invite.id}>
                  <CardContent className="flex items-center justify-between gap-4 p-4">
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface">
                        <MailPlus className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{invite.organization_name}</p>
                        <p className="truncate text-xs text-muted">
                          /{invite.organization_slug} · {invite.role}
                        </p>
                      </div>
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      loading={acceptingInviteId === invite.id}
                      disabled={acceptingInviteId !== null && acceptingInviteId !== invite.id}
                      onClick={() => handleAcceptInvite(invite.id)}
                    >
                      Accept and enter
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </section>
      )}

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
            description={pendingInvites.length > 0
              ? 'Accept an invitation above or create a new Organization.'
              : 'Organizations are the commercial workspace for Projects, members, plans and usage.'}
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
