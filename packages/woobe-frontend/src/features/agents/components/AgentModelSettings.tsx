import { useState } from 'react'
import { Cpu } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { useCredentials } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { useProviderModels } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { AgentModelManagerModal } from './AgentModelManagerModal'

type Target = 'primary' | 'fallback'

function Summary({ title, model, credential, onChange, onRemove }: { title: string; model: ProviderModel | null; credential?: ProviderCredential | null; onChange: () => void; onRemove: () => void }) {
  return <div className="border-t border-border p-4">
    {model ? <>
      <p className="mb-3 text-[11px] text-muted">{title}</p>
      <div className="flex items-start justify-between gap-2">
        <p className="min-w-0 break-words text-xs font-semibold text-foreground">{model.name}</p>
        <span className={`shrink-0 text-[11px] capitalize ${model.status === 'active' ? 'text-emerald-300' : 'text-muted'}`}>● {model.status}</span>
      </div>
      {model.model !== model.name ? <code title={model.model} className="mt-1 block truncate text-[11px] text-muted">{model.model}</code> : null}
      <p title={credential?.name || 'Missing connection'} className="mt-1 truncate text-[11px] text-muted">Connection · <span className="text-foreground/80">{credential?.name || 'Missing connection'}</span></p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={onChange}>Change</Button>
        <Button size="sm" variant="ghost" className="text-muted hover:text-red-300" onClick={onRemove}>Remove</Button>
      </div>
    </> : <div className="flex items-center justify-between gap-2">
      <div className="min-w-0"><p className="text-xs font-medium">{title}</p><p className="mt-1 text-[11px] text-muted">No model selected</p></div>
      <Button size="sm" variant="ghost" className="shrink-0 text-[11px] text-primary-light" onClick={onChange}>Select model</Button>
    </div>}
  </div>
}

export function AgentModelSettings({ projectId }: { projectId: string }) {
  const { data: models = [] } = useProviderModels(projectId)
  const { data: credentials = [] } = useCredentials(projectId)
  const { state, setField } = useAgentEditor()
  const [target, setTarget] = useState<Target | null>(null)
  const primary = models.find((item) => item.id === state.providerModelId) || null
  const fallback = models.find((item) => item.id === state.fallbackProviderModelId) || null
  const credentialFor = (model: ProviderModel | null) => model ? credentials.find((item) => item.id === model.provider_credential_id) || null : null
  const useModel = (model: ProviderModel, credential?: ProviderCredential | null) => {
    if (target === 'fallback') {
      setField('fallbackProviderModelId', model.id); setField('fallbackProviderCredentialId', model.provider_credential_id); setField('fallbackProvider', model.provider || credential?.provider || ''); setField('fallbackModel', model.model)
    } else {
      setField('providerModelId', model.id); setField('providerCredentialId', model.provider_credential_id); setField('provider', model.provider || credential?.provider || ''); setField('model', model.model); setField('baseUrl', credential?.metadata?.base_url || null)
    }
    setTarget(null)
  }
  return <div className="p-4">
    <section aria-label="Model" className="rounded-xl border border-border bg-surface">
      <div className="flex items-center gap-3 p-4"><Cpu className="h-4 w-4 shrink-0 text-primary" /><div className="min-w-0"><p className="text-sm font-semibold">Model</p><p className="mt-0.5 text-[11px] text-muted">{primary ? 'Primary configured' : 'No primary model'} · {fallback ? 'Fallback configured' : 'No fallback'}</p></div></div>
    <Summary title="Primary model" model={primary} credential={credentialFor(primary)} onChange={() => setTarget('primary')} onRemove={() => { setField('providerModelId', null); setField('providerCredentialId', null); setField('provider', ''); setField('model', ''); setField('baseUrl', null) }} />
    <Summary title="Fallback" model={fallback} credential={credentialFor(fallback)} onChange={() => setTarget('fallback')} onRemove={() => { setField('fallbackProviderModelId', null); setField('fallbackProviderCredentialId', null); setField('fallbackProvider', ''); setField('fallbackModel', '') }} />
    </section>
    <AgentModelManagerModal open={target !== null} projectId={projectId} selectedModelId={target === 'fallback' ? state.fallbackProviderModelId : state.providerModelId} onClose={() => setTarget(null)} onUseModel={useModel} />
  </div>
}
