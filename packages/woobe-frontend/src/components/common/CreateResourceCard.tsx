import { Plus } from 'lucide-react'
import type { ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

type CreateResourceCardProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  title: string
  description: string
  minHeight?: 'sm' | 'md' | 'lg'
}

const minHeightClass: Record<NonNullable<CreateResourceCardProps['minHeight']>, string> = {
  sm: 'min-h-[132px]',
  md: 'min-h-[152px]',
  lg: 'min-h-[176px]',
}

export function CreateResourceCard({ title, description, minHeight = 'md', className, disabled, type = 'button', ...props }: CreateResourceCardProps) {
  return (
    <button
      type={type}
      disabled={disabled}
      className={cn(
        'group flex flex-col items-start justify-center rounded-container border border-dashed border-border bg-surface/35 p-4 text-left transition-colors',
        'hover:border-primary/45 hover:bg-primary/[0.035] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30',
        'disabled:cursor-not-allowed disabled:opacity-45',
        minHeightClass[minHeight],
        className,
      )}
      {...props}
    >
      <span className="flex h-7 w-7 items-center justify-center rounded-control border border-primary/30 bg-primary/[0.07] text-primary-light">
        <Plus className="h-3.5 w-3.5" />
      </span>
      <span className="mt-3 font-mono text-[11px] font-semibold text-slate-100">{title}</span>
      <span className="mt-1 max-w-[300px] font-sans text-xs leading-5 text-muted">{description}</span>
    </button>
  )
}
