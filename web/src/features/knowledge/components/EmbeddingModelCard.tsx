import { Cpu } from 'lucide-react'
import { StatusBadge } from '@/components/common/StatusBadge'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import type { ProviderModel } from '@/features/provider-models/types'

interface EmbeddingModelCardProps {
  model: ProviderModel
  credential?: ProviderCredential | null
  onClick: () => void
}

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  custom: 'OpenAI Compatible',
  openrouter: 'OpenRouter',
}

function providerLabel(value?: string | null) {
  return value ? providerLabels[value] || value : 'Unknown provider'
}

function dimensionsOf(model: ProviderModel) {
  const value = model.metadata?.dimensions
  return typeof value === 'number' ? value : 1536
}

export function EmbeddingModelCard({ model, credential, onClick }: EmbeddingModelCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Open embedding model ${model.name}`}
      className="group flex min-h-[240px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 text-left transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/35 hover:bg-surface/85 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <span className="flex items-start justify-between gap-3">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-primary-light shadow-sm transition-colors duration-200 group-hover:border-primary/30 group-hover:bg-primary/10">
          <Cpu className="h-5 w-5" />
        </span>
        <StatusBadge status={model.status || 'active'} />
      </span>

      <span className="mt-6 block min-w-0">
        <span className="block truncate text-base font-semibold text-white">{model.name}</span>
        <code className="mt-2 block truncate text-xs text-muted">{model.model}</code>
      </span>

      <span className="my-5 block h-px bg-border/80" />

      <span className="grid gap-2 text-xs text-muted">
        <span>{providerLabel(model.provider || credential?.provider)}</span>
        <span>{credential?.name || 'Credential unavailable'}</span>
        <span>{dimensionsOf(model).toLocaleString()} dimensions</span>
      </span>
    </button>
  )
}
