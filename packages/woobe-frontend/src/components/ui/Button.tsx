import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { Button as WoobeButton } from '@woobe/ui'

export const buttonVariants = cva('', {
  variants: {
    variant: {
      default: '',
      destructive: '',
      outline: '',
      secondary: '',
      ghost: '',
      link: '',
    },
    size: {
      xs: '',
      default: '',
      sm: '',
      lg: '',
      icon: '',
      iconSm: '',
      iconXs: '',
    },
  },
  defaultVariants: {
    variant: 'default',
    size: 'default',
  },
})

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'default', size = 'default', loading = false, ...props }, ref) => (
    <WoobeButton
      ref={ref}
      variant={variant ?? 'default'}
      size={size ?? 'default'}
      loading={loading}
      {...props}
    />
  ),
)

Button.displayName = 'Button'

export { Button }
