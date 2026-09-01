import { Cpu } from 'lucide-react'

import { ResourceCard, ResourcePill } from '@/components/common/OperationalResourceCard'
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

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Not recorded'
}

export function EmbeddingModelCard({ model, credential, onClick }: EmbeddingModelCardProps) {
  return (
    <ResourceCard
      onClick={onClick}
      aria-label={`Open Embedding model ${model.name}`}
      icon={<Cpu className="h-4 w-4" />}
      title={model.name}
      subtitle={model.model}
      status={<StatusBadge status={model.status || 'active'} size="compact" />}
      metadata={(
        <>
          <ResourcePill tone="primary">{providerLabel(model.provider || credential?.provider)}</ResourcePill>
          <ResourcePill>{dimensionsOf(model).toLocaleString()} dimensions</ResourcePill>
          {credential?.name && <ResourcePill>{credential.name}</ResourcePill>}
        </>
      )}
      footer={`Updated · ${formatDate(model.updated_at || model.created_at)}`}
    />
  )
}
