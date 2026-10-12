import { Button, TechnicalListItem } from '@woobe/ui'
import { selectionMessage } from './environmentSelection'

export function EnvironmentSelectionNotice({ selection, environment }: {
  selection: { state: string; snapshotId: string | null; detailState?: string; refetch: () => unknown; retry?: () => unknown }
  environment: string
}) {
  return <TechnicalListItem label={environment} description={selectionMessage(selection, environment)}
    trailing={selection.state === 'unknown' || selection.detailState === 'unknown'
      ? <Button size="sm" variant="outline" onClick={() => void (selection.retry ?? selection.refetch)()}>Retry</Button> : undefined} />
}
