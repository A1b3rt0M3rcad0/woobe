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

  it('renders a Run empty state without replacing changes and current state', () => {
    const fixture = cloneFixture()
    fixture.summary.agent_runs = 0
    fixture.summary.network_runs = 0
    fixture.summary.terminal_agent_runs = 0
    fixture.summary.terminal_network_runs = 0
    fixture.timeseries = []
    const markup = renderToStaticMarkup(<DashboardDataState model={adaptProjectOverview(fixture)} onNavigate={vi.fn()} onOpenRun={vi.fn()} />)
    expect(markup).toContain('No Agent Runs or Network Runs in this interval')
    expect(markup).toContain('Changes in this period')
    expect(markup).toContain('Current Project State')
    expect(markup).toContain('Open Knowledge')
  })

  it('renders the story in the intended vertical order', () => {
    const markup = renderToStaticMarkup(<DashboardDataState model={adaptProjectOverview(cloneFixture())} onNavigate={vi.fn()} onOpenRun={vi.fn()} />)
    const activityIndex = markup.indexOf('What happened')
    const changesIndex = markup.indexOf('Changes in this period')
    const currentStateIndex = markup.indexOf('Current Project State')
    const recentIndex = markup.indexOf('Recent Runs')

    expect(activityIndex).toBeGreaterThan(-1)
    expect(changesIndex).toBeGreaterThan(activityIndex)
    expect(currentStateIndex).toBeGreaterThan(changesIndex)
    expect(recentIndex).toBeGreaterThan(currentStateIndex)
  })

  it('renders reliability, operational issues, and both release types', () => {
    const markup = renderToStaticMarkup(<DashboardDataState model={adaptProjectOverview(cloneFixture())} onNavigate={vi.fn()} onOpenRun={vi.fn()} />)
    expect(markup).toContain('Run Activity')
    expect(markup).toContain('Reliability &amp; Performance')
    expect(markup).toContain('Operational Issues')
    expect(markup).toContain('Agent Releases')
    expect(markup).toContain('Network Releases')
    expect(markup).toContain('Support Agent')
    expect(markup).toContain('Support Network')
  })

  it('keeps Recent Runs compact and removes token columns', () => {
    const markup = renderToStaticMarkup(<DashboardDataState model={adaptProjectOverview(cloneFixture())} onNavigate={vi.fn()} onOpenRun={vi.fn()} />)
    expect(markup).toContain('The three latest primary executions')
    expect(markup).toContain('Duration')
    expect(markup).toContain('Cost')
    expect(markup).not.toContain('Tokens')
  })
})
