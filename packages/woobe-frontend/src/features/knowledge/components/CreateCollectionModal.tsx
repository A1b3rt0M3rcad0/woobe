import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button, Dialog, Field, FieldLabel, Input, Textarea } from '@woobe/ui'
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
    <Dialog open={open} onClose={onClose} title="Create Collection" className="max-w-[560px]" contentClassName="p-0">
      <form onSubmit={handleSubmit}>
        <div className="space-y-4 p-5">
          <Field>
            <FieldLabel htmlFor="create-collection-name">Name</FieldLabel>
            <Input
              id="create-collection-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Collection name"
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="create-collection-description">Description</FieldLabel>
            <Textarea
              id="create-collection-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Description (optional)"
              className="min-h-[110px]"
            />
          </Field>
          <div className="grid gap-px overflow-hidden rounded-container border border-border bg-border sm:grid-cols-2">
            <div className="bg-control/70 p-3">
              <p className="font-mono text-[8px] uppercase tracking-[0.1em] text-muted-foreground">Scope</p>
              <p className="mt-1 font-mono text-[9px] text-slate-300">Current Project</p>
            </div>
            <div className="bg-control/70 p-3">
              <p className="font-mono text-[8px] uppercase tracking-[0.1em] text-muted-foreground">Lifecycle</p>
              <p className="mt-1 font-mono text-[9px] text-slate-300">Documents → vectors → snapshots</p>
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 border-t border-border bg-control/35 px-5 py-3">
          <Button type="button" variant="outline" onClick={onClose} disabled={createCollection.isPending}>Cancel</Button>
          <Button type="submit" loading={createCollection.isPending}>Create Collection</Button>
        </div>
      </form>
    </Dialog>
  )
}
