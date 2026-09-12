import type { UseFormReturn } from 'react-hook-form'
import { ArrowRight, Bot, Circle, FolderKanban } from 'lucide-react'
import { Field, FieldDescription, FieldLabel, SectionBlock } from '@woobe/ui'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { ScrollArea } from '@/components/ui/ScrollArea'
import type { CreateProjectFormData } from '@/features/projects/schemas'

interface FirstRunProjectStepProps {
  form: UseFormReturn<CreateProjectFormData>
  pending: boolean
  onSubmit: (data: CreateProjectFormData) => Promise<void>
}

export function FirstRunProjectStep({ form, pending, onSubmit }: FirstRunProjectStepProps) {
  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="grid min-h-[420px] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden rounded-container border border-border bg-surface/55 lg:h-full lg:min-h-0">
      <header className="flex items-start gap-3 border-b border-border px-5 py-4 sm:px-6">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light"><FolderKanban className="h-3.5 w-3.5" /></div>
        <div><p className="font-mono text-[9px] uppercase tracking-[0.16em] text-primary-light">Project setup</p><h2 className="mt-1 font-mono text-[13px] font-semibold text-slate-100">Create the Project for your Agent</h2><p className="mt-1 max-w-2xl font-sans text-xs leading-5 text-muted">Define the technical boundary that will contain the Agent and its operational resources.</p></div>
      </header>

      <ScrollArea className="min-h-0 px-5 py-5 sm:px-6">
        <div className="max-w-3xl space-y-4">
          <Field error={form.formState.errors.name?.message}>
            <FieldLabel>Project name</FieldLabel>
            <Input {...form.register('name')} placeholder="Customer support platform" autoFocus />
            <FieldDescription>Use the product, team or technical boundary this Project will represent.</FieldDescription>
          </Field>

          <SectionBlock title="What happens next" density="compact">
            <div className="grid divide-y divide-border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
              {[{ icon: Circle, title: 'Project', text: 'Create the isolation boundary.', tone: 'text-primary-light' }, { icon: Bot, title: 'Agent', text: 'Define instructions and model.', tone: 'text-muted' }, { icon: ArrowRight, title: 'Playground', text: 'Run the first operational test.', tone: 'text-muted' }].map((item) => {
                const Icon = item.icon
                return <div key={item.title} className="flex gap-2.5 px-3 py-2.5 first:pl-0 last:pr-0"><Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${item.tone}`} /><div><p className="font-mono text-[10px] font-medium text-slate-200">{item.title}</p><p className="mt-0.5 font-sans text-[11px] leading-4 text-muted">{item.text}</p></div></div>
              })}
            </div>
          </SectionBlock>
        </div>
      </ScrollArea>

      <footer className="flex items-center justify-end border-t border-border px-5 py-3 sm:px-6">
        <Button type="submit" loading={pending}>Create Project and continue<ArrowRight className="ml-1.5 h-3.5 w-3.5" /></Button>
      </footer>
    </form>
  )
}
