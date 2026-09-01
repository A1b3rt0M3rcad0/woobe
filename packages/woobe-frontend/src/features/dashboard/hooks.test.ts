import { describe, expect, it } from 'vitest'
import { projectOverviewQueryKey, resolveOverviewWindow } from './hooks'

describe('project overview query configuration', () => {
  it('uses hour buckets for 24 hours and day buckets for longer ranges', () => {
    const now = new Date('2026-06-20T12:00:00Z')
    expect(resolveOverviewWindow('24h', now).bucket).toBe('hour')
    expect(resolveOverviewWindow('7d', now).bucket).toBe('day')
    expect(resolveOverviewWindow('30d', now).bucket).toBe('day')
  })

  it('keeps the query identity stable while the rolling interval advances', () => {
    const base = {
      projectId: 'project-a',
      environment: 'draft' as const,
      range: '24h' as const,
      recentLimit: 5,
    }

    expect(projectOverviewQueryKey(base)).not.toEqual(projectOverviewQueryKey({ ...base, projectId: 'project-b' }))
    expect(projectOverviewQueryKey(base)).not.toEqual(projectOverviewQueryKey({ ...base, environment: 'production' }))
    expect(projectOverviewQueryKey(base)).not.toEqual(projectOverviewQueryKey({ ...base, range: '7d' }))
    expect(projectOverviewQueryKey(base)).toEqual(projectOverviewQueryKey({ ...base }))
  })

  it('advances from and to values without requiring a new query key', () => {
    const first = resolveOverviewWindow('24h', new Date('2026-06-20T12:00:00Z'))
    const second = resolveOverviewWindow('24h', new Date('2026-06-20T13:00:00Z'))

    expect(first.from).not.toBe(second.from)
    expect(first.to).not.toBe(second.to)
    expect(first.range).toBe(second.range)
    expect(first.bucket).toBe(second.bucket)
  })
})
