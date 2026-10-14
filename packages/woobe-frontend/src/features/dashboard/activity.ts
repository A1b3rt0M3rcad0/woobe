import type { DashboardSeriesPoint } from './adapters'
import type { DashboardBucket } from './types'

export interface ActivityWindow { from: string; to: string; bucket: DashboardBucket }
export interface ActivityBucket {
  key: string
  start: number
  end: number
  point: DashboardSeriesPoint | null
}

/** The API groups in UTC and filters Runs by the half-open requested interval. */
export function activityBuckets(window: ActivityWindow, series: DashboardSeriesPoint[]): ActivityBucket[] {
  const from = Date.parse(window.from)
  const to = Date.parse(window.to)
  if (!Number.isFinite(from) || !Number.isFinite(to) || to <= from) return []
  const step = window.bucket === 'hour' ? 3_600_000 : 86_400_000
  const points = new Map(series.map(point => [Date.parse(point.bucketStart), point]))
  const buckets: ActivityBucket[] = []
  for (let start = Math.floor(from / step) * step; start < to; start += step) {
    buckets.push({ key: new Date(start).toISOString(), start: Math.max(start, from), end: Math.min(start + step, to), point: points.get(start) ?? null })
  }
  return buckets
}

export function timePosition(timestamp: number, from: number, to: number, width: number) {
  return ((timestamp - from) / (to - from)) * width
}

export function countAxis(max: number) {
  const rough = Math.max(max, 1) / 4
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const step = Math.max(1, [1, 2, 5, 10].find(value => value * magnitude >= rough)! * magnitude)
  const ceiling = Math.max(step, Math.ceil(max / step) * step)
  return { ceiling, ticks: Array.from({ length: Math.round(ceiling / step) + 1 }, (_, index) => index * step) }
}

export function lastActiveBucket(buckets: ActivityBucket[]) {
  let lastReported = -1
  for (let index = buckets.length - 1; index >= 0; index--) {
    const point = buckets[index].point
    if (point && point.agentRuns + point.networkRuns > 0) return index
    if (point && lastReported < 0) lastReported = index
  }
  return Math.max(0, lastReported)
}
