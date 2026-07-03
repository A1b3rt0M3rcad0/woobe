import { useEffect, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { useCreateKnowledgeProviderModel } from '@/features/knowledge/vectorHooks'

interface CreateEmbeddingModelModalProps {
  open: boolean
  projectId: string
  onClose: () => void
  onCreated: (modelId: string) => void
}

function defaultModelForProvider(provider?: string) {
  if (provider === 'openai') return 'text-embedding-3-small'
  if (provider === 'openrouter') return 'openai/text-embedding-3-small'
  return 'text-embedding-3-small'
}

export function CreateEmbeddingModelModal({ open, projectId, onClose, onCreated }: CreateEmbeddingModelModalProps) {
  const { data: credentials = [] } = useCredentials(projectId)
  const createModel = useCreateKnowledgeProviderModel(projectId)
  const [credentialId, setCredentialId] = useState('')
  const [name, setName] = useState('Text embedding 3 small')
  const [model, setModel] = useState('text-embedding-3-small')
  const selectedCredential = credentials.find((credential) => credential.id === credentialId)

  useEffect(() => {
    if (!open) return
    const first = credentials[0]
    if (first) {
      setCredentialId(first.id)
      const defaultModel = defaultModelForProvider(first.provider)
      setModel(defaultModel)
      setName(defaultModel)
    }
  }, [open, credentials])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!credentialId) {
      toast.error('Select a provider credential')
      return
    }
    if (!name.trim() || !model.trim()) {
      toast.error('Name and model are required')
      return
    }

    try {
      const created = await createModel.mutateAsync({
        project_id: projectId,
        provider_credential_id: credentialId,
        name: name.trim(),
        model: model.trim(),
        metadata: {
          capability: 'embedding',
          dimensions: 1536,
        },
      })
      toast.success('Embedding model added')
      onCreated(String(created.id))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add embedding model')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Add embedding model" className="max-w-lg">
      <form onSubmit={submit} className="space-y-4">
        {credentials.length === 0 ? (
          <div className="rounded-xl border border-border bg-background/60 p-3 text-sm leading-6 text-muted">
            Add a provider credential first. Embedding models need an active BYOK credential.
          </div>
        ) : (
          <>
            <div>
              <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Provider credential</label>
              <select value={credentialId} onChange={(event) => { const id = event.target.value; setCredentialId(id); const credential = credentials.find((item) => item.id === id); const nextModel = defaultModelForProvider(credential?.provider); setModel(nextModel); setName(nextModel) }} className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-white outline-none focus:border-primary">
                {credentials.map((credential) => <option key={credential.id} value={credential.id}>{credential.name} · {credential.provider}</option>)}
              </select>
              {selectedCredential?.status && <p className="mt-2 text-xs text-muted">Status: {selectedCredential.status}</p>}
            </div>
            <div>
              <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Display name</label>
              <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Embedding model name" />
            </div>
            <div>
              <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Model</label>
              <Input value={model} onChange={(event) => setModel(event.target.value)} placeholder="text-embedding-3-small" />
            </div>
          </>
        )}
        <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" onClick={onClose} disabled={createModel.isPending}>Cancel</Button>
          <Button type="submit" loading={createModel.isPending} disabled={credentials.length === 0}>Add model</Button>
        </div>
      </form>
    </Dialog>
  )
}
