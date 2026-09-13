import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import {
  Button,
  Dialog,
  Field,
  FieldLabel,
  Input,
  SectionBlock,
  TechnicalListItem,
  Textarea,
} from '@woobe/ui'

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
    <Dialog open={open} onClose={onClose} title="Create Collection" className="max-w-dialog" contentClassName="p-0">
      <form onSubmit={handleSubmit}>
        <div className="grid gap-ui-md p-ui-lg">
          <SectionBlock title="Collection information" description="Create the source boundary used to organize documents before vector snapshots are built." density="compact">
            <div className="grid gap-ui-md">
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
                  className="min-h-textarea-compact"
                />
              </Field>
            </div>
          </SectionBlock>

          <div className="grid gap-ui-xs sm:grid-cols-2">
            <TechnicalListItem label="Scope" description="Current Project" />
            <TechnicalListItem label="Lifecycle" description="Documents → vectors → snapshots" />
          </div>
        </div>

        <div className="flex justify-end gap-ui-sm border-t border-border bg-surface/95 px-ui-lg py-ui-md">
          <Button type="button" variant="outline" onClick={onClose} disabled={createCollection.isPending}>Cancel</Button>
          <Button type="submit" loading={createCollection.isPending}>Create Collection</Button>
        </div>
      </form>
    </Dialog>
  )
}
