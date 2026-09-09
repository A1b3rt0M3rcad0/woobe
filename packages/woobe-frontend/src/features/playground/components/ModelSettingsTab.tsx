import { useMemo, useState } from 'react'
import { Cpu, Plus } from 'lucide-react'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { NetworkModelManagerModal } from '@/features/network/components/NetworkModelManagerModal'
import { useCredentials } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { useProviderModels } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'
import { useAgentEditor } from '../AgentEditorContext'

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  openrouter: 'OpenRouter',
  anthropic: 'Anthropic',
  google: 'Google',
  custom: 'OpenAI Compatible',
}

type Target = 'primary' | 'fallback'

function providerLabel(provider?: string | null) {
  return provider ? providerLabels[provider] || provider : 'Unknown'
}

function modelProvider(model: ProviderModel, credential?: ProviderCredential | null) {
  return model.provider || credential?.provider || ''
}

function ModelSummary({ model, credential, onChange, onRemove }: { model: ProviderModel; credential?: ProviderCredential | null; onChange: () => void; onRemove: () => void }) {
  return (
    <div className="space-y-2 rounded-lg border border-border bg-background p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <Badge variant="secondary">{providerLabel(modelProvider(model, credential))}</Badge>
            <span className="truncate text-sm font-medium">{model.name}</span>
          </div>
          <code className="mt-2 block truncate text-xs text-muted">{model.model}</code>
        </div>
        <Badge variant={model.status === 'active' ? 'success' : 'secondary'}>{model.status || 'active'}</Badge>
      </div>
      <div className="space-y-1 text-xs text-muted">
        <p>Credential: <span className="text-white/80">{credential?.name || 'Missing credential'}</span></p>
        {credential?.metadata?.base_url ? <p>Base URL: <code className="rounded bg-background px-1">{credential.metadata.base_url}</code></p> : null}
      </div>
      <div className="flex gap-2">
        <Button type="button" size="sm" variant="outline" onClick={onChange}>Change</Button>
        <Button type="button" size="sm" variant="ghost" onClick={onRemove}>Remove</Button>
      </div>
    </div>
  )
}

interface ModelSettingsTabProps {
  projectId: string
  standalone?: boolean
}

export function ModelSettingsTab({ projectId, standalone = false }: ModelSettingsTabProps) {
  const { data: credentials = [] } = useCredentials(projectId)
  const { data: providerModels = [] } = useProviderModels(projectId)
  const { state, setField } = useAgentEditor()
  const [target, setTarget] = useState<Target | null>(null)

  const credentialsById = useMemo(() => new Map(credentials.map((credential) => [credential.id, credential])), [credentials])
  const selectedModel = providerModels.find((model) => model.id === state.providerModelId) || null
  const selectedCredential = selectedModel ? credentialsById.get(selectedModel.provider_credential_id) : null
  const fallbackModel = providerModels.find((model) => model.id === state.fallbackProviderModelId) || null
  const fallbackCredential = fallbackModel ? credentialsById.get(fallbackModel.provider_credential_id) : null

  const useModel = (model: ProviderModel, credential?: ProviderCredential | null) => {
    if (target === 'fallback') {
      setField('fallbackProviderModelId', model.id)
      setField('fallbackProviderCredentialId', model.provider_credential_id)
      setField('fallbackProvider', model.provider || credential?.provider || '')
      setField('fallbackModel', model.model)
    } else {
      setField('providerModelId', model.id)
      setField('providerCredentialId', model.provider_credential_id)
      setField('provider', model.provider || credential?.provider || '')
      setField('model', model.model)
      setField('baseUrl', credential?.metadata?.base_url || null)
    }
    setTarget(null)
  }

  const removePrimary = () => {
    setField('providerModelId', null)
    setField('providerCredentialId', null)
    setField('provider', '')
    setField('model', '')
    setField('baseUrl', null)
  }

  const removeFallback = () => {
    setField('fallbackProviderModelId', null)
    setField('fallbackProviderCredentialId', null)
    setField('fallbackProvider', '')
    setField('fallbackModel', '')
  }

  const primaryContent = selectedModel ? (
    <ModelSummary model={selectedModel} credential={selectedCredential} onChange={() => setTarget('primary')} onRemove={removePrimary} />
  ) : (
    <div className="rounded-lg border border-dashed border-border bg-background/45 p-4">
      <div className="flex items-start gap-3"><Cpu className="mt-0.5 h-4 w-4 text-primary-light" /><div><p className="text-sm font-medium text-white">No primary model selected</p><p className="mt-1 text-xs leading-5 text-muted">Choose or create a reusable Project model.</p></div></div>
      <Button size="sm" className="mt-3" onClick={() => setTarget('primary')}><Plus className="mr-2 h-3.5 w-3.5" />Select model</Button>
    </div>
  )

  const fallbackContent = fallbackModel ? (
    <ModelSummary model={fallbackModel} credential={fallbackCredential} onChange={() => setTarget('fallback')} onRemove={removeFallback} />
  ) : (
    <div className="rounded-lg border border-dashed border-border bg-background/45 p-4">
      <p className="text-sm font-medium text-white">No fallback selected</p>
      <p className="mt-1 text-xs leading-5 text-muted">Add a fallback only when the runtime should retry another model.</p>
      <Button size="sm" variant="outline" className="mt-3" onClick={() => setTarget('fallback')}>Add fallback</Button>
    </div>
  )

  return (
    <>
      {standalone ? (
        <section aria-label="Model" className="space-y-5 p-4">
          <div>
            <p className="text-xs font-semibold text-white">Model</p>
            <p className="mt-1 text-[11px] leading-4 text-muted">Primary inference model and optional fallback used by this Agent.</p>
          </div>
          <div className="space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Primary</p>
            {primaryContent}
          </div>
          <div className="space-y-2 border-t border-border/80 pt-5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Fallback</p>
            {fallbackContent}
          </div>
        </section>
      ) : (
        <div className="space-y-4 p-4">
          <section className="rounded-xl border border-border bg-surface p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">Model</p>
            {primaryContent}
          </section>

          <section className="rounded-xl border border-border bg-surface p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">Fallback</p>
            {fallbackContent}
          </section>
        </div>
      )}

      <NetworkModelManagerModal
        open={target !== null}
        projectId={projectId}
        selectedModelId={target === 'fallback' ? state.fallbackProviderModelId : state.providerModelId}
        onClose={() => setTarget(null)}
        onUseModel={useModel}
      />
    </>
  )
}
