import { useState } from 'react'
import { Cpu, Trash2 } from 'lucide-react'
import { Badge, Button, EmptyStatePanel, PanelHeader, TechnicalListItem } from '@woobe/ui'

import { useCredentials } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { useProviderModels } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { AgentModelManagerModal } from './AgentModelManagerModal'

type Target = 'primary' | 'fallback'

function Summary({
  title,
  model,
  credential,
  onChange,
  onRemove,
}: {
  title: string
  model: ProviderModel | null
  credential?: ProviderCredential | null
  onChange: () => void
  onRemove: () => void
}) {
  if (!model) {
    return (
      <div className="border-t border-border p-ui-md">
        <EmptyStatePanel
          compact
          title={`No ${title.toLowerCase()} selected`}
          action={<Button size="sm" variant="outline" onClick={onChange}>Select model</Button>}
          className="border-0 bg-transparent"
        />
      </div>
    )
  }

  return (
    <div className="border-t border-border p-ui-md">
      <TechnicalListItem
        label={model.name}
        description={model.model !== model.name ? model.model : `${title} model`}
        meta={(
          <>
            <span>{title}</span>
            <span>Connection · {credential?.name || 'Missing connection'}</span>
          </>
        )}
        trailing={<Badge variant={model.status === 'active' ? 'success' : 'outline'} size="compact">{model.status}</Badge>}
      >
        <div className="mt-ui-sm flex flex-wrap gap-ui-sm border-t border-border pt-ui-sm">
          <Button size="sm" variant="outline" onClick={onChange}>Change</Button>
          <Button size="sm" variant="ghost" onClick={onRemove}>
            <Trash2 className="h-icon-sm w-icon-sm text-error" />Remove
          </Button>
        </div>
      </TechnicalListItem>
    </div>
  )
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

  return (
    <div className="p-ui-md">
      <section aria-label="Model" className="rounded-container border border-border bg-surface/[0.72]">
        <PanelHeader
          icon={<Cpu className="h-icon w-icon" />}
          title="Model"
          description={`${primary ? 'Primary configured' : 'No primary model'} · ${fallback ? 'Fallback configured' : 'No fallback'}`}
        />
        <Summary
          title="Primary"
          model={primary}
          credential={credentialFor(primary)}
          onChange={() => setTarget('primary')}
          onRemove={() => {
            setField('providerModelId', null)
            setField('providerCredentialId', null)
            setField('provider', '')
            setField('model', '')
            setField('baseUrl', null)
          }}
        />
        <Summary
          title="Fallback"
          model={fallback}
          credential={credentialFor(fallback)}
          onChange={() => setTarget('fallback')}
          onRemove={() => {
            setField('fallbackProviderModelId', null)
            setField('fallbackProviderCredentialId', null)
            setField('fallbackProvider', '')
            setField('fallbackModel', '')
          }}
        />
      </section>
      <AgentModelManagerModal
        open={target !== null}
        projectId={projectId}
        selectedModelId={target === 'fallback' ? state.fallbackProviderModelId : state.providerModelId}
        onClose={() => setTarget(null)}
        onUseModel={useModel}
      />
    </div>
  )
}
