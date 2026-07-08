import { useMemo, useState } from 'react'
import { Key, Plus, Search } from 'lucide-react'
import { CreateResourceCard } from '@/components/common/CreateResourceCard'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import { useCredentials } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { useProviderModels } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'
import { CreateEmbeddingModelModal } from '@/features/knowledge/components/CreateEmbeddingModelModal'
import { EmbeddingModelCard } from '@/features/knowledge/components/EmbeddingModelCard'

interface KnowledgeEmbeddingPanelProps { projectId: string }
type Section = 'models' | 'credentials'

function isEmbeddingModel(model: ProviderModel) {
  const metadata = model.metadata || {}
  const capability = String(metadata.capability || metadata.type || '').toLowerCase()
  return capability === 'embedding' || capability === 'embeddings' || model.model.toLowerCase().includes('embed')
}

function SectionButton({ active, children, onClick }: { active: boolean; children: string; onClick: () => void }) {
  return <button type="button" onClick={onClick} className={`rounded-lg border px-4 py-2 text-sm transition-colors ${active ? 'border-primary/40 bg-primary/10 text-primary-light' : 'border-border bg-surface/50 text-muted hover:text-white'}`}>{children}</button>
}

function CredentialCard({ credential, modelCount, onClick }: { credential: ProviderCredential; modelCount: number; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="group flex min-h-[220px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 text-left transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/35 hover:bg-surface/85 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background">
      <span className="flex items-start justify-between gap-3"><span className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-primary-light shadow-sm"><Key className="h-5 w-5" /></span><StatusBadge status={credential.status || 'active'} /></span>
      <span className="mt-6 block truncate text-base font-semibold text-white">{credential.name}</span>
      <span className="mt-2 block truncate text-xs text-muted">{credential.provider}</span>
      <span className="my-5 block h-px bg-border/80" />
      <span className="text-xs text-muted">{modelCount} embedding {modelCount === 1 ? 'model' : 'models'}</span>
    </button>
  )
}

export function KnowledgeEmbeddingPanel({ projectId }: KnowledgeEmbeddingPanelProps) {
  const credentialsQuery = useCredentials(projectId)
  const modelsQuery = useProviderModels(projectId)
  const credentials = credentialsQuery.data ?? []
  const models = modelsQuery.data ?? []
  const [section, setSection] = useState<Section>('models')
  const [query, setQuery] = useState('')
  const [modelModalOpen, setModelModalOpen] = useState(false)
  const [credentialModalOpen, setCredentialModalOpen] = useState(false)
  const [selectedModel, setSelectedModel] = useState<ProviderModel | null>(null)
  const [selectedCredential, setSelectedCredential] = useState<ProviderCredential | null>(null)

  const embeddingModels = useMemo(() => models.filter((model) => isEmbeddingModel(model) && model.status !== 'archived'), [models])
  const normalizedQuery = query.trim().toLowerCase()
  const visibleModels = useMemo(() => !normalizedQuery ? embeddingModels : embeddingModels.filter((model) => `${model.name} ${model.model} ${model.provider || ''}`.toLowerCase().includes(normalizedQuery)), [embeddingModels, normalizedQuery])
  const visibleCredentials = useMemo(() => !normalizedQuery ? credentials : credentials.filter((credential) => `${credential.name} ${credential.provider}`.toLowerCase().includes(normalizedQuery)), [credentials, normalizedQuery])

  const openNewModel = () => { setSelectedModel(null); setModelModalOpen(true) }
  const openNewCredential = () => { setSelectedCredential(null); setCredentialModalOpen(true) }

  if (credentialsQuery.isLoading || modelsQuery.isLoading) return <LoadingState />
  if (credentialsQuery.isError || modelsQuery.isError) return <ErrorState onRetry={() => { void credentialsQuery.refetch(); void modelsQuery.refetch() }} />

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"><div className="flex flex-wrap gap-2"><SectionButton active={section === 'models'} onClick={() => { setSection('models'); setQuery('') }}>Embedding models</SectionButton><SectionButton active={section === 'credentials'} onClick={() => { setSection('credentials'); setQuery('') }}>Credentials</SectionButton></div><Button type="button" onClick={section === 'models' ? openNewModel : openNewCredential}><Plus className="mr-2 h-4 w-4" />{section === 'models' ? 'Add embedding model' : 'Add credential'}</Button></div>
      <div className="relative max-w-3xl"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={section === 'models' ? 'Search embedding models...' : 'Search credentials...'} className="h-11 pl-9" /></div>

      {section === 'models' ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"><CreateResourceCard title="Add embedding model" description="Create a reusable embedding model from a provider credential" minHeight="sm" onClick={openNewModel} />{visibleModels.map((model) => <EmbeddingModelCard key={model.id} model={model} credential={credentials.find((credential) => credential.id === model.provider_credential_id)} onClick={() => { setSelectedModel(model); setModelModalOpen(true) }} />)}{visibleModels.length === 0 && <div className="flex min-h-[220px] flex-col rounded-xl border border-border/80 bg-surface/50 p-6"><p className="text-base font-semibold text-white">No embedding models found</p><p className="mt-2 text-sm leading-6 text-muted">{credentials.length > 0 ? 'Add an embedding model using one of the project credentials.' : 'Add a provider credential first, then create an embedding model.'}</p>{credentials.length === 0 && <Button type="button" size="sm" variant="outline" className="mt-5 self-start" onClick={openNewCredential}><Key className="mr-2 h-4 w-4" />Add credential</Button>}</div>}</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"><CreateResourceCard title="Add credential" description="Connect the provider account used to generate embeddings" minHeight="sm" onClick={openNewCredential} />{visibleCredentials.map((credential) => <CredentialCard key={credential.id} credential={credential} modelCount={embeddingModels.filter((model) => model.provider_credential_id === credential.id).length} onClick={() => { setSelectedCredential(credential); setCredentialModalOpen(true) }} />)}{visibleCredentials.length === 0 && <div className="flex min-h-[220px] flex-col rounded-xl border border-border/80 bg-surface/50 p-6"><p className="text-base font-semibold text-white">No credentials found</p><p className="mt-2 text-sm leading-6 text-muted">Add a BYOK provider credential to create embedding models.</p></div>}</div>
      )}

      <CreateEmbeddingModelModal open={modelModalOpen} projectId={projectId} model={selectedModel} onClose={() => { setModelModalOpen(false); setSelectedModel(null) }} onCreated={() => { setModelModalOpen(false); setSelectedModel(null) }} />
      <AddProviderCredentialModal open={credentialModalOpen} onClose={() => { setCredentialModalOpen(false); setSelectedCredential(null) }} projectId={projectId} credential={selectedCredential} onCredentialCreated={() => { setCredentialModalOpen(false); setSelectedCredential(null) }} />
    </div>
  )
}
