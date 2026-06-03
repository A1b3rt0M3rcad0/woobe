import { useState } from 'react'
import { useCollections, useAttachCollection } from '@/features/knowledge/hooks'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { toast } from 'sonner'

interface AttachCollectionModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  agentId: string
  existingCollectionIds: string[]
}

export function AttachCollectionModal({ open, onClose, projectId, agentId, existingCollectionIds }: AttachCollectionModalProps) {
  const { data: collections } = useCollections(projectId)
  const attachCollection = useAttachCollection()
  const [selectedId, setSelectedId] = useState('')

  const available = (collections || []).filter(
    (c) => !existingCollectionIds.includes(c.id)
  )

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedId) {
      toast.error('Select a collection')
      return
    }
    try {
      await attachCollection.mutateAsync({
        agent_id: agentId,
        collection_id: selectedId,
      })
      toast.success('Collection attached')
      setSelectedId('')
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to attach collection')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Attach Existing Collection">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-muted mb-1">Collection</label>
          <Select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            options={available.map((c) => ({ value: c.id, label: c.name }))}
            placeholder={available.length === 0 ? 'No collections available' : 'Select collection'}
          />
          {available.length === 0 && (
            <p className="text-xs text-muted mt-1">All collections are already attached.</p>
          )}
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={!selectedId || available.length === 0} loading={attachCollection.isPending}>Attach</Button>
        </div>
      </form>
    </Dialog>
  )
}
