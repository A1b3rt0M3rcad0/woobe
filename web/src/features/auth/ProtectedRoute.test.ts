import { describe, expect, it } from 'vitest'

import { resolvePublicRouteTarget } from './ProtectedRoute'

describe('resolvePublicRouteTarget', () => {
  it('prioritizes the explicit authentication transition target', () => {
    expect(resolvePublicRouteTarget(
      '/workspaces/workspace-1/setup',
      { pathname: '/workspaces' },
    )).toBe('/workspaces/workspace-1/setup')
  })

  it('preserves the protected route that originally requested authentication', () => {
    expect(resolvePublicRouteTarget(null, {
      pathname: '/workspaces/workspace-1/projects/project-1/agents',
      search: '?create=1',
      hash: '#setup',
    })).toBe('/workspaces/workspace-1/projects/project-1/agents?create=1#setup')
  })

  it('uses dashboard as the normal login destination', () => {
    expect(resolvePublicRouteTarget(null)).toBe('/dashboard')
  })
})
