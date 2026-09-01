import { useEffect, useState, type FormEvent } from 'react'
import { AlertTriangle, CheckCircle2, RotateCcw } from 'lucide-react'
import { toast } from 'sonner'

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

export function RotateProviderCredentialDialog({
  open,
  credential,
  generationCount,
  embeddingCount,
  onClose,
  onRotated,
}: RotateProviderCredentialDialogProps) {
  const rotateCredential = useRotateCredential()
  const [secret, setSecret] = useState('')

  useEffect(() => {
    if (!open) setSecret('')
  }, [open])

  const handleClose = () => {
    if (!rotateCredential.isPending) onClose()
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!credential) return
    if (!secret.trim()) return toast.error('New provider API key is required')

    try {
      const rotated = await rotateCredential.mutateAsync({
        id: credential.id,
        data: {
          secret: secret.trim(),
        },
      })
      setSecret('')
      toast.success('Provider key rotated', {
        description: 'Revoke the previous key in the provider dashboard when you are ready.',
      })
      onRotated(rotated)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to rotate provider key', {
        description: 'The current stored key was not changed.',
      })
    }
  }

  return (
    <Dialog open={open} onClose={handleClose} title="Rotate provider key" className="max-w-2xl">
      {credential && (
        <form onSubmit={handleSubmit} className="space-y-5">
          <section className="rounded-xl border border-border/80 bg-surface/60 p-4">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
                <RotateCcw className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{credential.name}</p>
                <p className="mt-1 text-xs text-muted">{credential.provider}</p>
              </div>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border border-border/70 bg-background/55 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Generation models</p>
                <p className="mt-1 text-sm font-medium text-white">{generationCount}</p>
              </div>
              <div className="rounded-lg border border-border/70 bg-background/55 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Embedding models</p>
                <p className="mt-1 text-sm font-medium text-white">{embeddingCount}</p>
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-primary/25 bg-primary/5 p-4">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />
              <div>
                <p className="text-sm font-semibold text-white">Existing bindings stay unchanged</p>
                <p className="mt-1 text-xs leading-5 text-muted">The credential ID is preserved. Connected models, Agents and releases continue using this connection without relinking.</p>
              </div>
            </div>
          </section>

          <div>
            <label className="mb-1 block text-sm font-medium text-muted">New API key</label>
            <ProviderSecretInput
              value={secret}
              onChange={setSecret}
              placeholder="Paste the replacement API key"
              disabled={rotateCredential.isPending}
              autoFocus
            />
            <p className="mt-2 text-xs leading-5 text-muted">The current stored key remains active until the replacement is verified successfully.</p>
          </div>

          <section className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-300" />
              <div>
                <p className="text-sm font-semibold text-yellow-100">Provider-side revocation is separate</p>
                <p className="mt-1 text-xs leading-5 text-yellow-100/70">Woobe replaces the stored secret but cannot revoke the previous key at the provider. Revoke it in the provider dashboard after rotation succeeds.</p>
              </div>
            </div>
          </section>

          <div className="flex justify-end gap-2 border-t border-border/80 pt-4">
            <Button type="button" variant="outline" onClick={handleClose} disabled={rotateCredential.isPending}>Cancel</Button>
            <Button type="submit" loading={rotateCredential.isPending} disabled={!secret.trim()}>
              Verify and rotate
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  )
}
