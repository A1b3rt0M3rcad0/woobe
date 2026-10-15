import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button, Dialog } from '@woobe/ui'
import { checkConfigurationDeletion, deleteConfiguration, type ConfigurationKey } from '../configuration'
import type { ProjectEnvironment } from '../types'

interface Props {
  projectId: string
  item: ConfigurationKey
  environment: ProjectEnvironment
  onClose: () => void
  onSaved: () => void
}

export function ConfigurationKeyDeletionDialog({ projectId, item, environment, onClose, onSaved }: Props) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const check = useQuery({
    queryKey: ['configuration-deletion', projectId, item.id, environment],
    queryFn: () => checkConfigurationDeletion(projectId, item, environment),
    staleTime: 0, refetchOnMount: 'always', retry: false,
  })
  const stale = check.data && check.data.definition_revision !== item.definition_revision
  const allowed = check.isSuccess && !check.isFetching && check.data.can_delete && !stale
  const remove = async () => {
    if (!allowed || pending) return
    setPending(true)
    setError('')
    try {
      await deleteConfiguration(projectId, item)
      onSaved()
      onClose()
    } catch {
      setError('The key was not deleted. It may now be in use or changed. Refresh its usage before trying again.')
      await check.refetch()
    } finally { setPending(false) }
  }
  return <Dialog open onClose={() => { if (!pending) onClose() }} title={`Delete key · ${item.key}`}>
    <div className="space-y-ui-md p-ui-lg">
      <p>This deletes the key and its values in Draft, Staging and Production.</p>
      {check.isFetching ? <p role="status">Checking whether this key is in use…</p>
        : check.isError ? <p role="alert">Usage could not be checked. Deletion is unavailable.</p>
          : stale ? <p role="alert">This key changed. Close this dialog and refresh the list before deleting it.</p>
            : check.data?.can_delete ? <p>No retained resources, legacy bindings or active Runs use this key.</p>
              : <div role="alert" className="space-y-ui-sm"><p>This key is in use. You can edit it, but cannot delete it.</p>
                <ul className="list-disc pl-ui-lg">
                  {check.data?.blockers.retained_resources && <li>Referenced by a saved resource definition.</li>}
                  {check.data?.blockers.legacy_binding && <li>Connected through a legacy binding.</li>}
                  {check.data?.blockers.active_run && <li>Protected by an active Run.</li>}
                </ul>
              </div>}
      {error && <p role="alert" className="text-destructive">{error}</p>}
      <div className="flex flex-wrap justify-end gap-ui-sm">
        <Button variant="outline" disabled={pending || check.isFetching} onClick={() => void check.refetch()}>Refresh usage</Button>
        <Button variant="outline" disabled={pending} onClick={onClose}>Cancel</Button>
        <Button variant="destructive" disabled={!allowed || pending} onClick={() => void remove()}>{pending ? 'Deleting…' : 'Delete key'}</Button>
      </div>
    </div>
  </Dialog>
}
