import { type HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { Badge as WoobeBadge, type BadgeVariant as WoobeBadgeVariant } from '@woobe/ui'

export const badgeVariants = cva('', {
  variants: {
    variant: {
      default: '',
      secondary: '',
      destructive: '',
      success: '',
      warning: '',
      outline: '',
    },
  },
  defaultVariants: {
    variant: 'default',
  },
})

interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

const variantMap: Record<NonNullable<BadgeProps['variant']>, WoobeBadgeVariant> = {
  default: 'default',
  secondary: 'outline',
  destructive: 'destructive',
  success: 'success',
  warning: 'warning',
  outline: 'outline',
}

function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return <WoobeBadge variant={variantMap[variant ?? 'default']} className={className} {...props} />
}

export { Badge }
