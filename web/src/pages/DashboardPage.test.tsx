import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { adaptProjectOverview } from '@/features/dashboard/adapters'
import { projectOverviewFixture } from '@/features/dashboard/fixtures'
import {
  DashboardDataState,
  DashboardErrorState,
  DashboardLoadingState,
} from './DashboardPage'

function cloneFixture() {
  return structuredClone(projectOverviewFixture)
}

describe('DashboardPage states', () => {
  it('renders loading and retryable error states', () => {
    expect(renderToStaticMarkup(<DashboardLoadingState />)).toContain('Loading project overview')
    const retry = vi.fn()
    const errorMarkup = renderToStaticMarkup(<DashboardErrorState message="API unavailable" onRetry={retry} />)
    expect(errorMarkup).toContain('Overview unavailable')
    expect(errorMarkup).toContain('Retry')
  })

  it('renders a Run empty state without replacing live project totals', () => {
    const fixture = cloneFixture()
    fixture.summary.agent_runs = 0
    fixture.summary.network_runs = 0
    fixture.timeseries = []
    const markup = renderToStaticMarkup(<DashboardDataState model={adaptProjectOverview(fixture)} onNavigate={vi.fn()} onOpenRun={vi.fn()} />)
    expect(markup).toContain('No Agent Runs or Network Runs in this interval')
    expect(markup).toContain('Open Knowledge')
  })

  it('renders populated Run data and project assets', () => {
    const markup = renderToStaticMarkup(<DashboardDataState model={adaptProjectOverview(cloneFixture())} onNavigate={vi.fn()} onOpenRun={vi.fn()} />)
    expect(markup).toContain('Support Agent')
    expect(markup).toContain('Support Network')
    expect(markup).toContain('Recent Runs')
    expect(markup).toContain('Runtime Assets')
  })

  it('keeps Agent Runs and Network Runs separate in the charts', () => {
    const markup = renderToStaticMarkup(<DashboardDataState model={adaptProjectOverview(cloneFixture())} onNavigate={vi.fn()} onOpenRun={vi.fn()} />)
    expect(markup).toContain('Run Volume')
    expect(markup).toContain('Agent Runs')
    expect(markup).toContain('Network Runs')
    expect(markup).toContain('Execution Time')
  })
})
