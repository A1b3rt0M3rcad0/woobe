import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Button, Card, PanelHeader } from '@woobe/ui'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { formatCost, formatInteger, formatLatency, type DashboardViewModel } from '../adapters'
import { activityBuckets, countAxis, lastActiveBucket, timePosition, type ActivityBucket } from '../activity'

const seriesStyles = { agent: 'text-primary-light', network: 'text-network', errors: 'text-error' }
const intervalFormatter = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
function intervalLabel(bucket: ActivityBucket) {
  return `${intervalFormatter.format(bucket.start)} – ${intervalFormatter.format(bucket.end)}`
}

export function RunActivityChart({ model }: { model: DashboardViewModel }) {
  const buckets = useMemo(() => activityBuckets(model.window, model.series), [model.window, model.series])
  const [selected, setSelected] = useState(() => lastActiveBucket(buckets))
  const [hovered, setHovered] = useState<number | null>(null)
  const [width, setWidth] = useState(760)
  const container = useRef<HTMLDivElement>(null)
  const descriptionId = useId()
  const selectId = useId()
  useEffect(() => {
    setSelected(lastActiveBucket(buckets))
    setHovered(null)
  }, [buckets])
  useEffect(() => {
    const node = container.current
    if (!node) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(240, entry.contentRect.width)))
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  const from = Date.parse(model.window.from)
  const to = Date.parse(model.window.to)
  const plotWidth = width - 52
  const baseline = 158
  const plotHeight = 138
  const x = (time: number) => 38 + timePosition(time, from, to, plotWidth)
  const axis = countAxis(Math.max(0, ...buckets.flatMap(({ point }) => point ? [point.agentRuns, point.networkRuns, point.agentErrors + point.networkErrors] : [])))
  const y = (count: number) => baseline - (count / axis.ceiling) * plotHeight
  const activeIndex = hovered ?? selected
  const active = buckets[activeIndex]
  const point = active?.point
  const missing = buckets.filter(bucket => !bucket.point).length
  const tickCount = width < 520 ? 2 : width < 700 ? 3 : 5
  const ticks = Array.from({ length: tickCount }, (_, i) => from + (to - from) * i / (tickCount - 1))
  const tickFormatter = new Intl.DateTimeFormat(undefined, model.window.bucket === 'hour'
    ? { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }
    : { month: 'short', day: 'numeric' })

  return <Card className="min-w-0 h-full" aria-label="Run activity analysis">
    <PanelHeader title="Run Activity" hierarchy="section" className="border-0 bg-transparent [&_h2]:text-product-label"
      actions={<p className="text-right text-product-caption text-muted-foreground">Period totals<br /><span className="font-mono text-foreground">{formatInteger(model.reliability.agent.totalRuns)}</span> Agent · <span className="font-mono text-foreground">{formatInteger(model.reliability.network.totalRuns)}</span> Network</p>} />
    <div className="space-y-ui-md px-ui-panel-inset pb-ui-panel-inset">
      <div className="flex flex-wrap gap-x-ui-lg gap-y-ui-xs text-product-caption">
        <span className="inline-flex items-center gap-ui-xs"><span aria-hidden="true" className={`h-3 w-2 rounded-sm bg-current ${seriesStyles.agent}`} />Agent Runs</span>
        <span className="inline-flex items-center gap-ui-xs"><span aria-hidden="true" className={`h-3 w-2 rounded-sm bg-current ${seriesStyles.network}`} />Network Runs</span>
        <span className="inline-flex items-center gap-ui-xs"><span aria-hidden="true" className={`h-2 w-2 rotate-45 bg-current ${seriesStyles.errors}`} />Errors (subset)</span>
      </div>
      <p id={descriptionId} className="text-product-caption text-muted-foreground">
        Runs started per {model.window.bucket}, not cumulative. Errors include failed, timed out and uncertain Runs. {model.timezoneLabel}.
      </p>
      <div ref={container} className="min-w-0">
        <svg viewBox={`0 0 ${width} 198`} className="block h-[198px] w-full" role="img" aria-label="Agent Runs, Network Runs and Errors by time bucket" aria-describedby={descriptionId} onMouseLeave={() => setHovered(null)}>
          {axis.ticks.map(tick => <g key={tick}>
            <line x1={38} x2={width - 14} y1={y(tick)} y2={y(tick)} className="text-border" stroke="currentColor" strokeWidth="1" />
            <text x={30} y={y(tick) + 4} textAnchor="end" className="fill-current font-mono text-[11px] text-muted-foreground">{new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(tick)}</text>
          </g>)}
          {buckets.map((bucket, index) => {
            const left = x(bucket.start)
            const span = x(bucket.end) - left
            const center = left + span / 2
            const barWidth = Math.min(12, span * 0.28)
            const value = bucket.point
            const errors = value ? value.agentErrors + value.networkErrors : 0
            return <g key={bucket.key} aria-hidden="true" onMouseEnter={() => setHovered(index)} onClick={() => setSelected(index)} className="cursor-pointer">
              <rect x={left} y={18} width={span} height={plotHeight + 2} fill="currentColor" className={index === activeIndex ? 'text-control' : !value ? 'text-control/40' : 'text-transparent'} />
              {!value && <line x1={left + 1} x2={left + span - 1} y1={baseline} y2={baseline} stroke="currentColor" strokeDasharray="2 3" className="text-muted-foreground" />}
              {value && <>
                <rect data-series="agent" x={center - barWidth - 1} y={y(value.agentRuns)} width={barWidth} height={baseline - y(value.agentRuns)} rx="1" fill="currentColor" className={seriesStyles.agent} />
                <rect data-series="network" x={center + 1} y={y(value.networkRuns)} width={barWidth} height={baseline - y(value.networkRuns)} rx="1" fill="currentColor" className={seriesStyles.network} />
                {errors > 0 && <path data-series="errors" d={`M ${center} ${y(errors) - 4} l 4 4 l -4 4 l -4 -4 Z`} fill="currentColor" className={seriesStyles.errors} />}
              </>}
              <title>{new Date(bucket.start).toISOString()} – {new Date(bucket.end).toISOString()}: {value ? `${value.agentRuns} Agent Runs; ${value.networkRuns} Network Runs; ${errors} errors` : 'Bucket data unavailable'}</title>
            </g>
          })}
          {ticks.map((tick, index) => <text key={tick} x={x(tick)} y={183} textAnchor={index === 0 ? 'start' : index === ticks.length - 1 ? 'end' : 'middle'} className="fill-current font-mono text-[11px] text-muted-foreground">{tickFormatter.format(tick)}</text>)}
        </svg>
      </div>
      {missing > 0 && <p className="text-product-caption text-muted-foreground">{buckets.length - missing} of {buckets.length} {model.window.bucket === 'hour' ? 'hourly' : 'daily'} buckets reported. Gaps are unavailable, not zero activity.</p>}
      {buckets.length > 0 && <div className="rounded-control bg-background p-ui-md">
        <div className="flex items-center gap-ui-sm">
          <label htmlFor={selectId} className="sr-only">Activity interval</label>
          <select id={selectId} value={selected} onChange={event => { setSelected(Number(event.target.value)); setHovered(null) }} className="h-control min-w-0 flex-1 rounded-control border border-control-border bg-surface px-ui-sm text-product-caption">
            {buckets.map((bucket, index) => <option key={bucket.key} value={index}>{intervalLabel(bucket)}{bucket.point ? '' : ' · unavailable'}</option>)}
          </select>
          <Button variant="outline" size="icon" aria-label="Previous activity interval" disabled={selected === 0} onClick={() => { setSelected(selected - 1); setHovered(null) }}><ChevronLeft className="h-icon w-icon" /></Button>
          <Button variant="outline" size="icon" aria-label="Next activity interval" disabled={selected >= buckets.length - 1} onClick={() => { setSelected(selected + 1); setHovered(null) }}><ChevronRight className="h-icon w-icon" /></Button>
        </div>
        <div aria-label="Selected interval details" className="mt-ui-md space-y-ui-sm">
          <p className="font-mono text-product-caption text-muted-foreground">{active && intervalLabel(active)} · {model.timezoneLabel}</p>
          {active && <p className="sr-only">Exact interval: {new Date(active.start).toISOString()} to {new Date(active.end).toISOString()}, end exclusive.</p>}
          {point ? <>
            <dl className="grid grid-cols-2 gap-ui-md sm:grid-cols-4">
              {[
                ['Agent Runs', point.agentRuns, `${point.agentSuccess} successful`, seriesStyles.agent],
                ['Network Runs', point.networkRuns, `${point.networkSuccess} successful`, seriesStyles.network],
                ['Errors', point.agentErrors + point.networkErrors, `${point.agentErrors} Agent · ${point.networkErrors} Network`, seriesStyles.errors],
                ['Runtime cost (USD)', formatCost(point.costUsd), point.unknownCostCount > 0 ? `${point.unknownCostCount} Runs unpriced${point.costUsd !== null ? ' · Partial' : ''}` : 'Recorded Agent Run cost', 'text-foreground'],
              ].map(([label, value, detail, tone]) => <div key={label}>
                <dt className="text-product-caption text-muted-foreground">{label}</dt>
                <dd className={`mt-ui-xs font-mono text-product-label ${tone}`}>{value}</dd>
                <dd className="mt-ui-xs text-product-caption text-muted-foreground">{detail}</dd>
              </div>)}
            </dl>
            <p className="text-product-caption text-muted-foreground">Average duration: <span className="font-mono">{formatLatency(point.agentDurationMs)}</span> Agent · <span className="font-mono">{formatLatency(point.networkDurationMs)}</span> Network</p>
          </> : <p className="text-product-small text-muted-foreground">No data was returned for this interval. Period totals are shown above.</p>}
        </div>
      </div>}
    </div>
  </Card>
}
