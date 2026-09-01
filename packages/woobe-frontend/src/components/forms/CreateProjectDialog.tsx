import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
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
  firstProject?: boolean
}

export function CreateProjectDialog({ open, onClose, onSubmit, loading, firstProject = false }: CreateProjectDialogProps) {
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
    <Dialog open={open} onClose={close} title={firstProject ? 'Create your first Project' : 'Create Project'}>
      <form onSubmit={form.handleSubmit(submit)} className="space-y-4">
        {firstProject ? (
          <div>
            <label className="mb-1.5 block text-sm font-medium text-muted">Project name</label>
            <Input
              {...form.register('name')}
              error={form.formState.errors.name?.message}
              placeholder="Customer support platform"
              autoFocus
            />
            <p className="mt-1.5 text-xs leading-5 text-muted">Projects isolate Agents, Knowledge, Tools, credentials, runtime and observability.</p>
          </div>
        ) : (
          <NameSlugFields
            form={form}
            namePath="name"
            slugPath="slug"
            namePlaceholder="Project name"
            fallback="project"
            uniqueScope="inside this workspace"
            lockSlug
          />
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={close}>Cancel</Button>
          <Button type="submit" loading={loading}>{firstProject ? 'Create Project' : 'Create'}</Button>
        </div>
      </form>
    </Dialog>
  )
}
