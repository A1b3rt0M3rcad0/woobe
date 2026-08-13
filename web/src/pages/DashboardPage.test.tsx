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
    expect(markup).toContain('What changed')
    expect(markup).toContain('Changes across all environments')
    expect(markup).toContain('Current Project State')
    expect(markup).toContain('Open Knowledge')
  })

  it('renders the story in the intended vertical order', () => {
    const markup = renderToStaticMarkup(<DashboardDataState model={adaptProjectOverview(cloneFixture())} onNavigate={vi.fn()} onOpenRun={vi.fn()} />)
    const activityIndex = markup.indexOf('What happened')
    const changesIndex = markup.indexOf('What changed')
    const currentStateIndex = markup.indexOf('Current Project State')
    const recentIndex = markup.indexOf('Recent Runs')

    expect(activityIndex).toBeGreaterThan(-1)
    expect(changesIndex).toBeGreaterThan(activityIndex)
    expect(currentStateIndex).toBeGreaterThan(changesIndex)
    expect(recentIndex).toBeGreaterThan(currentStateIndex)
  })

  it('renders distinct Run activity, reliability, issues, and contextual changes', () => {
    const markup = renderToStaticMarkup(<DashboardDataState model={adaptProjectOverview(cloneFixture())} onNavigate={vi.fn()} onOpenRun={vi.fn()} />)
    expect(markup).toContain('Run Activity')
    expect(markup).toContain('Agent Run line and Network Run bars')
    expect(markup).toContain('Reliability &amp; Performance')
    expect(markup).toContain('operational issue')
    expect(markup).toContain('Released to Production')
    expect(markup).toContain('Support Agent')
    expect(markup).toContain('Support Network')
  })

  it('renders Draft activity with mutable language', () => {
    const fixture = cloneFixture()
    fixture.recent_changes = [
      {
        id: '88888888-8888-8888-8888-888888888888',
        resource_type: 'network',
        resource_id: '66666666-6666-6666-6666-666666666666',
        resource_name: 'Support Network',
        environment: 'draft',
        action: 'draft_updated',
        version: null,
        revision: 14,
        description: null,
        occurred_at: '2026-06-20T11:30:00Z',
        immutable: false,
      },
    ]
    const markup = renderToStaticMarkup(<DashboardDataState model={adaptProjectOverview(fixture)} environment="draft" onNavigate={vi.fn()} onOpenRun={vi.fn()} />)

    expect(markup).toContain('Draft activity')
    expect(markup).toContain('Draft updated')
    expect(markup).toContain('Draft revision 14')
    expect(markup).not.toContain('Production releases')
  })

  it('keeps Recent Runs compact and removes guidance copy and token columns', () => {
    const model = adaptProjectOverview(cloneFixture())
    const markup = renderToStaticMarkup(<DashboardDataState model={model} onNavigate={vi.fn()} onOpenRun={vi.fn()} />)

    expect(markup).toContain('Recent Runs')
    expect(markup).toContain('View all Runs')
    expect(markup).toContain('Duration')
    expect(markup).toContain('Cost')
    expect(markup).not.toContain('The three latest primary executions')
    expect(markup).not.toContain('Volume, reliability, performance, and cost in the selected period.')
    expect(markup).not.toContain('Tokens')
  })
})
