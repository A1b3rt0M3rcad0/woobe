import { useState, type ReactNode } from 'react'
import { Cpu, Plus } from 'lucide-react'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { useCredentials } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { useProviderModels } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { NetworkModelManagerModal } from './NetworkModelManagerModal'

type Target = 'primary' | 'fallback'

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section className="rounded-xl border border-border bg-surface p-4"><p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">{title}</p>{children}</section>
}
function Summary({ title, model, credential, onChange, onRemove }: { title: string; model: ProviderModel | null; credential?: ProviderCredential | null; onChange: () => void; onRemove: () => void }) {
  return <Section title={title}>{model ? <div className="rounded-lg border border-border bg-background p-3"><div className="flex items-start gap-3"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface"><Cpu className="h-4 w-4 text-primary-light" /></div><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><p className="truncate text-sm font-medium text-white">{model.name}</p><Badge variant={model.status === 'active' ? 'success' : 'secondary'}>{model.status}</Badge></div><code className="mt-1 block truncate text-xs text-muted">{model.model}</code><p className="mt-2 truncate text-xs text-muted">Connection: <span className="text-white/80">{credential?.name || 'Missing connection'}</span></p></div></div><div className="mt-3 flex gap-2 border-t border-border/80 pt-3"><Button size="sm" variant="outline" onClick={onChange}>Change</Button><Button size="sm" variant="ghost" onClick={onRemove}>Remove</Button></div></div> : <div className="rounded-lg border border-dashed border-border bg-background/45 p-4"><p className="text-sm font-medium text-white">No {title.toLowerCase()} selected</p><p className="mt-1 text-xs leading-5 text-muted">Choose or create a Project model without leaving the Network.</p><Button size="sm" className="mt-3" onClick={onChange}><Plus className="mr-2 h-3.5 w-3.5" />Select model</Button></div>}</Section>
}

export function NetworkAgentModel({ projectId }: { projectId: string }) {
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
  return <div className="space-y-4 p-4">
    <Summary title="Primary Model" model={primary} credential={credentialFor(primary)} onChange={() => setTarget('primary')} onRemove={() => { setField('providerModelId', null); setField('providerCredentialId', null); setField('provider', ''); setField('model', ''); setField('baseUrl', null) }} />
    <Summary title="Fallback" model={fallback} credential={credentialFor(fallback)} onChange={() => setTarget('fallback')} onRemove={() => { setField('fallbackProviderModelId', null); setField('fallbackProviderCredentialId', null); setField('fallbackProvider', ''); setField('fallbackModel', '') }} />
    <NetworkModelManagerModal open={target !== null} projectId={projectId} selectedModelId={target === 'fallback' ? state.fallbackProviderModelId : state.providerModelId} onClose={() => setTarget(null)} onUseModel={useModel} />
  </div>
}
