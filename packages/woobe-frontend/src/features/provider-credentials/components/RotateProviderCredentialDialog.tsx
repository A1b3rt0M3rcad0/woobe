import { useEffect, useState, type FormEvent } from 'react'
import { AlertTriangle, CheckCircle2, RotateCcw } from 'lucide-react'
import { toast } from 'sonner'
import { Alert, AlertDescription, Field, FieldDescription, FieldLabel, MetricTile, SectionBlock } from '@woobe/ui'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { ProviderSecretInput } from '@/features/provider-credentials/components/ProviderSecretInput'
import { useRotateCredential } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'

interface RotateProviderCredentialDialogProps {
  open: boolean
  credential: ProviderCredential | null
  projectId?: string
  generationCount: number
  embeddingCount: number
  onClose: () => void
  onRotated: (credential: ProviderCredential) => void
}

export function RotateProviderCredentialDialog({ open, credential, generationCount, embeddingCount, onClose, onRotated }: RotateProviderCredentialDialogProps) {
  const rotateCredential = useRotateCredential()
  const [secret, setSecret] = useState('')

  useEffect(() => { if (!open) setSecret('') }, [open])
  const handleClose = () => { if (!rotateCredential.isPending) onClose() }
  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!credential) return
    if (!secret.trim()) return toast.error('New provider API key is required')
    try {
      const rotated = await rotateCredential.mutateAsync({ id: credential.id, data: { secret: secret.trim() } })
      setSecret('')
      toast.success('Provider key rotated', { description: 'Revoke the previous key in the provider dashboard when you are ready.' })
      onRotated(rotated)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to rotate provider key', { description: 'The current stored key was not changed.' })
    }
  }

  return (
    <Dialog open={open} onClose={handleClose} title="Rotate provider key" className="max-w-2xl">
      {credential ? (
        <form onSubmit={handleSubmit} className="space-y-3">
          <SectionBlock title={credential.name} eyebrow={credential.provider} density="compact" actions={<RotateCcw className="h-3.5 w-3.5 text-primary-light" />}>
            <div className="grid gap-2 sm:grid-cols-2">
              <MetricTile label="Generation models" value={generationCount} />
              <MetricTile label="Embedding models" value={embeddingCount} />
            </div>
          </SectionBlock>

          <Alert variant="info">
            <AlertDescription><span className="inline-flex items-center gap-1.5 font-mono text-[9px] font-semibold text-slate-100"><CheckCircle2 className="h-3.5 w-3.5 text-primary-light" />Existing bindings stay unchanged</span><span className="mt-1 block">The credential ID is preserved. Connected models, Agents and releases continue using this connection without relinking.</span></AlertDescription>
          </Alert>

          <Field>
            <FieldLabel>New API key</FieldLabel>
            <ProviderSecretInput value={secret} onChange={setSecret} placeholder="Paste the replacement API key" disabled={rotateCredential.isPending} autoFocus />
            <FieldDescription>The current stored key remains active until the replacement is verified successfully.</FieldDescription>
          </Field>

          <Alert variant="warning">
            <AlertDescription><span className="inline-flex items-center gap-1.5 font-mono text-[9px] font-semibold"><AlertTriangle className="h-3.5 w-3.5" />Provider-side revocation is separate</span><span className="mt-1 block">Woobe replaces the stored secret but cannot revoke the previous key at the provider. Revoke it in the provider dashboard after rotation succeeds.</span></AlertDescription>
          </Alert>

          <div className="flex justify-end gap-2 border-t border-border pt-3">
            <Button type="button" variant="outline" onClick={handleClose} disabled={rotateCredential.isPending}>Cancel</Button>
            <Button type="submit" loading={rotateCredential.isPending} disabled={!secret.trim()}>Verify and rotate</Button>
          </div>
        </form>
      ) : null}
    </Dialog>
  )
}
