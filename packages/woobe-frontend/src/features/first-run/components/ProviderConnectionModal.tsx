import { useState } from 'react'
import { toast } from 'sonner'
import { Button, Dialog } from '@woobe/ui'

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

export function ProviderConnectionModal({ open, onClose, projectId, existingCredentials, onCreated }: ProviderConnectionModalProps) {
  const [pending, setPending] = useState(false)

  return (
    <Dialog open={open} onClose={pending ? () => undefined : onClose} title="Connect provider" className="max-w-dialog">
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
      <div className="mt-ui-md flex items-center justify-end gap-ui-sm border-t border-border pt-ui-md">
        <Button type="button" variant="outline" onClick={onClose} disabled={pending}>Cancel</Button>
        <Button type="submit" form={formId} loading={pending}>Connect provider</Button>
      </div>
    </Dialog>
  )
}
