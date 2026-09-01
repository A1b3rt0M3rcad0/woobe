import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { useCreateCollection } from '@/features/knowledge/hooks'
import type { Collection } from '@/features/knowledge/types'

interface CreateCollectionModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  onCreated?: (collection: Collection) => void
}

export function CreateCollectionModal({ open, onClose, projectId, onCreated }: CreateCollectionModalProps) {
  const createCollection = useCreateCollection()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  useEffect(() => {
    if (!open) return
    setName('')
    setDescription('')
  }, [open])

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!name.trim()) {
      toast.error('Collection name is required')
      return
    }

    try {
      const collection = await createCollection.mutateAsync({
        project_id: projectId,
        name: name.trim(),
        description: description.trim() || undefined,
      })
      toast.success('Collection created')
      onCreated?.(collection)
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create collection')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Create Collection">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Collection name"
        />
        <Textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Description (optional)"
        />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose} disabled={createCollection.isPending}>Cancel</Button>
          <Button type="submit" loading={createCollection.isPending}>Create</Button>
        </div>
      </form>
    </Dialog>
  )
}
