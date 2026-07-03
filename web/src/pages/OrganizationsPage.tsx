import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { useCreateOrganization } from '@/features/organizations/hooks'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { CreateResourceCard } from '@/components/common/CreateResourceCard'
import { Input } from '@/components/ui/Input'
import { CreateOrganizationDialog } from '@/components/forms/CreateOrganizationDialog'
import { ArrowRight, Search } from 'lucide-react'
import { toast } from 'sonner'

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

  if (isLoadingOrganizations) return <LoadingState />
  if (workspaceError) return <ErrorState error={workspaceError} />

  const hasSearchMiss = query.trim().length > 0 && visibleOrganizations.length === 0

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6">
      <div className="space-y-5">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Select your organization</h1>
          <p className="mt-2 text-sm text-muted">Organizations group projects, members and runtime settings.</p>
        </div>

        <div className="relative max-w-3xl">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search organizations..."
            className="h-11 pl-9"
          />
        </div>
      </div>

      {hasSearchMiss && (
        <div className="rounded-xl border border-border/80 bg-surface/50 px-5 py-4">
          <h2 className="text-sm font-semibold text-white">No organizations found</h2>
          <p className="mt-1 text-sm text-muted">Create a new organization or adjust the search term.</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <CreateResourceCard
          title="New organization"
          description="Create a new organization"
          minHeight="lg"
          onClick={() => setShowCreate(true)}
        />

        {visibleOrganizations.map((org) => (
          <button
            key={org.id}
            type="button"
            aria-label={`Open projects for ${org.name}`}
            onClick={() => handleSelect(org)}
            className="group flex min-h-[260px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 text-left transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/35 hover:bg-surface/85 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-sm font-semibold text-primary-light shadow-sm transition-colors duration-200 group-hover:border-primary/30 group-hover:bg-primary/10">
              {getInitials(org.name)}
            </span>

            <span className="mt-6 block min-w-0">
              <span className="block truncate text-base font-semibold text-white">{org.name}</span>
              <span className="mt-1 block truncate font-mono text-sm text-muted">/{org.slug}</span>
            </span>

            <span className="my-5 block h-px bg-border/80" />

            <span className="block min-h-[48px] text-sm leading-6 text-muted">
              Projects, agents and settings linked to this organization.
            </span>

            <span className="mt-auto flex w-full items-center justify-between pt-5 text-sm font-medium text-primary-light transition-colors duration-200 group-hover:text-white">
              Open projects
              <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
            </span>
          </button>
        ))}
      </div>

      <CreateOrganizationDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={handleCreate}
        loading={createOrg.isPending}
      />
    </div>
  )
}
