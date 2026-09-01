import type { UseFormReturn } from 'react-hook-form'
import { ArrowRight, Bot, Circle, FolderKanban, Rocket } from 'lucide-react'

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
    <form
      onSubmit={form.handleSubmit(onSubmit)}
      className="grid min-h-[520px] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden rounded-2xl border border-border/90 bg-surface/60 shadow-xl shadow-black/10 lg:h-full lg:min-h-0"
    >
      <header className="border-b border-border/80 px-6 py-5 sm:px-8">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
            <FolderKanban className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-primary-light">Project setup</p>
            <h2 className="mt-1.5 text-xl font-semibold text-white">Create the Project for your Agent</h2>
            <p className="mt-1.5 max-w-2xl text-sm leading-6 text-muted">
              Define the technical boundary that will contain the Agent and its operational resources.
            </p>
          </div>
        </div>
      </header>

      <ScrollArea className="min-h-0 px-6 py-6 sm:px-8 sm:py-8">
        <div className="max-w-3xl space-y-7">
          <div>
            <label className="mb-2 block text-sm font-medium text-white">Project name</label>
            <Input
              {...form.register('name')}
              error={form.formState.errors.name?.message}
              placeholder="Customer support platform"
              autoFocus
              className="h-10"
            />
            <p className="mt-2 text-xs leading-5 text-muted">
              Use the product, team or technical boundary this Project will represent.
            </p>
          </div>

          <div className="grid gap-3 rounded-xl border border-border/80 bg-background/50 p-4 sm:grid-cols-3">
            <div className="flex items-start gap-3">
              <Circle className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />
              <div>
                <p className="text-sm font-medium text-white">Project</p>
                <p className="mt-1 text-xs leading-5 text-muted">Create the isolation boundary.</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Bot className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
              <div>
                <p className="text-sm font-medium text-white">Agent</p>
                <p className="mt-1 text-xs leading-5 text-muted">Define instructions and model.</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Rocket className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
              <div>
                <p className="text-sm font-medium text-white">Playground</p>
                <p className="mt-1 text-xs leading-5 text-muted">Run the first operational test.</p>
              </div>
            </div>
          </div>
        </div>
      </ScrollArea>

      <footer className="flex items-center justify-end border-t border-border/80 px-6 py-4 sm:px-8">
        <Button type="submit" loading={pending}>
          Create Project and continue
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </footer>
    </form>
  )
}
