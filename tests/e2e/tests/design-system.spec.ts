import { emptyUsage } from '../fixtures/design-gallery'
import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { installApi, login, respond, workspace, project } from '../fixtures/control-plane'
import { projectOverviewFixture } from '../../../packages/woobe-frontend/src/features/dashboard/fixtures'

const root = `/workspaces/${workspace.id}/projects/${project.id}`

async function capture(page: Page, name: string) {
  if (process.env.WOOBE_CAPTURE_DOCS !== '1') return
  const directory = resolve(process.cwd(), '../../docs/screenshots')
  await mkdir(directory, { recursive: true })
  await page.screenshot({ path: resolve(directory, `${name}.png`), animations: 'disabled' })
}

async function demo(page: Page) {
  await page.clock.setFixedTime(new Date('2026-06-20T12:00:00Z'))
  await installApi(page, { asacAgent: true })
  await page.route('**/core/projects/project-a/overview*', route => respond(route, projectOverviewFixture))
  await login(page)
}

test('editorial console preserves project scope, filters and resource navigation', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1100 })
  await demo(page)
  await page.goto(root)
  await expect(page.getByRole('heading', { name: 'Project Overview', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Run Activity', exact: true })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Project navigation' })).toBeVisible()
  const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  expect(accessibility.violations).toEqual([])
  await capture(page, 'project-overview')
  await page.getByRole('button', { name: 'Production', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Production', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('link', { name: 'Agents', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Agents', level: 1, exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: /Open Agent playground/ })).toBeVisible()
  await capture(page, 'agents')
  await page.getByRole('button', { name: /Create agent/i }).first().click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await capture(page, 'create-agent')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await page.goto(`${root}/networks`)
  await expect(page.getByRole('button', { name: 'Open Network workspace for Customer Support' })).toBeVisible()
  await capture(page, 'networks')
})

for (const width of [360, 768, 1024, 1440, 1920]) {
  test(`resource navigation remains usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    await demo(page)
    await page.goto(`${root}/agents`)
    await expect(page.getByRole('heading', { name: 'Agents', level: 1, exact: true })).toBeVisible()
    const bounds = await page.locator('.resource-page-shell').boundingBox()
    expect(bounds).not.toBeNull()
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width + 1)
    if (width < 1024) {
      const trigger = page.getByRole('button', { name: 'Open navigation' })
      await trigger.click()
      const navigation = page.getByRole('dialog', { name: 'Navigation' })
      await expect(navigation).toBeVisible()
      await navigation.getByRole('link', { name: 'Tools', exact: true }).click()
      await expect(navigation).not.toBeVisible()
      await expect(page.getByRole('heading', { name: 'Tools', level: 1, exact: true })).toBeVisible()
      await trigger.click()
      await page.keyboard.press('Escape')
      await expect(trigger).toBeFocused()
    }
    if (width === 360) await capture(page, 'mobile-console')
  })
}

test('login uses labelled fields, inline errors and responsive product context', async ({ page }) => {
  await installApi(page)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: 'Sign in to Woobe' })).toBeVisible()
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.locator('#login-email')).toHaveAttribute('aria-invalid', 'true')
  await expect(page.locator('#login-email')).toBeFocused()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Sign in to Woobe' })).toBeVisible()
  await capture(page, 'sign-in')
})


test('resource families share readable states and retain their owning routes', async ({ page }) => {
  test.setTimeout(90_000)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await demo(page)
  await page.route('**/metering/projects/project-a/usage*', route => respond(route, emptyUsage))
  await page.route('**/core/projects/project-a/configuration/keys*', route => respond(route, {
    items: [], total: 0, offset: 0, limit: 50, permissions: { declare: true, 'value:write': true },
  }))
  await page.route('**/core/projects/project-a/runs*', route => respond(route, {
    summary: { agent_runs: 0, direct_agent_runs: 0, network_agent_runs: 0, network_runs: 0,
      active_top_level_runs: 0, failed_top_level_runs: 0, top_level_runs: 0,
      failure_rate_percent: 0, p95_top_level_latency_ms: null, avg_agent_runs_per_network_run: null },
    direct_agent_runs: [], network_runs: [],
  }))
  const failures: string[] = []
  const accessibilityFailures: unknown[] = []
  page.on('pageerror', error => failures.push(error.message))
  for (const [segment, title] of [
    ['knowledge', 'Knowledge'], ['tools', 'Tools'], ['skills', 'Skills'],
    ['models', 'Models'], ['credentials', 'Credentials'], ['api-keys', 'API Keys'],
    ['chat-surfaces', 'ChatSurfaces'], ['environments', 'Environments'],
    ['usage', 'Usage'], ['traces', 'Runs'],
  ]) {
    await page.goto(`${root}/${segment}`)
    await expect(page.getByRole('heading', { name: title, level: 1, exact: true })).toBeVisible()
    await expect(page.getByText('Something went wrong', { exact: true })).not.toBeVisible()
    const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
    accessibilityFailures.push(...audit.violations.map(({ id, nodes }) => ({ surface: segment, id, targets: nodes.map(node => ({ target: node.target, summary: node.failureSummary })) })))
    await capture(page, segment)
  }
  expect(failures).toEqual([])
  expect(accessibilityFailures).toEqual([])
})

test('Agent and Network workspaces keep release context and their separate runtime surfaces', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await demo(page)
  await page.goto(`${root}/agents`)
  await page.getByRole('button', { name: /Open Agent playground/ }).click()
  await page.getByRole('group', { name: 'Agent environment' }).getByRole('button', { name: 'PRODUCTION', exact: true }).click()
  await expect(page.getByText('Using: Production · 1.2.0', { exact: true })).toBeVisible()
  await capture(page, 'agent-playground')
  await page.goto(`${root}/networks`)
  await page.getByRole('button', { name: 'Open Network workspace for Customer Support' }).click()
  await expect(page).toHaveURL(/networks\/network-support$/)
  await expect(page.getByRole('heading', { name: 'Customer Support', level: 1, exact: true })).toBeVisible()
  await capture(page, 'network-workspace')
})
