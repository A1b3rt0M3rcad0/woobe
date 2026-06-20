import { describe, expect, it } from 'vitest'
import { projectOverviewQueryKey, resolveOverviewWindow } from './hooks'

describe('project overview query configuration', () => {
  it('uses hour buckets for 24 hours and day buckets for longer ranges', () => {
    const now = new Date('2026-06-20T12:00:00Z')
    expect(resolveOverviewWindow('24h', now).bucket).toBe('hour')
    expect(resolveOverviewWindow('7d', now).bucket).toBe('day')
    expect(resolveOverviewWindow('30d', now).bucket).toBe('day')
  })

  it('changes the query key for project, environment, range, bucket and interval', () => {
    const base = {
      projectId: 'project-a',
      environment: 'draft' as const,
      range: '24h' as const,
      bucket: 'hour' as const,
      from: '2026-06-19T12:00:00Z',
      to: '2026-06-20T12:00:00Z',
      recentLimit: 5,
    }

    expect(projectOverviewQueryKey(base)).not.toEqual(projectOverviewQueryKey({ ...base, projectId: 'project-b' }))
    expect(projectOverviewQueryKey(base)).not.toEqual(projectOverviewQueryKey({ ...base, environment: 'production' }))
    expect(projectOverviewQueryKey(base)).not.toEqual(projectOverviewQueryKey({ ...base, range: '7d', bucket: 'day' }))
    expect(projectOverviewQueryKey(base)).not.toEqual(projectOverviewQueryKey({ ...base, to: '2026-06-20T13:00:00Z' }))
  })
})
