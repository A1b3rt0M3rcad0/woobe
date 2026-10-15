import { expect, type Page } from '@playwright/test'
import { installApi } from '../fixtures/control-plane'

/** Change the real preference in another tab without leaving an unsaved workspace. */
export async function themeSettingsFor(page: Page) {
  const settings = await page.context().newPage()
  await installApi(settings)
  await settings.goto(new URL('/settings', page.url()).href)
  const modal = settings.getByRole('dialog', { name: 'Account settings', exact: true })
  await expect(modal).toBeVisible()
  return async (preference: 'light' | 'dark') => {
    await modal.getByLabel('Theme', { exact: true }).selectOption(preference)
    await expect(page.locator('html')).toHaveAttribute('data-theme', preference)
  }
}
