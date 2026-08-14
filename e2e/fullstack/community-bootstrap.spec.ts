import { expect, test } from '@playwright/test'

const ownerEmail = 'owner-fullstack@example.test'
const ownerPassword = 'ReleaseGate123!'

test('bootstraps a fresh Community instance through the real stack', async ({ page }) => {
  await page.goto('/register')

  await page.getByPlaceholder('you@company.com').fill(ownerEmail)
  await page.getByPlaceholder('At least 6 characters').fill(ownerPassword)
  await page.getByRole('button', { name: 'Create account' }).click()

  await expect(page).toHaveURL(/\/workspaces\/[^/]+\/setup/)
  await expect(page.getByText('Woobe', { exact: true }).first()).toBeVisible()
})
