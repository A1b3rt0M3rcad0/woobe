import { useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAgents, useCreateAgent } from '@/features/agents/hooks'
import { useProviderModels } from '@/features/provider-models/hooks'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { ArrowRight, Bot, Boxes, Plus, Search, ShieldCheck } from 'lucide-react'
import { orgProjectPath } from '@/lib/constants/routes'
import { toast } from 'sonner'
import type { Agent } from '@/features/agents/types'
import type { ProviderModel } from '@/features/provider-models/types'

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  openrouter: 'OpenRouter',
  anthropic: 'Anthropic',
  google: 'Google',
  custom: 'Custom',
}

function providerLabel(agent: Agent) {
  return [agent.provider, agent.model].filter(Boolean).join(' / ') || 'Model not configured'
}

function modelProviderLabel(model: ProviderModel) {
  const provider = model.provider || ''
  return providerLabels[provider] || provider || 'Provider'
}

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

function ModelSummary({ model }: { model: ProviderModel }) {
  return (
    <div className="rounded-xl border border-border/80 bg-background/60 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">{model.name}</p>
          <p className="mt-1 text-xs text-muted">{modelProviderLabel(model)}</p>
        </div>
        <StatusBadge status={model.status || 'active'} />
      </div>
      <div className="mt-3 space-y-1 text-xs text-muted">
        <p>Model · <code className="rounded bg-surface px-1">{model.model}</code></p>
      </div>
    </div>
  )
}

export default function AgentsPage() {
  const { organizationId, projectId } = useParams<{ organizationId?: string; projectId: string }>()
  const navigate = useNavigate()
  const { data: agents, isLoading, isError, error, refetch } = useAgents(projectId)
  const createAgent = useCreateAgent(projectId)
  const { data: providerModels = [], isLoading: modelsLoading } = useProviderModels(projectId)
  const [query, setQuery] = useState('')
  const [showCreateAgent, setShowCreateAgent] = useState(false)
  const [agentName, setAgentName] = useState('')
  const [agentDescription, setAgentDescription] = useState('')
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null)

  const p = (projectId: string, ...segments: string[]) => orgProjectPath(organizationId, projectId, ...segments)
  const items = agents ?? []
  const activeModels = providerModels.filter((model) => model.status !== 'archived')
  const selectedModel = activeModels.find((model) => model.id === selectedModelId) || null

  const visibleAgents = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return items

    return items.filter((agent) => (
      agent.name.toLowerCase().includes(normalizedQuery)
      || agent.provider?.toLowerCase().includes(normalizedQuery)
      || agent.model?.toLowerCase().includes(normalizedQuery)
      || agent.status?.toLowerCase().includes(normalizedQuery)
    ))
  }, [items, query])

  const openCreateAgent = () => {
    setAgentName('')
    setAgentDescription('')
    setSelectedModelId(null)
    setShowCreateAgent(true)
  }

  const closeCreateAgent = () => {
    setShowCreateAgent(false)
    setSelectedModelId(null)
    setAgentName('')
    setAgentDescription('')
  }

  const getDisabledReason = () => {
    if (!agentName.trim()) return 'Agent name is required.'
    if (!selectedModel) return 'Select a reusable model.'
    if (!projectId) return 'Project ID is missing.'
    return null
  }

  const handleCreateAgent = async () => {
    const reason = getDisabledReason()
    if (reason) {
      toast.error(reason)
      return
    }
    if (!selectedModel || !projectId) return

    try {
      const agent = await createAgent.mutateAsync({
        project_id: projectId,
        name: agentName.trim(),
        description: agentDescription.trim() || '',
        provider_model_id: selectedModel.id,
        provider: selectedModel.provider || 'openai',
        model: selectedModel.model,
        system_prompt: '',
        temperature: 0.7,
        max_output_tokens: 2048,
        provider_credential_id: selectedModel.provider_credential_id,
        session_mode: 'stateful',
      })
      toast.success('Agent created')
      closeCreateAgent()
      navigate(p(projectId, 'agents', agent.id, 'playground'))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create agent')
    }
  }

  if (isLoading || modelsLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const hasSearchMiss = query.trim().length > 0 && visibleAgents.length === 0
  const disabledReason = getDisabledReason()

  return (
    <MinimalShell
      title="Agents"
      description="Create and operate model-backed agents for this project."
    >
      <div className="relative max-w-3xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search agents..."
          className="h-11 pl-9"
        />
      </div>

      {hasSearchMiss && (
        <div className="rounded-xl border border-border/80 bg-surface/50 px-5 py-4">
          <h2 className="text-sm font-semibold text-white">No agents found</h2>
          <p className="mt-1 text-sm text-muted">Create a new agent or adjust the search term.</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <CreateCard
          title="New agent"
          description="Create with name, description and reusable model"
          onClick={openCreateAgent}
        />

        {visibleAgents.map((agent: Agent) => (
          <button
            key={agent.id}
            type="button"
            aria-label={`Open agent playground for ${agent.name}`}
            onClick={() => navigate(p(projectId!, 'agents', agent.id, 'playground'))}
            className="group flex min-h-[240px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 text-left transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/35 hover:bg-surface/85 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <span className="flex items-start justify-between gap-3">
              <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-primary-light shadow-sm transition-colors duration-200 group-hover:border-primary/30 group-hover:bg-primary/10">
                <Bot className="h-5 w-5" />
              </span>
              <StatusBadge status={agent.status} />
            </span>

            <span className="mt-6 block min-w-0">
              <span className="block truncate text-base font-semibold text-white">{agent.name}</span>
              <span className="mt-1 block truncate text-sm text-muted">{providerLabel(agent)}</span>
            </span>

            <span className="my-5 block h-px bg-border/80" />

            <span className="block min-h-[48px] text-sm leading-6 text-muted">
              Open the playground to test, edit and iterate on this agent.
            </span>

            <span className="mt-auto flex w-full items-center justify-between pt-5 text-sm font-medium text-primary-light transition-colors duration-200 group-hover:text-white">
              Open playground
              <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
            </span>
          </button>
        ))}
      </div>

      <Dialog open={showCreateAgent} onClose={closeCreateAgent} title="Create agent" className="max-w-2xl">
        <div className="space-y-5">
          <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-white">Agent details</h3>
              <p className="mt-1 text-xs leading-5 text-muted">Start with the minimum required setup. You can refine prompt, tools and knowledge in the playground.</p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <Input
                value={agentName}
                onChange={(event) => setAgentName(event.target.value)}
                placeholder="Agent name"
              />
              <Input
                value={agentDescription}
                onChange={(event) => setAgentDescription(event.target.value)}
                placeholder="Description (optional)"
              />
            </div>
          </section>

          <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-white">Model</h3>
              <p className="mt-1 text-xs leading-5 text-muted">Select a reusable model from the Models page. Runtime settings can be changed after creation.</p>
            </div>

            {selectedModel ? (
              <div className="space-y-3">
                <ModelSummary model={selectedModel} />
                <Button type="button" size="sm" variant="outline" onClick={() => setSelectedModelId(null)}>
                  Change model
                </Button>
              </div>
            ) : activeModels.length > 0 ? (
              <Select
                value=""
                onChange={(event) => setSelectedModelId(event.target.value)}
                options={[
                  { value: '', label: 'Select a model' },
                  ...activeModels.map((model) => ({
                    value: model.id,
                    label: `${model.name} · ${model.model} (${modelProviderLabel(model)})`,
                  })),
                ]}
              />
            ) : (
              <div className="rounded-xl border border-border/80 bg-background/60 p-4">
                <p className="text-sm text-muted">No reusable model available. Create one in the Models page first.</p>
                <Button type="button" size="sm" variant="outline" className="mt-3" onClick={() => navigate(p(projectId!, 'models'))}>
                  <Boxes className="mr-2 h-4 w-4" />
                  Open Models
                </Button>
              </div>
            )}
          </section>

          {disabledReason && (
            <p className="text-right text-xs text-muted">{disabledReason}</p>
          )}

          <div className="flex justify-end gap-2 border-t border-border pt-4">
            <Button type="button" variant="outline" onClick={closeCreateAgent}>Cancel</Button>
            <Button type="button" onClick={handleCreateAgent} loading={createAgent.isPending} disabled={Boolean(disabledReason)}>
              <ShieldCheck className="mr-2 h-4 w-4" />
              Create agent
            </Button>
          </div>
        </div>
      </Dialog>
    </MinimalShell>
  )
}
