import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { NameSlugFields } from './NameSlugFields'
import { slugify } from '@/lib/slug'
import { createOrganizationSchema, type CreateOrganizationFormData } from '@/features/organizations/schemas'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'

interface CreateOrganizationDialogProps {
  open: boolean
  onClose: () => void
  onSubmit: (data: { name: string; slug: string }) => Promise<void>
  loading?: boolean
}

export function CreateOrganizationDialog({ open, onClose, onSubmit, loading }: CreateOrganizationDialogProps) {
  const form = useForm<CreateOrganizationFormData>({ resolver: zodResolver(createOrganizationSchema) })

  const submit = async (data: CreateOrganizationFormData) => {
    await onSubmit({
      name: data.name.trim(),
      slug: slugify(data.slug || data.name, 'organization'),
    })
    form.reset()
  }

  const close = () => {
    form.reset()
    onClose()
  }

  return (
    <Dialog open={open} onClose={close} title="Create Organization">
      <form onSubmit={form.handleSubmit(submit)} className="space-y-4">
        <NameSlugFields
          form={form}
          namePath="name"
          slugPath="slug"
          namePlaceholder="Organization name"
          fallback="organization"
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
