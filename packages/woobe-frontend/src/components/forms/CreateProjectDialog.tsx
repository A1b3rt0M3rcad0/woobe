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
import { createProjectSchema, type CreateProjectFormData } from '@/features/projects/schemas'

interface CreateProjectDialogProps {
  open: boolean
  onClose: () => void
  onSubmit: (data: { name: string; slug: string }) => Promise<void>
  loading?: boolean
  firstProject?: boolean
}

export function CreateProjectDialog({
  open,
  onClose,
  onSubmit,
  loading,
  firstProject = false,
}: CreateProjectDialogProps) {
  const form = useForm<CreateProjectFormData>({ resolver: zodResolver(createProjectSchema) })
  const nameField = form.register('name')
  const slugField = form.register('slug')

  const handleNameChange = (event: ChangeEvent<HTMLInputElement>) => {
    nameField.onChange(event)
    form.setValue('slug', slugify(event.target.value, 'project'), {
      shouldDirty: true,
      shouldValidate: true,
    })
  }

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
    <Dialog
      open={open}
      onClose={close}
      title={firstProject ? 'Create your first Project' : 'Create Project'}
      className="max-w-[460px]"
    >
      <form onSubmit={form.handleSubmit(submit)} className="space-y-4" noValidate>
        <Field>
          <FieldLabel htmlFor="project-name">Name</FieldLabel>
          <Input
            {...nameField}
            id="project-name"
            autoComplete="off"
            placeholder={firstProject ? 'Customer support platform' : 'Project name'}
            autoFocus
            invalid={Boolean(form.formState.errors.name)}
            aria-describedby={form.formState.errors.name ? 'project-name-error' : undefined}
            onChange={handleNameChange}
          />
          {form.formState.errors.name?.message && (
            <FieldError id="project-name-error">{form.formState.errors.name.message}</FieldError>
          )}
          {firstProject && (
            <FieldDescription className="font-mono text-[9px] leading-4">
              Projects isolate Agents, Knowledge, Tools, credentials, runtime and observability.
            </FieldDescription>
          )}
        </Field>

        {!firstProject && (
          <Field>
            <FieldLabel htmlFor="project-slug">Slug</FieldLabel>
            <Input
              {...slugField}
              id="project-slug"
              readOnly
              aria-readonly="true"
              placeholder="project"
              className="cursor-default font-mono text-[11px] text-muted-foreground"
            />
            <FieldDescription className="font-mono text-[9px] leading-4">
              Generated from the name · unique inside this Workspace
            </FieldDescription>
          </Field>
        )}

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={close}>Cancel</Button>
          <Button type="submit" loading={Boolean(loading) || form.formState.isSubmitting}>
            Create Project
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
