import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { adaptProjectOverview } from '@/features/dashboard/adapters'
import { projectOverviewFixture } from '@/features/dashboard/fixtures'
import {
  DashboardDataState,
  DashboardErrorState,
  DashboardLoadingState,
  dashboardRowTarget,
} from './DashboardPage'

function cloneFixture() {
  return structuredClone(projectOverviewFixture)
}

describe('DashboardPage states', () => {
  it('renders loading and retryable error states', () => {
    expect(renderToStaticMarkup(<DashboardLoadingState />)).toContain('Loading dashboard')
    const retry = vi.fn()
    const errorMarkup = renderToStaticMarkup(<DashboardErrorState message="API unavailable" onRetry={retry} />)
    expect(errorMarkup).toContain('Dashboard unavailable')
    expect(errorMarkup).toContain('Retry')
  })

  it('renders an execution empty state without replacing live project totals', () => {
    const fixture = cloneFixture()
    fixture.summary.requests = 0
    fixture.timeseries = []
    const markup = renderToStaticMarkup(<DashboardDataState model={adaptProjectOverview(fixture)} onNavigate={vi.fn()} />)
    expect(markup).toContain('No executions in this interval')
    expect(markup).toContain('Open Knowledge')
  })

  it('renders populated data and hides unavailable capability panels', () => {
    const markup = renderToStaticMarkup(<DashboardDataState model={adaptProjectOverview(cloneFixture())} onNavigate={vi.fn()} />)
    expect(markup).toContain('Support Agent')
    expect(markup).toContain('Recent Traces')
    expect(markup).not.toContain('Sessions &amp; Jobs')
    expect(markup).not.toContain('Ingestion Pipeline')
    expect(markup).not.toContain('Recent Activity')
  })

  it('shows capability panels only when the API enables them', () => {
    const fixture = cloneFixture()
    fixture.capabilities = { sessions_jobs: true, ingestion_pipeline: true, activity_feed: true }
    const markup = renderToStaticMarkup(<DashboardDataState model={adaptProjectOverview(fixture)} onNavigate={vi.fn()} />)
    expect(markup).toContain('Sessions &amp; Jobs')
    expect(markup).toContain('Ingestion Pipeline')
    expect(markup).toContain('Recent Activity')
  })

  it('routes release and trace rows to their dedicated screens', () => {
    expect(dashboardRowTarget('release')).toBe('agents')
    expect(dashboardRowTarget('trace')).toBe('traces')
  })
})
