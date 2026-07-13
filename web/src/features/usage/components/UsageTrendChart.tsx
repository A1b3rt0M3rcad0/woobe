import { useEffect, useMemo, useState } from 'react'
import { CalendarRange, CircleGauge, MousePointerClick, TrendingUp } from 'lucide-react'

import type { ProjectUsageTimeseriesPoint, UsageBucket } from '../types'
import { formatKnownMoney } from '@/lib/formatters/money'
import { cn } from '@/lib/utils'

export type UsageTrendMode = 'cost' | 'requests' | 'tokens' | 'llm_calls'

const modes: Array<{ value: UsageTrendMode; label: string }> = [
  { value: 'cost', label: 'Spend' },
  { value: 'requests', label: 'Requests' },
  { value: 'tokens', label: 'Tokens' },
  { value: 'llm_calls', label: 'LLM calls' },
]

function valueFor(point: ProjectUsageTimeseriesPoint, mode: UsageTrendMode) {
  if (mode === 'cost') return point.known_cost_usd ?? 0
  if (mode === 'requests') return point.runtime_requests
  if (mode === 'llm_calls') return point.llm_calls
  return point.input_tokens + point.output_tokens
}

function formatValue(value: number, mode: UsageTrendMode) {
  if (mode === 'cost') return formatKnownMoney(value)
  return new Intl.NumberFormat('en-US', {
    notation: value >= 10_000 ? 'compact' : 'standard',
    maximumFractionDigits: 1,
  }).format(value)
}

function formatBucket(value: string, bucket: UsageBucket, detailed = false) {
  const date = new Date(value)
  return new Intl.DateTimeFormat('en-US', bucket === 'hour'
    ? { month: 'short', day: 'numeric', hour: '2-digit', minute: detailed ? '2-digit' : undefined }
    : { month: 'short', day: 'numeric', year: detailed ? 'numeric' : undefined }).format(date)
}

function successRate(point: ProjectUsageTimeseriesPoint) {
  return point.runtime_requests
    ? (point.successful_requests / point.runtime_requests) * 100
    : 0
}

export function UsageTrendChart({
  points,
  mode,
  bucket,
  contextLabel,
  onModeChange,
}: {
  points: ProjectUsageTimeseriesPoint[]
  mode: UsageTrendMode
  bucket: UsageBucket
  contextLabel: string
  onModeChange: (mode: UsageTrendMode) => void
}) {
  const [selectedIndex, setSelectedIndex] = useState(Math.max(points.length - 1, 0))

  useEffect(() => {
    setSelectedIndex(Math.max(points.length - 1, 0))
  }, [points])

  const values = points.map((point) => valueFor(point, mode))
  const max = Math.max(...values, 1)
  const width = 1000
  const height = 220
  const paddingX = 18
  const paddingY = 18
  const drawableWidth = width - paddingX * 2
  const drawableHeight = height - paddingY * 2
  const coordinates = values.map((value, index) => ({
    x: paddingX + (points.length <= 1 ? drawableWidth / 2 : (index / (points.length - 1)) * drawableWidth),
    y: paddingY + drawableHeight - (value / max) * drawableHeight,
  }))
  const line = coordinates.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')
  const area = coordinates.length
    ? `${line} L ${coordinates[coordinates.length - 1].x} ${height - paddingY} L ${coordinates[0].x} ${height - paddingY} Z`
    : ''
  const total = values.reduce((sum, value) => sum + value, 0)
  const tickIndexes = Array.from(new Set([0, Math.floor((points.length - 1) / 2), points.length - 1])).filter((index) => index >= 0)
  const selectedPoint = points[selectedIndex]

  const highlights = useMemo(() => {
    if (!points.length) return []
    const peakIndex = values.reduce((best, value, index) => value > values[best] ? index : best, 0)
    const busiestIndex = points.reduce(
      (best, point, index) => point.runtime_requests > points[best].runtime_requests ? index : best,
      0,
    )
    const eligible = points
      .map((point, index) => ({ point, index }))
      .filter(({ point }) => point.runtime_requests > 0)
    const lowestSuccess = eligible.length
      ? eligible.reduce(
          (best, current) => successRate(current.point) < successRate(best.point) ? current : best,
        )
      : undefined

    return [
      {
        label: `Peak ${modes.find((item) => item.value === mode)?.label.toLowerCase() ?? mode}`,
        period: formatBucket(points[peakIndex].bucket_start, bucket),
        value: formatValue(values[peakIndex], mode),
      },
      {
        label: 'Highest request volume',
        period: formatBucket(points[busiestIndex].bucket_start, bucket),
        value: formatValue(points[busiestIndex].runtime_requests, 'requests'),
      },
      ...(lowestSuccess
        ? [{
            label: 'Lowest success rate',
            period: formatBucket(lowestSuccess.point.bucket_start, bucket),
            value: `${successRate(lowestSuccess.point).toFixed(1)}%`,
          }]
        : []),
    ]
  }, [bucket, mode, points, values])

  return (
    <section className="overflow-hidden rounded-xl border border-border/90 bg-surface/70">
      <div className="flex flex-col gap-4 border-b border-border px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-white">What changed over time?</h2>
          <p className="mt-1 text-xs text-muted">{contextLabel} Click any point to inspect the exact period.</p>
        </div>
        <div className="inline-flex w-fit rounded-lg border border-border/80 bg-background/45 p-1">
          {modes.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => onModeChange(item.value)}
              className={cn(
                'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                item.value === mode ? 'bg-primary/15 text-primary-light' : 'text-muted hover:text-white',
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="relative min-h-[290px] overflow-hidden rounded-lg border border-border/70 bg-background/25 p-3">
          <svg viewBox={`0 0 ${width} ${height}`} className="h-[230px] w-full" preserveAspectRatio="none" role="img" aria-label={`${mode} usage trend`}>
            {[0.25, 0.5, 0.75].map((ratio) => (
              <line
                key={ratio}
                x1={paddingX}
                x2={width - paddingX}
                y1={paddingY + drawableHeight * ratio}
                y2={paddingY + drawableHeight * ratio}
                className="stroke-border/60"
                strokeWidth="1"
                vectorEffect="non-scaling-stroke"
              />
            ))}
            {area && <path d={area} className="fill-primary/10" />}
            {line && <path d={line} fill="none" className="stroke-primary" strokeWidth="2" vectorEffect="non-scaling-stroke" />}
            {coordinates.map((point, index) => (
              <circle
                key={points[index]?.bucket_start ?? index}
                cx={point.x}
                cy={point.y}
                r={selectedIndex === index ? 5 : 3}
                role="button"
                tabIndex={0}
                aria-label={`Inspect ${formatBucket(points[index].bucket_start, bucket, true)}`}
                onClick={() => setSelectedIndex(index)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') setSelectedIndex(index)
                }}
                className={cn(
                  'cursor-pointer outline-none transition-all',
                  points[index]?.partial_cost_requests || points[index]?.unpriced_requests
                    ? 'fill-amber-300'
                    : 'fill-primary-light',
                  selectedIndex === index && 'stroke-white stroke-2',
                )}
                vectorEffect="non-scaling-stroke"
              >
                <title>{`${formatBucket(points[index].bucket_start, bucket, true)} · ${formatValue(values[index], mode)}`}</title>
              </circle>
            ))}
          </svg>
          <div className="flex justify-between gap-4 px-1 text-[10px] text-muted">
            {tickIndexes.map((index) => <span key={index}>{points[index] ? formatBucket(points[index].bucket_start, bucket) : ''}</span>)}
          </div>
          <div className="mt-3 flex items-center gap-2 border-t border-border/60 pt-3 text-[10px] text-muted">
            <MousePointerClick className="h-3.5 w-3.5 text-primary-light" />
            Selected buckets replace the former full period table with focused evidence.
          </div>
        </div>

        <div className="space-y-3">
          <div className="rounded-lg border border-primary/25 bg-primary/5 p-4">
            <div className="flex items-center gap-2">
              <CalendarRange className="h-4 w-4 text-primary-light" />
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-primary-light">Selected period</p>
            </div>
            <p className="mt-2 text-sm font-semibold text-white">
              {selectedPoint ? formatBucket(selectedPoint.bucket_start, bucket, true) : 'No period selected'}
            </p>
            {selectedPoint && (
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="rounded-md border border-border/60 bg-background/25 p-2.5">
                  <p className="text-[9px] uppercase tracking-wider text-muted">{modes.find((item) => item.value === mode)?.label}</p>
                  <p className="mt-1 text-sm font-semibold text-white">{formatValue(valueFor(selectedPoint, mode), mode)}</p>
                </div>
                <div className="rounded-md border border-border/60 bg-background/25 p-2.5">
                  <p className="text-[9px] uppercase tracking-wider text-muted">Success</p>
                  <p className="mt-1 text-sm font-semibold text-white">{successRate(selectedPoint).toFixed(1)}%</p>
                </div>
                <div className="rounded-md border border-border/60 bg-background/25 p-2.5">
                  <p className="text-[9px] uppercase tracking-wider text-muted">Requests</p>
                  <p className="mt-1 text-sm font-semibold text-white">{formatValue(selectedPoint.runtime_requests, 'requests')}</p>
                </div>
                <div className="rounded-md border border-border/60 bg-background/25 p-2.5">
                  <p className="text-[9px] uppercase tracking-wider text-muted">Known spend</p>
                  <p className="mt-1 text-sm font-semibold text-white">{formatKnownMoney(selectedPoint.known_cost_usd)}</p>
                </div>
              </div>
            )}
          </div>

          <div className="rounded-lg border border-border/70 bg-background/25 p-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary-light" />
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Period highlights</p>
            </div>
            <div className="mt-3 space-y-3">
              {highlights.map((highlight) => (
                <div key={highlight.label} className="flex items-center justify-between gap-3 text-xs">
                  <div className="min-w-0">
                    <p className="truncate text-white">{highlight.label}</p>
                    <p className="mt-0.5 text-[10px] text-muted">{highlight.period}</p>
                  </div>
                  <span className="shrink-0 font-medium text-white">{highlight.value}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border/70 bg-background/25 p-3 text-xs">
            <div className="flex items-center gap-2 text-muted">
              <CircleGauge className="h-4 w-4 text-primary-light" />
              Period total
            </div>
            <span className="font-semibold text-white">{formatValue(total, mode)}</span>
          </div>
        </div>
      </div>
    </section>
  )
}
