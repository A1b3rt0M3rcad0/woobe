import type { CSSProperties } from 'react'
import { cn } from '../lib/cn'

export interface DotMeterProps {
  value: number | null
  label: string
  tone?: 'accent' | 'success' | 'warning' | 'danger' | 'neutral'
  className?: string
}

/** Percent of a stated denominator. Unknown is distinct from zero; only the graphic is clamped. */
export function DotMeter({ value, label, tone = 'accent', className }: DotMeterProps) {
  const known = value !== null && Number.isFinite(value)
  const fill = known ? Math.min(100, Math.max(0, value)) : 0
  return <div className={cn('woobe-dot-meter', className)} data-tone={known ? tone : 'neutral'}
    role={known ? 'meter' : 'img'} aria-label={known ? label : `${label}: unavailable`}
    aria-valuemin={known ? 0 : undefined} aria-valuemax={known ? 100 : undefined}
    aria-valuenow={known ? fill : undefined} aria-valuetext={known ? `${value}%` : undefined}
    style={{ '--meter-fill': `${fill}%` } as CSSProperties}><span aria-hidden="true" /></div>
}
