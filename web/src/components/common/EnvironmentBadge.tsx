import { cn } from '@/lib/utils'
import { getEnvironmentAppearance } from '@/lib/environment-appearance'

interface EnvironmentBadgeProps {
  environment: string
  label?: string
  showDot?: boolean
  compact?: boolean
  className?: string
}

export function EnvironmentBadge({
  environment,
  label,
  showDot = true,
  compact = false,
  className,
}: EnvironmentBadgeProps) {
  const appearance = getEnvironmentAppearance(environment)

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border font-medium',
        compact ? 'gap-1 px-1.5 py-0 text-[10px]' : 'gap-1.5 px-2 py-0.5 text-xs',
        appearance?.tone ?? 'border-border/80 bg-background/55 text-muted',
        className,
      )}
    >
      {showDot && (
        <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', appearance?.dot ?? 'bg-slate-400')} />
      )}
      {label ?? appearance?.label ?? environment}
    </span>
  )
}
