import { useState } from 'react'
import { useCreateCollection, useAttachCollection } from '@/features/knowledge/hooks'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { toast } from 'sonner'

interface CreateCollectionModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  agentId: string
}

export function CreateCollectionModal({ open, onClose, projectId, agentId }: CreateCollectionModalProps) {
  const createCollection = useCreateCollection()
  const attachCollection = useAttachCollection()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      toast.error('Collection name is required')
      return
    }
    setSaving(true)
    try {
      const collection = await createCollection.mutateAsync({
        project_id: projectId,
        name: name.trim(),
        description: description.trim() || undefined,
      })
      await attachCollection.mutateAsync({
        agent_id: agentId,
        collection_id: collection.id,
      })
      toast.success('Collection created and attached')
      setName('')
      setDescription('')
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create collection')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Create Collection">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Collection name"
        />
        <Textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description (optional)"
        />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={saving}>Create & Attach</Button>
        </div>
      </form>
    </Dialog>
  )
}
