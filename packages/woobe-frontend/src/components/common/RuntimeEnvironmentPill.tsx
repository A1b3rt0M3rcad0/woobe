import { Badge, type BadgeVariant } from '@woobe/ui'
import { cn } from '@/lib/utils'

export type OperationalEnvironment = 'draft' | 'staging' | 'production'

const environmentLabels: Record<OperationalEnvironment, string> = {
  draft: 'Draft',
  staging: 'Staging',
  production: 'Production',
}

const enabledVariant: Record<OperationalEnvironment, BadgeVariant> = {
  draft: 'secondary',
  staging: 'default',
  production: 'success',
}

const enabledDot: Record<OperationalEnvironment, string> = {
  draft: 'bg-slate-400',
  staging: 'bg-primary',
  production: 'bg-success',
}

export function RuntimeEnvironmentPill({
  environment,
  enabled,
  available = true,
  loading = false,
  unknown = false,
}: {
  environment: OperationalEnvironment
  enabled?: boolean
  available?: boolean
  loading?: boolean
  unknown?: boolean
}) {
  unknown = unknown || (available && enabled === undefined && !loading)
  const label = environmentLabels[environment]
  const isEnabled = available && enabled === true && !unknown
  const off = available && enabled === false && !unknown
  const neutral = loading || unknown
  const text = loading
    ? `${label}…`
    : unknown
      ? `${label} Unknown`
      : !available
        ? `No ${label}`
        : isEnabled
          ? `${label} Enabled`
          : `${label} Off`
  const variant: BadgeVariant = neutral || !available || off ? 'outline' : enabledVariant[environment]

  return (
    <Badge
      variant={variant}
      size="compact"
      className="font-medium normal-case tracking-normal"
      aria-label={text}
    >
      <span
        className={cn(
          'h-ui-xs w-ui-xs shrink-0 rounded-full',
          neutral && 'bg-slate-500',
          !neutral && !available && 'bg-slate-600',
          !neutral && off && 'bg-slate-500',
          !neutral && isEnabled && enabledDot[environment],
          loading && 'animate-pulse',
        )}
        aria-hidden="true"
      />
      {text}
    </Badge>
  )
}
