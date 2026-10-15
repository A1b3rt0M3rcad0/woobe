import { describe, expect, it } from 'vitest'
import { adaptProjectOverview } from './adapters'
import { projectOverviewFixture } from './fixtures'
import { activityBuckets, countAxis, lastActiveBucket, timePosition } from './activity'

describe('Overview activity time domain', () => {
  it('keeps two reported hours at their actual positions in a 24-hour window', () => {
    const model = adaptProjectOverview(projectOverviewFixture)
    const buckets = activityBuckets(model.window, [...model.series].reverse())
    expect(buckets).toHaveLength(24)
    expect(buckets.slice(0, 22).every(bucket => bucket.point === null)).toBe(true)
    expect(buckets[22].point?.agentRuns).toBe(5)
    expect(buckets[23].point?.agentRuns).toBe(7)
    expect(lastActiveBucket(buckets)).toBe(23)
    const from = Date.parse(model.window.from), to = Date.parse(model.window.to)
    expect(timePosition(buckets[22].start, from, to, 240)).toBe(220)
  })

  it('distinguishes explicitly reported zeros from missing buckets', () => {
    const model = adaptProjectOverview(projectOverviewFixture)
    const zero = { ...model.series[0], bucketStart: model.window.from, agentRuns: 0, networkRuns: 0, agentErrors: 0, networkErrors: 0 }
    const buckets = activityBuckets(model.window, [zero])
    expect(buckets[0].point?.agentRuns).toBe(0)
    expect(buckets[1].point).toBeNull()
    expect(lastActiveBucket(buckets)).toBe(0)
  })

  it('clips edge buckets to the requested interval and excludes an end-boundary record', () => {
    const point = adaptProjectOverview(projectOverviewFixture).series[0]
    const window = { from: '2026-06-20T10:30:00Z', to: '2026-06-20T12:00:00Z', bucket: 'hour' as const }
    const buckets = activityBuckets(window, [point, { ...point, bucketStart: window.to, agentRuns: 999 }])
    expect(buckets).toHaveLength(2)
    expect(buckets[0].start).toBe(Date.parse(window.from))
    expect(buckets[0].end - buckets[0].start).toBe(30 * 60_000)
    expect(buckets[1].end).toBe(Date.parse(window.to))
    expect(buckets[1].point).toBeNull()
  })

  it('retains UTC daily boundaries across local daylight-saving offsets', () => {
    const buckets = activityBuckets({ from: '2026-03-07T12:00:00-05:00', to: '2026-03-09T12:00:00-04:00', bucket: 'day' }, [])
    expect(buckets.map(bucket => bucket.key)).toEqual(['2026-03-07T00:00:00.000Z', '2026-03-08T00:00:00.000Z', '2026-03-09T00:00:00.000Z'])
    expect(buckets[1].end - buckets[1].start).toBe(86_400_000)
    expect(buckets.every(bucket => bucket.point === null)).toBe(true)
  })

  it.each([0, 1, 2, 7, 123, 10000])('uses a nonzero integer count scale for %s Runs', max => {
    const axis = countAxis(max)
    expect(axis.ceiling).toBeGreaterThanOrEqual(Math.max(1, max))
    expect(axis.ticks[0]).toBe(0)
    expect(axis.ticks.every(Number.isInteger)).toBe(true)
    expect(new Set(axis.ticks).size).toBe(axis.ticks.length)
    expect(axis.ticks.length).toBeLessThanOrEqual(6)
  })
})
