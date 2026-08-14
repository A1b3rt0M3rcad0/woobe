import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { NameSlugFields } from './NameSlugFields'
import { slugify } from '@/lib/slug'
import { createWorkspaceSchema, type CreateWorkspaceFormData } from '@/features/workspaces/schemas'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'

interface CreateWorkspaceDialogProps {
  open: boolean
  onClose: () => void
  onSubmit: (data: { name: string; slug: string }) => Promise<void>
  loading?: boolean
}

export function CreateWorkspaceDialog({ open, onClose, onSubmit, loading }: CreateWorkspaceDialogProps) {
  const form = useForm<CreateWorkspaceFormData>({ resolver: zodResolver(createWorkspaceSchema) })

  const submit = async (data: CreateWorkspaceFormData) => {
    await onSubmit({
      name: data.name.trim(),
      slug: slugify(data.slug || data.name, 'workspace'),
    })
    form.reset()
  }

  const close = () => {
    form.reset()
    onClose()
  }

  return (
    <Dialog open={open} onClose={close} title="Create Workspace">
      <form onSubmit={form.handleSubmit(submit)} className="space-y-4">
        <NameSlugFields
          form={form}
          namePath="name"
          slugPath="slug"
          namePlaceholder="Workspace name"
          fallback="workspace"
          uniqueScope="globally"
          lockSlug
        />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={close}>Cancel</Button>
          <Button type="submit" loading={loading}>Create</Button>
        </div>
      </form>
    </Dialog>
  )
}
