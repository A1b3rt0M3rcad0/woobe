import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Key, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import { useCredentials } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { useAvailableProviderModels, useCreateProviderModel, useUpdateProviderModel } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'

interface CreateEmbeddingModelModalProps {
  open: boolean
  projectId: string
  onClose: () => void
  onCreated: (modelId: string) => void
  model?: ProviderModel | null
}

function supportsModelCatalog(credential?: ProviderCredential | null) {
  return credential?.provider === 'openai' || credential?.provider === 'openrouter'
}

export function CreateEmbeddingModelModal({ open, projectId, onClose, onCreated, model = null }: CreateEmbeddingModelModalProps) {
  const { data: credentials = [], refetch: refetchCredentials } = useCredentials(projectId)
  const createModel = useCreateProviderModel()
  const updateModel = useUpdateProviderModel()
  const wasOpen = useRef(false)

  const activeCredentials = useMemo(
    () => credentials.filter((credential) => !credential.status || credential.status === 'active'),
    [credentials],
  )

  const [credentialId, setCredentialId] = useState('')
  const [name, setName] = useState('')
  const [modelIdentifier, setModelIdentifier] = useState('')
  const [catalogModelId, setCatalogModelId] = useState('')
  const [manualMode, setManualMode] = useState(false)
  const [credentialModalOpen, setCredentialModalOpen] = useState(false)

  const selectedCredential = activeCredentials.find((credential) => credential.id === credentialId) || null
  const catalogQuery = useAvailableProviderModels(
    projectId,
    supportsModelCatalog(selectedCredential) ? credentialId : undefined,
    'embedding',
  )
  const embeddingCatalog = catalogQuery.data ?? []

  useEffect(() => {
    const justOpened = open && !wasOpen.current
    wasOpen.current = open
    if (!justOpened) return

    if (model) {
      setCredentialId(model.provider_credential_id)
      setName(model.name)
      setModelIdentifier(model.model)
      setCatalogModelId('')
      setManualMode(true)
      return
    }

    setCredentialId('')
    setName('')
    setModelIdentifier('')
    setCatalogModelId('')
    setManualMode(false)
  }, [open, model])

  useEffect(() => {
    if (!open || model || credentialId || activeCredentials.length === 0) return
    const firstCredential = activeCredentials[0]
    setCredentialId(firstCredential.id)
    setManualMode(!supportsModelCatalog(firstCredential))
  }, [open, model, credentialId, activeCredentials])

  const selectCredential = (nextCredentialId: string) => {
    const credential = activeCredentials.find((item) => item.id === nextCredentialId) || null
    setCredentialId(nextCredentialId)
    setName('')
    setModelIdentifier('')
    setCatalogModelId('')
    setManualMode(!supportsModelCatalog(credential))
  }

  const selectCatalogModel = (catalogId: string) => {
    const selected = embeddingCatalog.find((item) => item.id === catalogId)
    setCatalogModelId(catalogId)
    if (!selected) return
    setModelIdentifier(selected.id)
    setName(selected.label || selected.id)
  }

  const handleCredentialCreated = (createdCredentialId: string) => {
    setCredentialModalOpen(false)
    setCredentialId(createdCredentialId)
    setName('')
    setModelIdentifier('')
    setCatalogModelId('')
    setManualMode(false)
    void refetchCredentials()
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!credentialId) {
      toast.error('Select a provider credential')
      return
    }
    if (!name.trim() || !modelIdentifier.trim()) {
      toast.error('Name and model are required')
      return
    }

    const selectedCatalogModel = embeddingCatalog.find((item) => item.id === catalogModelId) || null
    const metadata = {
      ...(model?.metadata || {}),
      capability: 'embedding',
      dimensions: 1536,
      source: selectedCatalogModel ? 'remote' : 'manual',
      catalog: selectedCatalogModel ? {
        provider: selectedCatalogModel.provider,
        model_id: selectedCatalogModel.id,
        label: selectedCatalogModel.label,
        owned_by: selectedCatalogModel.owned_by ?? null,
      } : model?.metadata?.catalog,
    }

    try {
      if (model) {
        const updated = await updateModel.mutateAsync({
          id: model.id,
          data: {
            provider_credential_id: credentialId,
            name: name.trim(),
            model: modelIdentifier.trim(),
            metadata,
          },
        })
        toast.success('Embedding model updated')
        onCreated(updated.id)
        return
      }

      const created = await createModel.mutateAsync({
        project_id: projectId,
        provider_credential_id: credentialId,
        name: name.trim(),
        model: modelIdentifier.trim(),
        metadata,
      })
      toast.success('Embedding model added')
      onCreated(created.id)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save embedding model')
    }
  }

  const pending = createModel.isPending || updateModel.isPending

  return (
    <>
      <Dialog open={open} onClose={onClose} title={model ? 'Edit embedding model' : 'Add embedding model'} className="max-w-lg">
        <form onSubmit={submit} className="space-y-4">
          {activeCredentials.length === 0 ? (
            <div className="rounded-xl border border-border bg-background/60 p-4">
              <div className="flex items-start gap-3">
                <Key className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />
                <div>
                  <p className="text-sm font-medium text-white">A provider credential is required.</p>
                  <p className="mt-1 text-sm leading-6 text-muted">Add a BYOK credential, then create the embedding model used to build vectors.</p>
                </div>
              </div>
              <Button type="button" size="sm" variant="outline" className="mt-4" onClick={() => setCredentialModalOpen(true)}>
                <Plus className="mr-2 h-4 w-4" /> Add credential
              </Button>
            </div>
          ) : (
            <>
              <div>
                <div className="mb-1.5 flex items-center justify-between gap-3">
                  <label className="block text-sm font-medium text-muted">Credential</label>
                  <Button type="button" size="sm" variant="ghost" className="h-auto px-0 py-0 text-xs" onClick={() => setCredentialModalOpen(true)}>Add credential</Button>
                </div>
                <Select
                  value={credentialId}
                  onChange={(event) => selectCredential(event.target.value)}
                  options={activeCredentials.map((credential) => ({
                    value: credential.id,
                    label: `${credential.name} · ${credential.provider}`,
                  }))}
                />
              </div>

              {!manualMode && supportsModelCatalog(selectedCredential) ? (
                <div>
                  <div className="mb-1.5 flex items-center justify-between gap-3">
                    <label className="block text-sm font-medium text-muted">Embedding model</label>
                    <Button type="button" size="sm" variant="ghost" className="h-auto px-0 py-0 text-xs" onClick={() => { setManualMode(true); setCatalogModelId(''); setModelIdentifier(''); setName('') }}>Enter manually</Button>
                  </div>
                  {catalogQuery.isLoading ? (
                    <div className="rounded-lg border border-border bg-background/50 px-3 py-3 text-sm text-muted">Loading embedding models...</div>
                  ) : catalogQuery.isError ? (
                    <div className="rounded-lg border border-border bg-background/50 px-3 py-3 text-sm text-muted">Could not load the embedding catalog. Use manual entry.</div>
                  ) : embeddingCatalog.length === 0 ? (
                    <div className="rounded-lg border border-border bg-background/50 px-3 py-3 text-sm text-muted">No embedding models were returned by this provider. Use manual entry.</div>
                  ) : (
                    <Select
                      value={catalogModelId}
                      onChange={(event) => selectCatalogModel(event.target.value)}
                      placeholder="Select embedding model"
                      options={embeddingCatalog.map((item) => ({ value: item.id, label: item.label }))}
                    />
                  )}
                </div>
              ) : (
                <div>
                  <div className="mb-1.5 flex items-center justify-between gap-3">
                    <label className="block text-sm font-medium text-muted">Model</label>
                    {supportsModelCatalog(selectedCredential) && !model && (
                      <Button type="button" size="sm" variant="ghost" className="h-auto px-0 py-0 text-xs" onClick={() => { setManualMode(false); setModelIdentifier(''); setName('') }}>Use provider catalog</Button>
                    )}
                  </div>
                  <Input value={modelIdentifier} onChange={(event) => setModelIdentifier(event.target.value)} placeholder="text-embedding-3-small" />
                </div>
              )}

              <div>
                <label className="mb-1.5 block text-sm font-medium text-muted">Display name</label>
                <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Production embeddings" />
              </div>

              <p className="text-xs leading-5 text-muted">The MVP stores this model as an embedding-capable provider model with 1536 dimensions.</p>
            </>
          )}

          <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" onClick={onClose} disabled={pending}>Cancel</Button>
            <Button type="submit" loading={pending} disabled={activeCredentials.length === 0 || !credentialId || !name.trim() || !modelIdentifier.trim()}>
              {model ? 'Save changes' : 'Add model'}
            </Button>
          </div>
        </form>
      </Dialog>

      <AddProviderCredentialModal
        open={credentialModalOpen}
        onClose={() => setCredentialModalOpen(false)}
        projectId={projectId}
        onCredentialCreated={handleCredentialCreated}
      />
    </>
  )
}
