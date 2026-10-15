import { useEffect, useState } from 'react'
import { Button, Dialog } from '@woobe/ui'
import { ProviderCredentialCreateForm } from '@/features/provider-credentials/components/ProviderCredentialCreateForm'
import { ProviderConnectionConfiguration } from '@/features/provider-credentials/components/ProviderConnectionConfiguration'
import type { ProviderCredential } from '@/features/provider-credentials/types'

interface ProviderConnectionModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  existingCredentials: ProviderCredential[]
  onCreated: (credential: ProviderCredential) => void
}
const formId = 'first-run-provider-connection-form'
export function ProviderConnectionModal({ open, onClose, projectId, existingCredentials, onCreated }: ProviderConnectionModalProps) {
  const [pending, setPending] = useState(false)
  const [saved, setSaved] = useState<ProviderCredential | null>(null)
  useEffect(() => { if (open) { setSaved(null); setPending(false) } }, [open])
  const close = () => {
    if (pending) return
    if (saved) onCreated(saved)
    onClose()
  }
  return <Dialog open={open} onClose={close} title={saved ? 'Configure provider connection' : 'Connect provider'} className="max-w-2xl">
    {saved ? <div className="space-y-4">
      <div role="status"><p className="break-words text-sm font-medium text-foreground">Connection saved: {saved.name}</p><p className="mt-1 text-sm leading-6 text-muted-foreground">Finish Draft access here. Your Agent instructions remain in the setup form.</p></div>
      <ProviderConnectionConfiguration credential={saved} />
      <div className="flex justify-end border-t border-border pt-4"><Button type="button" onClick={close}>Continue to models</Button></div>
    </div> : <>
      <ProviderCredentialCreateForm projectId={projectId} existingCredentials={existingCredentials} formId={formId} showActions={false} onPendingChange={setPending} onCreated={setSaved} />
      <div className="mt-5 flex flex-wrap justify-end gap-3 border-t border-border pt-4"><Button type="button" variant="outline" onClick={close} disabled={pending}>Cancel</Button><Button type="submit" form={formId} loading={pending}>Save connection</Button></div>
    </>}
  </Dialog>
}
