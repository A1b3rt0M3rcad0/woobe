import { useState } from 'react'
import { Dialog } from '@/components/ui/Dialog'
import { SkillCatalog, type SkillCatalogProps } from './SkillCatalog'

export function ManageSkillsDialog({ onClose, title = 'Manage Skills', ...props }: SkillCatalogProps & { onClose: () => void; title?: string }) {
  const [busy, setBusy] = useState(false)
  return <Dialog open onClose={busy ? () => {} : onClose} title={title} className="max-w-4xl" scrollMode="content">
    <SkillCatalog {...props} onBusyChange={setBusy} onInstall={props.onInstall ? version => { props.onInstall?.(version); onClose() } : undefined} />
  </Dialog>
}
