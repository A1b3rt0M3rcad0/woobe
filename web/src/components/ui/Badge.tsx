import { type HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary/20 text-primary-light',
        secondary: 'border-transparent bg-accent text-accent-foreground',
        destructive: 'border-transparent bg-red-500/20 text-red-400',
        success: 'border-transparent bg-emerald-500/20 text-emerald-400',
        warning: 'border-transparent bg-yellow-500/20 text-yellow-400',
        outline: 'text-muted-foreground',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

interface BadgeProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
