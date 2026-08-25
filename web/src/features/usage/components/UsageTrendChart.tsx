import { useEffect, useMemo, useState } from 'react'
import { CalendarRange, CircleGauge, MousePointerClick, TrendingUp } from 'lucide-react'

import type { ProjectUsageTimeseriesPoint, UsageBucket } from '../types'
import { formatKnownMoney } from '@/lib/formatters/money'
import { cn } from '@/lib/utils'

export type UsageTrendMode = 'cost' | 'runs' | 'unit_cost' | 'tokens'

const modes: Array<{ value: UsageTrendMode; label: string }> = [
  { value: 'cost', label: 'Cost' },
  { value: 'runs', label: 'Runs' },
  { value: 'unit_cost', label: 'Unit cost' },
  { value: 'tokens', label: 'Tokens' },
]

const DOMAIN_HEADROOM = 1.08

function seriesFor(point: ProjectUsageTimeseriesPoint, mode: UsageTrendMode) {
  if (mode === 'cost') {
    return {
      primary: point.known_cost_usd ?? 0,
      secondary: point.network_run_cost_usd ?? 0,
      primaryLabel: 'Agent Run cost',
      secondaryLabel: 'Network-attributed cost',
    }
  }
  if (mode === 'runs') {
    return {
      primary: point.agent_runs,
      secondary: point.network_runs,
      primaryLabel: 'Agent Runs',
      secondaryLabel: 'Network Runs',
    }
  }
  if (mode === 'unit_cost') {
    return {
      primary: point.agent_cost_per_run ?? 0,
      secondary: point.network_cost_per_run ?? 0,
      primaryLabel: 'Cost / Agent Run',
      secondaryLabel: 'Cost / Network Run',
    }
  }
  return {
    primary: point.input_tokens + point.output_tokens,
    secondary: 0,
    primaryLabel: 'Generation tokens',
    secondaryLabel: '',
  }
}

function adaptiveDomainMax(values: number[]) {
  const maxValue = values.reduce((currentMax, value) => (
    Number.isFinite(value) && value > currentMax ? value : currentMax
  ), 0)
  return maxValue > 0 ? maxValue * DOMAIN_HEADROOM : 0
}

function scaledHeight(value: number, domainMax: number, drawableHeight: number) {
  if (value <= 0 || domainMax <= 0 || drawableHeight <= 0) return 0
  return Math.min(value / domainMax, 1) * drawableHeight
}

function formatValue(value: number, mode: UsageTrendMode) {
  if (mode === 'cost' || mode === 'unit_cost') return formatKnownMoney(value)
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

function successRate(successful: number, total: number) {
  return total ? (successful / total) * 100 : null
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

  const series = points.map((point) => seriesFor(point, mode))
  const primaryDomainMax = adaptiveDomainMax(series.map((item) => item.primary))
  const secondaryDomainMax = adaptiveDomainMax(series.map((item) => item.secondary))
  const width = 1000
  const height = 220
  const paddingX = 20
  const paddingY = 18
  const drawableWidth = width - paddingX * 2
  const drawableHeight = height - paddingY * 2
  const coordinates = series.map((item, index) => ({
    x: paddingX + (points.length <= 1 ? drawableWidth / 2 : (index / (points.length - 1)) * drawableWidth),
    y: paddingY + drawableHeight - scaledHeight(item.primary, primaryDomainMax, drawableHeight),
  }))
  const line = coordinates.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')
  const area = coordinates.length
    ? `${line} L ${coordinates[coordinates.length - 1].x} ${height - paddingY} L ${coordinates[0].x} ${height - paddingY} Z`
    : ''
  const barWidth = Math.max(Math.min(drawableWidth / Math.max(points.length, 1) * 0.38, 22), 5)
  const tickIndexes = Array.from(new Set([0, Math.floor((points.length - 1) / 2), points.length - 1])).filter((index) => index >= 0)
  const selectedPoint = points[selectedIndex]
  const selectedSeries = selectedPoint ? seriesFor(selectedPoint, mode) : null
  const hasSecondarySeries = Boolean(series[0]?.secondaryLabel)

  const totals = useMemo(() => points.reduce((acc, point) => {
    const item = seriesFor(point, mode)
    return {
      primary: acc.primary + item.primary,
      secondary: acc.secondary + item.secondary,
    }
  }, { primary: 0, secondary: 0 }), [mode, points])

  const highlights = useMemo(() => {
    if (!points.length) return []
    const primaryPeak = series.reduce((best, item, index) => item.primary > series[best].primary ? index : best, 0)
    const networkPeak = series.reduce((best, item, index) => item.secondary > series[best].secondary ? index : best, 0)
    return [
      {
        label: `Peak ${series[primaryPeak].primaryLabel.toLowerCase()}`,
        period: formatBucket(points[primaryPeak].bucket_start, bucket),
        value: formatValue(series[primaryPeak].primary, mode),
      },
      ...(series[networkPeak].secondaryLabel && series[networkPeak].secondary > 0
        ? [{
            label: `Peak ${series[networkPeak].secondaryLabel.toLowerCase()}`,
            period: formatBucket(points[networkPeak].bucket_start, bucket),
            value: formatValue(series[networkPeak].secondary, mode),
          }]
        : []),
    ]
  }, [bucket, mode, points, series])

  const agentSuccess = selectedPoint
    ? successRate(selectedPoint.successful_agent_runs, selectedPoint.agent_runs)
    : null
  const networkSuccess = selectedPoint
    ? successRate(selectedPoint.successful_network_runs, selectedPoint.network_runs)
    : null

  return (
    <section className="overflow-hidden rounded-xl border border-border/90 bg-surface/70">
      <div className="flex flex-col gap-4 border-b border-border px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-white">Cost and run volume over time</h2>
          <p className="mt-1 text-xs text-muted">{contextLabel} Network cost is contained in Agent Run cost and is not additive.</p>
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
          <div className="mb-2 flex flex-wrap items-center gap-4 text-[10px] text-muted">
            <span className="inline-flex items-center gap-1.5"><span className="h-0.5 w-5 bg-primary" />{series[0]?.primaryLabel ?? 'Agent Runs'}</span>
            {series[0]?.secondaryLabel && (
              <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2 rounded-sm bg-violet-400/70" />{series[0].secondaryLabel}</span>
            )}
            {hasSecondarySeries && (
              <span className="text-muted">Series use independent relative scales; cards show absolute values.</span>
            )}
          </div>
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
            {series.map((item, index) => {
              const barHeight = scaledHeight(item.secondary, secondaryDomainMax, drawableHeight)
              return item.secondary > 0 ? (
                <rect
                  key={`bar-${points[index]?.bucket_start ?? index}`}
                  x={coordinates[index].x - barWidth / 2}
                  y={height - paddingY - barHeight}
                  width={barWidth}
                  height={barHeight}
                  rx="3"
                  className="fill-violet-400/65"
                  vectorEffect="non-scaling-stroke"
                />
              ) : null
            })}
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
                  'cursor-pointer fill-primary-light outline-none transition-all',
                  selectedIndex === index && 'stroke-white stroke-2',
                )}
                vectorEffect="non-scaling-stroke"
              >
                <title>{`${formatBucket(points[index].bucket_start, bucket, true)} · ${formatValue(series[index].primary, mode)}`}</title>
              </circle>
            ))}
          </svg>
          <div className="flex justify-between gap-4 px-1 text-[10px] text-muted">
            {tickIndexes.map((index) => <span key={index}>{points[index] ? formatBucket(points[index].bucket_start, bucket) : ''}</span>)}
          </div>
          <div className="mt-3 flex items-center gap-2 border-t border-border/60 pt-3 text-[10px] text-muted">
            <MousePointerClick className="h-3.5 w-3.5 text-primary-light" />
            Select a bucket to inspect its Agent Run and Network Run economics.
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
            {selectedPoint && selectedSeries && (
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="rounded-md border border-border/60 bg-background/25 p-2.5">
                  <p className="text-[9px] uppercase tracking-wider text-muted">{selectedSeries.primaryLabel}</p>
                  <p className="mt-1 text-sm font-semibold text-white">{formatValue(selectedSeries.primary, mode)}</p>
                </div>
                <div className="rounded-md border border-border/60 bg-background/25 p-2.5">
                  <p className="text-[9px] uppercase tracking-wider text-muted">{selectedSeries.secondaryLabel || 'LLM calls'}</p>
                  <p className="mt-1 text-sm font-semibold text-white">
                    {selectedSeries.secondaryLabel ? formatValue(selectedSeries.secondary, mode) : selectedPoint.llm_calls}
                  </p>
                </div>
                <div className="rounded-md border border-border/60 bg-background/25 p-2.5">
                  <p className="text-[9px] uppercase tracking-wider text-muted">Agent success</p>
                  <p className="mt-1 text-sm font-semibold text-white">{agentSuccess === null ? '—' : `${agentSuccess.toFixed(1)}%`}</p>
                </div>
                <div className="rounded-md border border-border/60 bg-background/25 p-2.5">
                  <p className="text-[9px] uppercase tracking-wider text-muted">Network success</p>
                  <p className="mt-1 text-sm font-semibold text-white">{networkSuccess === null ? '—' : `${networkSuccess.toFixed(1)}%`}</p>
                </div>
              </div>
            )}
          </div>

          <div className="rounded-lg border border-border/70 bg-background/25 p-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary-light" />
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Period peaks</p>
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

          <div className="rounded-lg border border-border/70 bg-background/25 p-3 text-xs">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-muted"><CircleGauge className="h-4 w-4 text-primary-light" />Primary total</div>
              <span className="font-semibold text-white">{formatValue(totals.primary, mode)}</span>
            </div>
            {series[0]?.secondaryLabel && (
              <div className="mt-2 flex items-center justify-between gap-3 border-t border-border/60 pt-2">
                <span className="text-muted">Secondary total</span>
                <span className="font-semibold text-white">{formatValue(totals.secondary, mode)}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
