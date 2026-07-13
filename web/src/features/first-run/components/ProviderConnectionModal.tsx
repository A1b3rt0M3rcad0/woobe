import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { ProviderCredentialCreateForm } from '@/features/provider-credentials/components/ProviderCredentialCreateForm'
import type { ProviderCredential } from '@/features/provider-credentials/types'

interface ProviderConnectionModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  existingCredentials: ProviderCredential[]
  onCreated: (credential: ProviderCredential) => void
}

const formId = 'first-run-provider-connection-form'

export function ProviderConnectionModal({
  open,
  onClose,
  projectId,
  existingCredentials,
  onCreated,
}: ProviderConnectionModalProps) {
  const [pending, setPending] = useState(false)

  return (
    <Dialog
      open={open}
      onClose={pending ? () => undefined : onClose}
      title="Connect provider"
      className="max-w-3xl overflow-hidden"
    >
      <ProviderCredentialCreateForm
        projectId={projectId}
        existingCredentials={existingCredentials}
        formId={formId}
        showActions={false}
        onPendingChange={setPending}
        onCreated={(credential) => {
          toast.success('Provider connected')
          onCreated(credential)
          onClose()
        }}
      />

      <div className="mt-6 flex items-center justify-end gap-2 border-t border-border/80 pt-4">
        <Button type="button" variant="outline" onClick={onClose} disabled={pending}>Cancel</Button>
        <Button type="submit" form={formId} loading={pending}>Connect provider</Button>
      </div>
    </Dialog>
  )
}
