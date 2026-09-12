import { type HTMLAttributes } from 'react'
import {
  Alert as WoobeAlert,
  AlertDescription as WoobeAlertDescription,
  AlertTitle as WoobeAlertTitle,
  type AlertVariant,
} from '@woobe/ui'
import { AlertCircle, AlertTriangle, CheckCircle2, Info } from 'lucide-react'
import { cn } from '@/lib/utils'

const icons = {
  default: Info,
  destructive: AlertCircle,
  warning: AlertTriangle,
  success: CheckCircle2,
  info: Info,
} satisfies Record<AlertVariant, typeof Info>

interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  variant?: AlertVariant
  icon?: boolean
}

function Alert({ className, variant = 'default', icon = true, children, ...props }: AlertProps) {
  const Icon = icons[variant]
  return (
    <WoobeAlert variant={variant} className={cn('flex items-start gap-ui-sm', className)} {...props}>
      {icon ? <Icon className="mt-ui-hairline h-icon w-icon shrink-0" aria-hidden="true" /> : null}
      <div className="min-w-0 flex-1">{children}</div>
    </WoobeAlert>
  )
}

function AlertTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <WoobeAlertTitle className={className} {...props} />
}

function AlertDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <WoobeAlertDescription className={className} {...props} />
}

export { Alert, AlertTitle, AlertDescription }
