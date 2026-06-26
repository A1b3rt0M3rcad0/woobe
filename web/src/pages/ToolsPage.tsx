import { useMemo, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { Plus, Search, Wrench } from 'lucide-react'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Input } from '@/components/ui/Input'
import { useTools } from '@/features/tools/hooks'
import type { Tool } from '@/features/tools/types'
import { ToolsCreateDialog } from '@/pages/ToolsCreateDialog'

function MinimalShell({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">{title}</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">{description}</p>
      </div>
      {children}
    </div>
  )
}

function CreateCard({ title, description, onClick }: { title: string; description: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex min-h-[240px] flex-col items-center justify-center rounded-xl border border-dashed border-primary/40 bg-surface/35 p-6 text-center transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/60 hover:bg-primary/5 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <span className="flex h-14 w-14 items-center justify-center rounded-full border border-primary/50 bg-primary/10 text-primary-light transition-colors duration-200 group-hover:bg-primary/15">
        <Plus className="h-6 w-6" />
      </span>
      <span className="mt-5 text-base font-semibold text-white">{title}</span>
      <span className="mt-2 max-w-[220px] text-sm leading-6 text-muted">{description}</span>
    </button>
  )
}

function NoResults() {
  return (
    <div className="rounded-xl border border-border/80 bg-surface/50 px-5 py-4">
      <h2 className="text-sm font-semibold text-white">No tools found</h2>
      <p className="mt-1 text-sm text-muted">Create a new tool or adjust the search term.</p>
    </div>
  )
}

export default function ToolsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: tools, isLoading, isError, error, refetch } = useTools(projectId)
  const [showCreate, setShowCreate] = useState(false)
  const [query, setQuery] = useState('')

  const items = tools ?? []
  const visibleTools = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return items

    return items.filter((tool) => (
      tool.name.toLowerCase().includes(normalizedQuery)
      || tool.description?.toLowerCase().includes(normalizedQuery)
      || String(tool.type).toLowerCase().includes(normalizedQuery)
      || tool.status?.toLowerCase().includes(normalizedQuery)
      || tool.risk_level?.toLowerCase().includes(normalizedQuery)
    ))
  }, [items, query])

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const hasSearchMiss = query.trim().length > 0 && visibleTools.length === 0

  return (
    <MinimalShell
      title="Tools"
      description="Connect and review external capabilities available to agents in this project."
    >
      <div className="relative max-w-3xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search tools..."
          className="h-11 pl-9"
        />
      </div>

      {hasSearchMiss && <NoResults />}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {visibleTools.map((tool: Tool) => (
          <article
            key={tool.id}
            className="flex min-h-[240px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/35 hover:bg-surface/85 hover:shadow-lg hover:shadow-primary/5"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-primary-light shadow-sm">
                <Wrench className="h-5 w-5" />
              </div>
              <StatusBadge status={tool.status} />
            </div>

            <div className="mt-6 min-w-0">
              <h2 className="truncate text-base font-semibold text-white">{tool.name}</h2>
              <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted">{tool.description || tool.type}</p>
            </div>

            <div className="my-5 h-px bg-border/80" />

            <div className="mt-auto flex flex-wrap gap-2 text-xs text-muted">
              <span className="rounded-full border border-border/80 bg-background/70 px-2.5 py-1">{String(tool.type)}</span>
              {tool.risk_level && <span className="rounded-full border border-border/80 bg-background/70 px-2.5 py-1">Risk · {tool.risk_level}</span>}
            </div>
          </article>
        ))}

        <CreateCard
          title="New tool"
          description="Connect an external capability"
          onClick={() => setShowCreate(true)}
        />
      </div>

      <ToolsCreateDialog open={showCreate} projectId={projectId!} onClose={() => setShowCreate(false)} />
    </MinimalShell>
  )
}
