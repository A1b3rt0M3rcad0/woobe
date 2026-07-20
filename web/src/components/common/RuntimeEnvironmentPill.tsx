import { cn } from '@/lib/utils'

export type OperationalEnvironment = 'draft' | 'staging' | 'production'

const environmentLabels: Record<OperationalEnvironment, string> = {
  draft: 'Draft',
  staging: 'Staging',
  production: 'Production',
}

const liveStyles: Record<OperationalEnvironment, { pill: string; dot: string }> = {
  draft: {
    pill: 'border-blue-500/30 bg-blue-500/10 text-blue-200',
    dot: 'bg-blue-400',
  },
  staging: {
    pill: 'border-indigo-500/30 bg-indigo-500/10 text-indigo-200',
    dot: 'bg-indigo-400',
  },
  production: {
    pill: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    dot: 'bg-emerald-400',
  },
}

export function RuntimeEnvironmentPill({
  environment,
  enabled,
  available = true,
  loading = false,
}: {
  environment: OperationalEnvironment
  enabled?: boolean
  available?: boolean
  loading?: boolean
}) {
  const label = environmentLabels[environment]
  const live = available && enabled === true
  const off = available && enabled === false
  const text = loading
    ? `${label}…`
    : !available
      ? `No ${label}`
      : live
        ? `${label} Live`
        : `${label} Off`

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium',
        loading && 'border-border/80 bg-background/55 text-muted',
        !loading && !available && 'border-border/70 bg-background/35 text-muted/80',
        !loading && off && 'border-slate-500/25 bg-slate-500/[0.08] text-slate-300',
        !loading && live && liveStyles[environment].pill,
      )}
      aria-label={text}
    >
      <span
        className={cn(
          'h-1.5 w-1.5 shrink-0 rounded-full',
          loading && 'bg-slate-500',
          !loading && !available && 'bg-slate-600',
          !loading && off && 'bg-slate-400',
          !loading && live && liveStyles[environment].dot,
        )}
        aria-hidden="true"
      />
      {text}
    </span>
  )
}
