import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Locator, type Page } from '@playwright/test'
import { installApi, login, project, respond, workspace } from '../fixtures/control-plane'
import { projectOverviewFixture } from '../../../packages/woobe-frontend/src/features/dashboard/fixtures'

function luminance(color: string) {
  const values = color.match(/[\d.]+/g)!.slice(0, 3).map(Number).map(value => {
    const channel = value / 255
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  })
  return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722
}
function contrast(first: string, second: string) {
  const values = [luminance(first), luminance(second)].sort((a, b) => b - a)
  return (values[0] + 0.05) / (values[1] + 0.05)
}
async function colors(locator: Locator) {
  return locator.evaluate(element => {
    const style = getComputedStyle(element)
    return { background: style.backgroundColor, text: style.color, outline: style.outlineColor, outlineStyle: style.outlineStyle }
  })
}
async function navigation(page: Page, width: number, label: string) {
  if (width < 1024) await page.getByRole('button', { name: 'Open navigation', exact: true }).click()
  await expect(page.getByRole('navigation', { name: label })).toBeVisible()
  return page.locator('aside.woobe-navigation:visible')
}

for (const width of [1440, 390]) test(`navigation keeps its dark surface and dialogs retain light surfaces at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1100 })
  await installApi(page, { asacAgent: true })
  await page.route('**/core/projects/project-a/overview*', route => respond(route, projectOverviewFixture))
  await login(page)
  await page.goto(`/workspaces/${workspace.id}/projects`)
  const workspaceNav = await navigation(page, width, 'Workspace navigation')
  const workspaceColors = await colors(workspaceNav)
  expect(luminance(workspaceColors.background)).toBeLessThan(0.06)
  if (width < 1024) await page.keyboard.press('Escape')

  await page.goto(`/workspaces/${workspace.id}/projects/${project.id}`)
  const projectNav = await navigation(page, width, 'Project navigation')
  expect((await colors(projectNav)).background).toBe(workspaceColors.background)
  const overview = projectNav.getByRole('link', { name: 'Overview', exact: true })
  await expect(overview).toHaveAttribute('aria-current', 'page')
  const activeColors = await colors(overview)
  expect(contrast(activeColors.text, activeColors.background)).toBeGreaterThanOrEqual(4.5)

  await projectNav.getByRole('button', { name: 'Open account settings', exact: true }).click()
  const account = page.getByRole('dialog', { name: 'Account settings', exact: true })
  await expect(account).toBeVisible()
  expect(luminance((await colors(account)).background)).toBeGreaterThan(0.85)
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  expect(audit.violations).toEqual([])
  await page.keyboard.press('Escape')
  await expect(account).not.toBeVisible()
  const accountTrigger = projectNav.getByRole('button', { name: 'Open account settings', exact: true })
  await expect(accountTrigger).toBeFocused()
  expect(contrast((await colors(accountTrigger)).outline, workspaceColors.background)).toBeGreaterThanOrEqual(3)
  await overview.focus()
  const focusedColors = await colors(overview)
  expect(focusedColors.outlineStyle).toBe('solid')
  expect(contrast(focusedColors.outline, focusedColors.background)).toBeGreaterThanOrEqual(3)
})
