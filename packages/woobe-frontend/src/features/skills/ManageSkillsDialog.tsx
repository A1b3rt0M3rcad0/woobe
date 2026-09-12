import { useState } from 'react'
import { Dialog } from '@/components/ui/Dialog'
import { SkillCatalog, type SkillCatalogProps } from './SkillCatalog'

export function ManageSkillsDialog({ onClose, title = 'Manage Skills', ...props }: SkillCatalogProps & { onClose: () => void; title?: string }) {
  const [busy, setBusy] = useState(false)
  return (
    <Dialog
      open
      onClose={busy ? () => {} : onClose}
      title={title}
      className="flex h-[min(760px,calc(100svh-2rem))] max-w-4xl flex-col overflow-hidden"
      contentClassName="min-h-0 flex-1 p-0"
    >
      <div className="h-full min-h-0 overflow-y-auto p-4 scrollbar-thin">
        <SkillCatalog {...props} onBusyChange={setBusy} onInstall={props.onInstall ? version => { props.onInstall?.(version); onClose() } : undefined} />
      </div>
    </Dialog>
  )
}
