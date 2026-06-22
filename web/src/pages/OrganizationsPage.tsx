import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { useCreateOrganization } from '@/features/organizations/hooks'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { CreateOrganizationDialog } from '@/components/forms/CreateOrganizationDialog'
import { ArrowRight, Building2, CheckCircle2, Plus, Search, Settings, ShieldCheck } from 'lucide-react'
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
  const { organizations, currentOrganization, selectOrganization, isLoadingOrganizations, workspaceError } = useWorkspace()
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

  const hasOrganizations = organizations.length > 0

  return (
    <div className="space-y-6">
      <PageHeader
        title="Select your organization"
        description={
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
            <span>Organizations help you group projects, members and settings.</span>
            {currentOrganization && (
              <span className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary-light">
                <CheckCircle2 className="h-3 w-3" />
                {currentOrganization.name} selected
              </span>
            )}
          </div>
        }
        actions={
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="mr-2 h-4 w-4" />
            New organization
          </Button>
        }
      />

      {!hasOrganizations ? (
        <EmptyState
          icon={<Building2 className="h-12 w-12" />}
          title="No organizations yet"
          description="Create an organization to start building projects and invite your team."
          action={
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create organization
            </Button>
          }
        />
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
            <Card className="overflow-hidden border-border/80 bg-surface/80">
              <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary-light">Workspace control</p>
                  <h2 className="mt-2 text-lg font-semibold text-white">Available organizations</h2>
                  <p className="mt-1 text-sm text-muted">
                    You have {organizations.length} {organizations.length === 1 ? 'organization' : 'organizations'}.
                  </p>
                </div>
                <div className="relative w-full sm:max-w-xs">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
                  <Input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search organizations..."
                    className="pl-9"
                  />
                </div>
              </CardContent>
            </Card>

            <Card className="border-primary/20 bg-primary/10">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/30 bg-background text-primary-light">
                    <ShieldCheck className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-xs text-muted">Current context</p>
                    <p className="text-sm font-semibold text-white">{currentOrganization?.name || 'None selected'}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {visibleOrganizations.length === 0 ? (
            <Card className="border-dashed border-border bg-surface/60">
              <CardContent className="flex flex-col items-center justify-center px-6 py-12 text-center">
                <Search className="h-10 w-10 text-muted" />
                <h3 className="mt-4 text-base font-semibold text-white">No organizations found</h3>
                <p className="mt-1 max-w-md text-sm text-muted">Adjust the search term or create a new organization.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {visibleOrganizations.map((org) => {
                const isSelected = org.id === currentOrganization?.id

                return (
                  <Card
                    key={org.id}
                    className={`group relative overflow-hidden transition-all hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5 ${isSelected ? 'border-primary/60 bg-primary/10 ring-1 ring-primary/30' : 'border-border bg-surface'}`}
                  >
                    <CardHeader className="pb-4">
                      <div className="mb-4 flex items-start justify-between gap-3">
                        <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-background text-sm font-semibold text-primary-light shadow-sm">
                          {getInitials(org.name)}
                        </div>
                        <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${isSelected ? 'border-primary/40 bg-primary/20 text-primary-light' : 'border-border bg-background text-muted'}`}>
                          {isSelected && <CheckCircle2 className="h-3 w-3" />}
                          {isSelected ? 'Selected' : 'Available'}
                        </span>
                      </div>

                      <CardTitle className="flex items-center gap-2 text-white">
                        <Building2 className="h-4 w-4 text-primary" />
                        {org.name}
                      </CardTitle>
                      <CardDescription className="font-mono">/{org.slug}</CardDescription>
                    </CardHeader>

                    <CardContent className="space-y-4">
                      <div className="rounded-lg border border-border/70 bg-background/70 p-3">
                        <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted">Access</p>
                        <p className="mt-1 text-sm text-muted-foreground">Projects, agents and settings linked to this organization.</p>
                      </div>

                      <div className="flex flex-col gap-2 sm:flex-row">
                        <Button className="flex-1" size="sm" variant={isSelected ? 'default' : 'outline'} onClick={() => handleSelect(org)}>
                          {isSelected ? 'Open projects' : 'Select'}
                          <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => navigate(`/organizations/${org.id}/settings`)}>
                          <Settings className="mr-1.5 h-3.5 w-3.5" />
                          Settings
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          )}
        </>
      )}

      <CreateOrganizationDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={handleCreate}
        loading={createOrg.isPending}
      />
    </div>
  )
}
