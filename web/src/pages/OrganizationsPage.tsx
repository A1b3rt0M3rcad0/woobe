import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { useCreateOrganization } from '@/features/organizations/hooks'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { CreateOrganizationDialog } from '@/components/forms/CreateOrganizationDialog'
import { ArrowRight, Plus, Search } from 'lucide-react'
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
        {visibleOrganizations.map((org) => (
          <Card
            key={org.id}
            className="group relative overflow-hidden border-border/90 bg-surface/70 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-surface hover:shadow-xl hover:shadow-primary/5"
          >
            <CardContent className="flex min-h-[260px] flex-col p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-sm font-semibold text-primary-light shadow-sm">
                {getInitials(org.name)}
              </div>

              <div className="mt-6">
                <h2 className="text-base font-semibold text-white">{org.name}</h2>
                <p className="mt-1 truncate font-mono text-sm text-muted">/{org.slug}</p>
              </div>

              <div className="my-5 h-px bg-border/80" />

              <p className="min-h-[48px] text-sm leading-6 text-muted">
                Projects, agents and settings linked to this organization.
              </p>

              <Button
                className="mt-auto w-full justify-between border-border/90 bg-background/40 text-primary-light hover:bg-primary/10 hover:text-primary-light"
                size="sm"
                variant="outline"
                onClick={() => handleSelect(org)}
              >
                Open projects
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </CardContent>
          </Card>
        ))}

        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="group flex min-h-[260px] flex-col items-center justify-center rounded-xl border border-dashed border-primary/40 bg-surface/35 p-6 text-center transition-all hover:-translate-y-0.5 hover:border-primary/70 hover:bg-primary/5 hover:shadow-xl hover:shadow-primary/5"
        >
          <span className="flex h-14 w-14 items-center justify-center rounded-full border border-primary/50 bg-primary/10 text-primary-light transition-colors group-hover:bg-primary/15">
            <Plus className="h-6 w-6" />
          </span>
          <span className="mt-5 text-base font-semibold text-white">New organization</span>
          <span className="mt-2 max-w-[180px] text-sm leading-6 text-muted">Create a new organization</span>
        </button>
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
