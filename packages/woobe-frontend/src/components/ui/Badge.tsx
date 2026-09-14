import { type HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import {
  Badge as WoobeBadge,
  type BadgeSize as WoobeBadgeSize,
  type BadgeVariant as WoobeBadgeVariant,
} from '@woobe/ui'

export const badgeVariants = cva('', {
  variants: {
    variant: {
      default: '',
      secondary: '',
      destructive: '',
      success: '',
      warning: '',
      outline: '',
      network: '',
    },
    size: {
      compact: '',
      default: '',
    },
  },
  defaultVariants: {
    variant: 'default',
    size: 'default',
  },
})

interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

const variantMap: Record<NonNullable<BadgeProps['variant']>, WoobeBadgeVariant> = {
  default: 'default',
  secondary: 'secondary',
  destructive: 'destructive',
  success: 'success',
  warning: 'warning',
  outline: 'outline',
  network: 'network',
}

function Badge({ className, variant = 'default', size = 'default', ...props }: BadgeProps) {
  return (
    <WoobeBadge
      variant={variantMap[variant ?? 'default']}
      size={(size ?? 'default') as WoobeBadgeSize}
      className={className}
      {...props}
    />
  )
}

export { Badge }