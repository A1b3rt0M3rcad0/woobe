import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { Plus } from 'lucide-react'
import { cn } from '../lib/cn'

export type CreateResourceCardSize = 'sm' | 'md' | 'lg'

export interface CreateResourceCardProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'title'> {
  title: ReactNode
  description: ReactNode
  size?: CreateResourceCardSize
}

const sizeClasses: Record<CreateResourceCardSize, string> = {
  sm: 'min-h-[8.25rem]',
  md: 'min-h-[9.5rem]',
  lg: 'min-h-[11rem]',
}

const CreateResourceCard = forwardRef<HTMLButtonElement, CreateResourceCardProps>(
  ({ title, description, size = 'md', className, disabled, type = 'button', ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      disabled={disabled}
      className={cn(
        'group flex flex-col items-start justify-center rounded-container border border-dashed border-border bg-surface/35 p-ui-lg text-left transition-colors',
        'hover:border-primary/45 hover:bg-primary/[0.035] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30',
        'disabled:cursor-not-allowed disabled:opacity-45',
        sizeClasses[size],
        className,
      )}
      {...props}
    >
      <span className="flex h-control-segment w-control-segment items-center justify-center rounded-control border border-primary/30 bg-primary/[0.07] text-primary-light">
        <Plus className="h-icon w-icon" />
      </span>
      <span className="mt-ui-md font-mono text-system-heading font-semibold text-accent-foreground">{title}</span>
      <span className="mt-ui-xs max-w-sm font-sans text-product-small text-muted-foreground">{description}</span>
    </button>
  ),
)
CreateResourceCard.displayName = 'CreateResourceCard'

export { CreateResourceCard }
