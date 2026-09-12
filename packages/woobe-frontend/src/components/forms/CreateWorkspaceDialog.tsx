import type { ChangeEvent } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  Button,
  Dialog,
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
  Input,
} from '@woobe/ui'

import { slugify } from '@/lib/slug'
import { createWorkspaceSchema, type CreateWorkspaceFormData } from '@/features/workspaces/schemas'

interface CreateWorkspaceDialogProps {
  open: boolean
  onClose: () => void
  onSubmit: (data: { name: string; slug: string }) => Promise<void>
  loading?: boolean
}

export function CreateWorkspaceDialog({ open, onClose, onSubmit, loading }: CreateWorkspaceDialogProps) {
  const form = useForm<CreateWorkspaceFormData>({ resolver: zodResolver(createWorkspaceSchema) })
  const nameField = form.register('name')
  const slugField = form.register('slug')

  const handleNameChange = (event: ChangeEvent<HTMLInputElement>) => {
    nameField.onChange(event)
    form.setValue('slug', slugify(event.target.value, 'workspace'), {
      shouldDirty: true,
      shouldValidate: true,
    })
  }

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
    <Dialog open={open} onClose={close} title="Create Workspace" className="max-w-[460px]">
      <form onSubmit={form.handleSubmit(submit)} className="space-y-4" noValidate>
        <Field>
          <FieldLabel htmlFor="workspace-name">Name</FieldLabel>
          <Input
            {...nameField}
            id="workspace-name"
            autoComplete="off"
            placeholder="Workspace name"
            invalid={Boolean(form.formState.errors.name)}
            aria-describedby={form.formState.errors.name ? 'workspace-name-error' : undefined}
            onChange={handleNameChange}
          />
          {form.formState.errors.name?.message && (
            <FieldError id="workspace-name-error">{form.formState.errors.name.message}</FieldError>
          )}
        </Field>

        <Field>
          <FieldLabel htmlFor="workspace-slug">Slug</FieldLabel>
          <Input
            {...slugField}
            id="workspace-slug"
            readOnly
            aria-readonly="true"
            placeholder="workspace"
            className="cursor-default font-mono text-[11px] text-muted-foreground"
          />
          <FieldDescription className="font-mono text-[9px] leading-4">
            Generated from the name · globally unique
          </FieldDescription>
        </Field>

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={close}>Cancel</Button>
          <Button type="submit" loading={Boolean(loading) || form.formState.isSubmitting}>Create</Button>
        </div>
      </form>
    </Dialog>
  )
}
