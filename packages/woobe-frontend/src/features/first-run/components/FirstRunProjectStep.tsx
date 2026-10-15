import type { UseFormReturn } from 'react-hook-form'
import { ArrowRight } from 'lucide-react'
import { Button, Field, FieldDescription, FieldLabel } from '@woobe/ui'
import { Input } from '@/components/ui/Input'
import type { CreateProjectFormData } from '@/features/projects/schemas'

interface FirstRunProjectStepProps {
  form: UseFormReturn<CreateProjectFormData>
  pending: boolean
  onSubmit: (data: CreateProjectFormData) => Promise<void>
}
export function FirstRunProjectStep({ form, pending, onSubmit }: FirstRunProjectStepProps) {
  return <form onSubmit={form.handleSubmit(onSubmit)} className="overflow-hidden rounded-container border border-border bg-surface">
    <header className="border-b border-border px-5 py-5 sm:px-6">
      <h2 className="font-serif text-editorial-section font-normal text-foreground">Create a Project</h2>
      <p className="mt-2 text-sm leading-5 text-muted-foreground">Keep this Agent, its models, credentials and Run history together.</p>
    </header>
    <div className="space-y-6 px-5 py-6 sm:px-6">
      <Field><FieldLabel htmlFor="first-project-name">Project name</FieldLabel><Input id="first-project-name" {...form.register('name')} error={form.formState.errors.name?.message} aria-describedby="first-project-help" placeholder="e.g. Customer support" autoFocus /><FieldDescription id="first-project-help" className="text-sm leading-5">Use your product or team name. You can create more Projects later.</FieldDescription></Field>
      <p className="text-sm leading-6 text-muted-foreground">Next, you will define your Agent’s purpose and choose a model. Creating the Project does not send a model request or deploy anything.</p>
    </div>
    <footer className="flex justify-end border-t border-border px-5 py-4 sm:px-6"><Button type="submit" loading={pending}>Create Project and continue<ArrowRight className="h-3.5 w-3.5" /></Button></footer>
  </form>
}
