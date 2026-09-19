import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { ProjectEnvironmentSettings } from './ProjectEnvironmentSettings'

const fixture = vi.hoisted(() => ({
  remove: vi.fn(),
  upsert: vi.fn(),
}))

vi.mock('@/features/projects/hooks', () => ({
  useProjectEnvironmentKeys: () => ({
    data: [
      {
        id: 'env-key-1',
        project_id: 'project-1',
        key: 'API_KEY',
        kind: 'secret',
        values: {
          draft: { configured: true, value: null },
          staging: { configured: true, value: null },
          production: { configured: true, value: null },
        },
        used_by_tools: [
          { id: 'tool-1', name: 'Billing API' },
          { id: 'tool-2', name: 'Orders API' },
        ],
      },
    ],
    isPending: false,
    isError: false,
    error: null,
  }),
  useUpsertProjectEnvironmentKey: () => ({
    mutateAsync: fixture.upsert,
    isPending: false,
  }),
  useDeleteProjectEnvironmentKey: () => ({
    mutateAsync: fixture.remove,
    isPending: false,
  }),
}))

describe('ProjectEnvironmentSettings dependencies', () => {
  it('shows dependent Tools and disables deletion while a key is in use', () => {
    const html = renderToStaticMarkup(
      <ProjectEnvironmentSettings projectId="project-1" />,
    )

    expect(html).toContain('Used by Tools')
    expect(html).toContain('Billing API, Orders API')
    expect(html).toContain('Edit these Tools to use another Project Environment key')
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*aria-label="Delete API_KEY"/)
  })
})
