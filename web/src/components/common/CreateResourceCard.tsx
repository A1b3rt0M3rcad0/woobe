import { Plus } from 'lucide-react'
import type { ButtonHTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

type CreateResourceCardProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  title: string
  description: string
  minHeight?: 'sm' | 'md' | 'lg'
}

const minHeightClass: Record<NonNullable<CreateResourceCardProps['minHeight']>, string> = {
  sm: 'min-h-[220px]',
  md: 'min-h-[250px]',
  lg: 'min-h-[260px]',
}

export function CreateResourceCard({
  title,
  description,
  minHeight = 'md',
  className,
  disabled,
  type = 'button',
  ...props
}: CreateResourceCardProps) {
  return (
    <button
      type={type}
      disabled={disabled}
      className={cn(
        'group flex flex-col items-center justify-center rounded-xl border border-dashed border-primary/40 bg-surface/35 p-6 text-center transition-[border-color,background-color,box-shadow] duration-200',
        'hover:border-primary/60 hover:bg-primary/5 hover:shadow-lg hover:shadow-primary/5',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background',
        'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-primary/40 disabled:hover:bg-surface/35 disabled:hover:shadow-none',
        minHeightClass[minHeight],
        className,
      )}
      {...props}
    >
      <span className="flex h-14 w-14 items-center justify-center rounded-full border border-primary/50 bg-primary/10 text-primary-light transition-colors duration-200 group-hover:bg-primary/15">
        <Plus className="h-6 w-6" />
      </span>
      <span className="mt-5 text-base font-semibold text-white">{title}</span>
      <span className="mt-2 max-w-[260px] text-sm leading-6 text-muted">{description}</span>
    </button>
  )
}
