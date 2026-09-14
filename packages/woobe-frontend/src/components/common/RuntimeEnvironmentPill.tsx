import { Badge, type BadgeVariant } from '@woobe/ui'
import { cn } from '@/lib/utils'

export type OperationalEnvironment = 'draft' | 'staging' | 'production'

const environmentLabels: Record<OperationalEnvironment, string> = {
  draft: 'Draft',
  staging: 'Staging',
  production: 'Production',
}

const liveVariant: Record<OperationalEnvironment, BadgeVariant> = {
  draft: 'secondary',
  staging: 'default',
  production: 'success',
}

const liveDot: Record<OperationalEnvironment, string> = {
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
  const label = environmentLabels[environment]
  const live = available && enabled === true && !unknown
  const off = available && enabled === false && !unknown
  const neutral = loading || unknown
  const text = loading
    ? `${label}…`
    : unknown
      ? `${label} Unknown`
      : !available
        ? `No ${label}`
        : live
          ? `${label} Live`
          : `${label} Off`
  const variant: BadgeVariant = neutral || !available || off ? 'outline' : liveVariant[environment]

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
          !neutral && live && liveDot[environment],
          loading && 'animate-pulse',
        )}
        aria-hidden="true"
      />
      {text}
    </Badge>
  )
}