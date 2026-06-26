import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { NameSlugFields } from './NameSlugFields'
import { slugify } from '@/lib/slug'
import { createProjectSchema, type CreateProjectFormData } from '@/features/projects/schemas'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'

interface CreateProjectDialogProps {
  open: boolean
  onClose: () => void
  onSubmit: (data: { name: string; slug: string }) => Promise<void>
  loading?: boolean
}

export function CreateProjectDialog({ open, onClose, onSubmit, loading }: CreateProjectDialogProps) {
  const form = useForm<CreateProjectFormData>({ resolver: zodResolver(createProjectSchema) })

  const submit = async (data: CreateProjectFormData) => {
    await onSubmit({
      name: data.name.trim(),
      slug: slugify(data.slug || data.name, 'project'),
    })
    form.reset()
  }

  const close = () => {
    form.reset()
    onClose()
  }

  return (
    <Dialog open={open} onClose={close} title="Create Project">
      <form onSubmit={form.handleSubmit(submit)} className="space-y-4">
        <NameSlugFields
          form={form}
          namePath="name"
          slugPath="slug"
          namePlaceholder="Project name"
          fallback="project"
          uniqueScope="inside this organization"
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
