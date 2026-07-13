import type { ProjectUsageTimeseriesPoint } from '../types'
import { formatKnownMoney } from '@/lib/formatters/money'
import { cn } from '@/lib/utils'

export type UsageTrendMode = 'cost' | 'requests' | 'tokens' | 'llm_calls'

const modes: Array<{ value: UsageTrendMode; label: string }> = [
  { value: 'cost', label: 'Cost' },
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

function formatBucket(value: string, hourly: boolean) {
  const date = new Date(value)
  return new Intl.DateTimeFormat('en-US', hourly
    ? { month: 'short', day: 'numeric', hour: '2-digit' }
    : { month: 'short', day: 'numeric' }).format(date)
}

export function UsageTrendChart({
  points,
  mode,
  onModeChange,
}: {
  points: ProjectUsageTimeseriesPoint[]
  mode: UsageTrendMode
  onModeChange: (mode: UsageTrendMode) => void
}) {
  const values = points.map((point) => valueFor(point, mode))
  const max = Math.max(...values, 1)
  const width = 1000
  const height = 210
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
  const peak = values.length ? Math.max(...values) : 0
  const hourly = points.length > 31
  const tickIndexes = Array.from(new Set([0, Math.floor((points.length - 1) / 2), points.length - 1])).filter((index) => index >= 0)

  return (
    <section className="overflow-hidden rounded-xl border border-border/90 bg-surface/70">
      <div className="flex flex-col gap-4 border-b border-border px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-white">Usage trend</h2>
          <p className="mt-1 text-xs text-muted">Runtime consumption across the selected period.</p>
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

      <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_180px]">
        <div className="relative min-h-[250px] overflow-hidden rounded-lg border border-border/70 bg-background/25 p-3">
          <svg viewBox={`0 0 ${width} ${height}`} className="h-[220px] w-full" preserveAspectRatio="none" role="img" aria-label={`${mode} usage trend`}>
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
                r="3"
                className={points[index]?.partial_cost_requests || points[index]?.unpriced_requests ? 'fill-amber-300' : 'fill-primary-light'}
                vectorEffect="non-scaling-stroke"
              >
                <title>{`${formatBucket(points[index].bucket_start, hourly)} · ${formatValue(values[index], mode)}`}</title>
              </circle>
            ))}
          </svg>
          <div className="flex justify-between gap-4 px-1 text-[10px] text-muted">
            {tickIndexes.map((index) => <span key={index}>{points[index] ? formatBucket(points[index].bucket_start, hourly) : ''}</span>)}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-1">
          <div className="rounded-lg border border-border/70 bg-background/25 p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Period total</p>
            <p className="mt-2 text-lg font-semibold text-white">{formatValue(total, mode)}</p>
          </div>
          <div className="rounded-lg border border-border/70 bg-background/25 p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Peak bucket</p>
            <p className="mt-2 text-lg font-semibold text-white">{formatValue(peak, mode)}</p>
          </div>
          <div className="col-span-2 rounded-lg border border-border/70 bg-background/25 p-4 xl:col-span-1">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Data quality</p>
            <p className="mt-2 text-xs leading-5 text-muted"><span className="text-amber-300">Amber points</span> contain partial or unpriced requests.</p>
          </div>
        </div>
      </div>
    </section>
  )
}
