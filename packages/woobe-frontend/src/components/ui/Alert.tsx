import { type ReactNode } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'
import { AlertCircle, AlertTriangle, Info, CheckCircle2 } from 'lucide-react'

const alertVariants = cva(
  'relative w-full rounded-lg border p-4 text-sm',
  {
    variants: {
      variant: {
        default: 'bg-surface border-border text-white',
        destructive: 'border-red-500/50 bg-red-500/10 text-red-400',
        warning: 'border-yellow-500/50 bg-yellow-500/10 text-yellow-400',
        success: 'border-emerald-500/50 bg-emerald-500/10 text-emerald-400',
        info: 'border-primary/50 bg-primary/10 text-primary-light',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

const icons = {
  default: Info,
  destructive: AlertCircle,
  warning: AlertTriangle,
  success: CheckCircle2,
  info: Info,
}

interface AlertProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {
  icon?: boolean
}

function Alert({ className, variant, icon = true, children, ...props }: AlertProps) {
  const Icon = icons[variant || 'default']
  return (
    <div className={cn(alertVariants({ variant }), className)} {...props}>
      {icon && <Icon className="absolute left-4 top-4 h-4 w-4" />}
      <div className={cn(icon && 'pl-6')}>{children}</div>
    </div>
  )
}

const AlertTitle = ({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
  <h5 className={cn('mb-1 font-medium leading-none tracking-tight', className)} {...props} />
)

const AlertDescription = ({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
  <div className={cn('text-sm opacity-90', className)} {...props} />
)

export { Alert, AlertTitle, AlertDescription }
