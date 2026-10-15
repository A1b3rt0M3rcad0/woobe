// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { ProjectConfigurationNotice } from './ProjectConfigurationNotice'
import { ApiError } from '@/lib/api/errors'
const { query, useQuery } = vi.hoisted(() => ({ query: { data: undefined as unknown, isError: false, isFetching: false, error: undefined as unknown, refetch: vi.fn() }, useQuery: vi.fn() }))
vi.mock('@tanstack/react-query', () => ({ useQuery }))
let root: Root, container: HTMLDivElement
beforeEach(() => {
  vi.clearAllMocks(); sessionStorage.clear(); Object.assign(query, { data: undefined, isError: false, isFetching: false, error: undefined })
  useQuery.mockReturnValue(query); Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
})
afterEach(async () => { await act(async () => root.unmount()); container.remove() })
async function render(environment?: 'draft' | 'production') {
  await act(async () => root.render(<ProjectConfigurationNotice projectId="project" workspaceId="workspace" environment={environment} />))
}
it('defaults to Draft, persists an explicit choice and does not execute automatically', async () => {
  query.data = { state: 'blocked', blocked_key_count: 2, affected_target_count: 3 }
  await render()
  expect(useQuery.mock.calls[useQuery.mock.calls.length-1]?.[0].queryKey).toEqual(['configuration-readiness','project','summary','draft'])
  expect(container.textContent).toContain('Configuration blocks 3 selected targets · 2 required keys need attention')
  const select = container.querySelector('select')!
  await act(async () => { select.value = 'production'; select.dispatchEvent(new Event('change', { bubbles:true })) })
  expect(sessionStorage.getItem('woobe:configuration-environment:project')).toBe('production')
  expect(useQuery.mock.calls[useQuery.mock.calls.length-1]?.[0].queryKey[3]).toBe('production')
  expect(container.querySelector('a')?.href).toContain('environment=production')
  expect(query.refetch).not.toHaveBeenCalled()
})
it('uses the Overview environment and hides stale counts when permission is lost', async () => {
  query.data = { state:'blocked',blocked_key_count:99,affected_target_count:99 }
  query.isError=true; query.error=new ApiError('SECRET-CANARY',403)
  await render('production')
  expect(container.querySelector('select')).toBeNull()
  expect(container.textContent).toContain('requires permission')
  expect(container.textContent).not.toMatch(/99|SECRET-CANARY/)
  expect(container.querySelector('a')).toBeNull()
})
it('keeps incomplete checks distinct from readiness and refreshes only metadata', async () => {
  query.data={state:'unknown'}
  await render('draft')
  expect(container.textContent).toContain('Execution readiness is unverified')
  await act(async()=>container.querySelector('button')!.click())
  expect(query.refetch).toHaveBeenCalledOnce()
  expect(useQuery.mock.calls[useQuery.mock.calls.length-1]?.[0].refetchInterval).toBe(30_000)
})
it('identifies a bounded page without treating its counts as the whole Project', async () => {
  query.data={state:'unknown',has_next:true,inspected_target_count:100,blocked_key_count:0,page_state:'ready'}
  await render('draft')
  expect(container.textContent).toContain('Partial configuration check · 100 targets inspected')
  expect(container.textContent).not.toContain('Required configuration is ready')
})

it('uses a primary action only for confirmed configuration blockers', async () => {
  query.data = { state: 'unknown', inspected_target_count: 4 }
  await render('draft')
  expect(container.textContent).toContain('Execution readiness is unverified')
  expect(container.querySelector('a')?.textContent).toBe('Review configuration')
  expect(container.textContent).not.toContain('Configuration blocks')
  query.data = { state: 'blocked', affected_target_count: 1, blocked_key_count: 1 }
  await render('draft')
  expect(container.textContent).toContain('Configuration blocks 1 selected target')
  expect(container.querySelector('a')?.textContent).toBe('Configure now')
})

it('does not call an unavailable check a configuration blocker or expose stale counts', async () => {
  query.data = { state: 'blocked', affected_target_count: 99, blocked_key_count: 99 }
  query.isError = true; query.error = new Error('PRIVATE-UPSTREAM-CANARY')
  await render('draft')
  expect(container.textContent).toContain('Configuration check unavailable')
  expect(container.textContent).not.toMatch(/99|PRIVATE-UPSTREAM-CANARY|Configuration blocks/)
})

it('keeps the last partial page unverified even when its page is ready', async () => {
  query.data = { scope: 'current_selections_page', state: 'unknown', has_next: false, inspected_target_count: 5, page_state: 'ready', page_complete: true }
  await render('draft')
  expect(container.textContent).toContain('Partial configuration check · 5 targets inspected')
  expect(container.textContent).not.toContain('Required configuration is available')
})
