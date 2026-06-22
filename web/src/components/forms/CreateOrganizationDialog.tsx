import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { NameSlugFields } from './NameSlugFields'
import { createOrganizationSchema, type CreateOrganizationFormData } from '@/features/organizations/schemas'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'

interface CreateOrganizationDialogProps {
  open: boolean
  onClose: () => void
}

export function CreateOrganizationDialog({ open, onClose }: CreateOrganizationDialogProps) {
  const form = useForm<CreateOrganizationFormData>({ resolver: zodResolver(createOrganizationSchema) })

  return (
    <Dialog open={open} onClose={onClose} title="Create Organization">
      <form className="space-y-4">
        <NameSlugFields
          form={form}
          namePath="name"
          slugPath="slug"
          namePlaceholder="Organization name"
          fallback="organization"
          uniqueScope="globally"
        />
        <Button>Create</Button>
      </form>
    </Dialog>
  )
}
