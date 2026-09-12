import { cn } from '@/lib/utils'

export type OperationalEnvironment = 'draft' | 'staging' | 'production'

const environmentLabels: Record<OperationalEnvironment, string> = {
  draft: 'Draft',
  staging: 'Staging',
  production: 'Production',
}

const liveStyles: Record<OperationalEnvironment, { pill: string; dot: string }> = {
  draft: {
    pill: 'border-slate-500/30 bg-slate-500/[0.08] text-slate-300',
    dot: 'bg-slate-400',
  },
  staging: {
    pill: 'border-indigo-500/30 bg-indigo-500/[0.08] text-indigo-200',
    dot: 'bg-indigo-400',
  },
  production: {
    pill: 'border-emerald-500/30 bg-emerald-500/[0.08] text-emerald-300',
    dot: 'bg-emerald-400',
  },
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

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-technical border px-2 py-1 font-mono text-[8px] font-medium leading-none',
        neutral && 'border-border bg-control/70 text-muted-foreground',
        !neutral && !available && 'border-border/80 bg-control/40 text-muted-foreground/80',
        !neutral && off && 'border-slate-500/25 bg-slate-500/[0.06] text-slate-400',
        !neutral && live && liveStyles[environment].pill,
      )}
      aria-label={text}
    >
      <span
        className={cn(
          'h-1.5 w-1.5 shrink-0 rounded-full',
          neutral && 'bg-slate-500',
          !neutral && !available && 'bg-slate-600',
          !neutral && off && 'bg-slate-500',
          !neutral && live && liveStyles[environment].dot,
        )}
        aria-hidden="true"
      />
      {text}
    </span>
  )
}
