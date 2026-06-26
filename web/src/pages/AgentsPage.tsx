import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAgents, useCreateAgent } from '@/features/agents/hooks'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { ArrowRight, Bot, Plus, Search, ShieldCheck } from 'lucide-react'
import { orgProjectPath } from '@/lib/constants/routes'
import { toast } from 'sonner'
import type { Agent } from '@/features/agents/types'
import type { ProviderCredential } from '@/features/provider-credentials/types'

const defaultModels: Record<string, string> = {
  openai: 'gpt-4o-mini',
  anthropic: 'claude-3-5-haiku-latest',
  google: 'gemini-1.5-flash',
}

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google',
  custom: 'Custom',
}

function getCredentialModel(credential: ProviderCredential): string {
  return credential.metadata?.model || credential.metadata?.model_name || ''
}

function getCredentialBaseUrl(credential: ProviderCredential): string {
  return credential.metadata?.base_url || ''
}

function providerLabel(agent: Agent) {
  return [agent.provider, agent.model].filter(Boolean).join(' / ') || 'Model not configured'
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

function CredentialSummary({ credential }: { credential: ProviderCredential }) {
  const isCustom = credential.provider === 'custom'
  return (
    <div className="rounded-xl border border-border/80 bg-background/60 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">{credential.name}</p>
          <p className="mt-1 text-xs text-muted">{providerLabels[credential.provider] || credential.provider}</p>
        </div>
        <StatusBadge status={credential.status || 'active'} />
      </div>
      {isCustom && (
        <div className="mt-3 space-y-1 text-xs text-muted">
          <p>Model · <code className="rounded bg-surface px-1">{getCredentialModel(credential) || 'missing'}</code></p>
          <p>Base URL · <code className="rounded bg-surface px-1">{getCredentialBaseUrl(credential) || 'missing'}</code></p>
        </div>
      )}
    </div>
  )
}

export default function AgentsPage() {
  const { organizationId, projectId } = useParams<{ organizationId?: string; projectId: string }>()
  const navigate = useNavigate()
  const { data: agents, isLoading, isError, error, refetch } = useAgents(projectId)
  const createAgent = useCreateAgent(projectId)
  const { data: credentials = [], refetch: refetchCredentials } = useCredentials(projectId)
  const [query, setQuery] = useState('')
  const [showCreateAgent, setShowCreateAgent] = useState(false)
  const [showAddCredential, setShowAddCredential] = useState(false)
  const [selectedCredential, setSelectedCredential] = useState<ProviderCredential | null>(null)
  const [agentName, setAgentName] = useState('')
  const [agentDescription, setAgentDescription] = useState('')
  const pendingCredentialId = useRef<string | null>(null)

  const p = (projectId: string, ...segments: string[]) => orgProjectPath(organizationId, projectId, ...segments)
  const items = agents ?? []

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

  useEffect(() => {
    if (pendingCredentialId.current) {
      const match = credentials.find((credential) => credential.id === pendingCredentialId.current)
      if (match) {
        setSelectedCredential(match)
        pendingCredentialId.current = null
        return
      }
    }

    if (!selectedCredential) return
    const match = credentials.find((credential) => credential.id === selectedCredential.id)
    if (match) setSelectedCredential(match)
  }, [credentials, selectedCredential])

  const handleCredentialCreated = async (credentialId: string) => {
    setShowAddCredential(false)
    pendingCredentialId.current = credentialId
    await refetchCredentials()
  }

  const openCreateAgent = () => {
    setAgentName('')
    setAgentDescription('')
    setSelectedCredential(null)
    setShowCreateAgent(true)
  }

  const closeCreateAgent = () => {
    setShowCreateAgent(false)
    setShowAddCredential(false)
    setSelectedCredential(null)
    setAgentName('')
    setAgentDescription('')
    pendingCredentialId.current = null
  }

  const selectCredential = (credentialId: string) => {
    const credential = credentials.find((item) => item.id === credentialId)
    setSelectedCredential(credential || null)
  }

  const getDisabledReason = () => {
    if (!agentName.trim()) return 'Agent name is required.'
    if (!selectedCredential) return 'Select a provider credential.'
    if (!projectId) return 'Project ID is missing.'
    if (selectedCredential.provider === 'custom') {
      if (!getCredentialModel(selectedCredential)) return 'Custom credentials require a model name.'
      if (!getCredentialBaseUrl(selectedCredential)) return 'Custom credentials require a base URL.'
    }
    return null
  }

  const handleCreateAgent = async () => {
    const reason = getDisabledReason()
    if (reason) {
      toast.error(reason)
      return
    }
    if (!selectedCredential || !projectId) return

    const model = selectedCredential.provider === 'custom'
      ? getCredentialModel(selectedCredential)
      : defaultModels[selectedCredential.provider] || getCredentialModel(selectedCredential) || 'gpt-4o-mini'

    const settings: Record<string, unknown> = {}
    if (selectedCredential.provider === 'custom') {
      const baseUrl = getCredentialBaseUrl(selectedCredential)
      if (baseUrl) settings.base_url = baseUrl
    }

    try {
      const agent = await createAgent.mutateAsync({
        project_id: projectId,
        name: agentName.trim(),
        description: agentDescription.trim() || '',
        provider: selectedCredential.provider,
        model,
        system_prompt: '',
        temperature: 0.7,
        max_output_tokens: 2048,
        provider_credential_id: selectedCredential.id,
        session_mode: 'stateful',
        settings: Object.keys(settings).length > 0 ? settings : undefined,
      })
      toast.success('Agent created')
      closeCreateAgent()
      navigate(p(projectId, 'agents', agent.id, 'playground'))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create agent')
    }
  }

  if (isLoading) return <LoadingState />
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

        <CreateCard
          title="New agent"
          description="Create with name, description and credential"
          onClick={openCreateAgent}
        />
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
              <h3 className="text-sm font-semibold text-white">Model credential</h3>
              <p className="mt-1 text-xs leading-5 text-muted">Select the provider credential this agent will use at runtime.</p>
            </div>

            {selectedCredential ? (
              <div className="space-y-3">
                <CredentialSummary credential={selectedCredential} />
                <div className="flex flex-wrap gap-2">
                  <Button type="button" size="sm" variant="outline" onClick={() => setSelectedCredential(null)}>
                    Change credential
                  </Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setShowAddCredential(true)}>
                    Add another
                  </Button>
                </div>
              </div>
            ) : credentials.length > 0 ? (
              <div className="space-y-3">
                <Select
                  value=""
                  onChange={(event) => selectCredential(event.target.value)}
                  options={[
                    { value: '', label: 'Select a credential' },
                    ...credentials.map((credential) => ({
                      value: credential.id,
                      label: `${credential.name} (${providerLabels[credential.provider] || credential.provider})`,
                    })),
                  ]}
                />
                <Button type="button" size="sm" variant="outline" onClick={() => setShowAddCredential(true)}>
                  Add credential
                </Button>
              </div>
            ) : (
              <div className="rounded-xl border border-border/80 bg-background/60 p-4">
                <p className="text-sm text-muted">No provider credential available. Add a credential to connect this agent to a model provider.</p>
                <Button type="button" size="sm" variant="outline" className="mt-3" onClick={() => setShowAddCredential(true)}>
                  Add credential
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

      <AddProviderCredentialModal
        open={showAddCredential}
        onClose={() => setShowAddCredential(false)}
        projectId={projectId!}
        onCredentialCreated={handleCredentialCreated}
      />
    </MinimalShell>
  )
}
