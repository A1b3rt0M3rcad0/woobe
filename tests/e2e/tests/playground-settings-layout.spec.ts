import { expect, test, type Locator, type Page } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { installApi, login, now, productionAgent, project, respond, workspace } from '../fixtures/control-plane'
import { installResources } from '../fixtures/resource-api'
import { credential, model } from '../fixtures/resource-data'

const root = `/workspaces/${workspace.id}/projects/${project.id}`
const connection = {
  ...credential, name: 'DeepSeek', provider: 'deepseek', metadata: { base_url: 'https://api.deepseek.com' },
  authentication: { type: 'api_key', fields: { api_key: { source: 'project_environment', key: 'DEEPSEEK_API_KEY' } } },
}
const original = { ...model, spec: { operations: ['language.generate'], output_modalities: ['text'], interaction: { supports_conversation: true } }, provider: 'deepseek', name: 'DeepSeek V4.1 Flash with a long display name', model: 'deepseek-flash' }
const replacement = { ...original, id: 'replacement-model', name: 'Replacement model', model: 'deepseek-chat' }

async function prepare(page: Page) {
  await installApi(page, { asacAgent: true })
  await installResources(page)
  const saves: Record<string, any>[] = []
  const agent = { ...productionAgent, provider: 'deepseek', model: original.model, provider_model_id: original.id, provider_credential_id: connection.id, settings: { external_context_contract: {} } }
  await page.route('**/ai/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/ai/credentials') return respond(route, [connection])
    if (path === '/ai/provider-models') return respond(route, [original, replacement])
    if (path === `/ai/agents/${agent.id}`) return respond(route, agent)
    if (path === `/ai/agents/${agent.id}/releases` && route.request().method() === 'POST') {
      const body = route.request().postDataJSON()
      saves.push(body)
      Object.assign(agent, body)
      return respond(route, { ...body, id: 'saved-draft', status: 'draft', agent_revision: 2, created_at: now })
    }
    return route.fallback()
  })
  await login(page)
  return saves
}

async function inside(container: Locator, controls: Locator) {
  const bounds = (await container.boundingBox())!
  expect(await container.evaluate(el => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(1)
  for (const control of await controls.all()) {
    await expect(control).toBeVisible()
    const box = (await control.boundingBox())!
    expect(box.x).toBeGreaterThanOrEqual(bounds.x)
    expect(box.x + box.width).toBeLessThanOrEqual(bounds.x + bounds.width + 1)
  }
}

async function capture(page: Page, name: string, width: number) {
  if (process.env.WOOBE_CAPTURE_LAYOUT !== '1') return
  await mkdir('work/playground-layout-captures', { recursive: true })
  await page.screenshot({ path: `work/playground-layout-captures/${name}-${width}.png` })
}

for (const width of [1440, 768, 390]) {
  test(`Playground changes the primary model and saves its binding at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1100 })
    const saves = await prepare(page)
    await page.goto(`${root}/agents/${productionAgent.id}/playground?editor=model`)
    if (width < 1280) await page.getByRole('button', { name: 'Show inspector', exact: true }).click()
    const card = page.getByRole('region', { name: 'Model', exact: true })
    await inside(card, card.getByRole('button'))
    await capture(page, 'model', width)
    await card.getByRole('button', { name: 'Change primary model', exact: true }).click()
    const chooser = page.getByRole('dialog', { name: 'Manage models', exact: true })
    await chooser.getByPlaceholder('Search models...').fill(replacement.name)
    await inside(chooser, chooser.getByRole('button'))
    await chooser.getByRole('button', { name: 'Use model', exact: true }).click()
    await expect(chooser).toHaveCount(0)
    await expect(card.getByRole('group', { name: 'Primary model', exact: true })).toContainText(replacement.name)
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect.poll(() => saves.length).toBe(1)
    expect(saves[0]).toMatchObject({ version: 'draft', provider_model_id: replacement.id, provider_credential_id: connection.id, provider: 'deepseek', model: replacement.model })
    expect(saves[0]).not.toHaveProperty('model_spec_snapshot')
  })

  test(`External Context fields remain editable inside the Playground card at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1100 })
    const saves = await prepare(page)
    await page.goto(`${root}/agents/${productionAgent.id}/playground?editor=external-context`)
    if (width < 1280) await page.getByRole('button', { name: 'Show inspector', exact: true }).click()
    const card = page.getByRole('region', { name: 'External Context', exact: true })
    await inside(card, card.getByRole('button'))
    await card.getByRole('button', { name: 'Add field', exact: true }).click()
    await inside(card, card.locator('input,select,button'))
    await card.getByRole('textbox', { name: 'Field 1 name', exact: true }).fill('customer_id')
    await card.getByRole('combobox', { name: 'Field customer_id scope', exact: true }).selectOption('session')
    await card.getByRole('checkbox', { name: 'Field customer_id required', exact: true }).check()
    await card.getByRole('checkbox', { name: 'Field customer_id model visibility', exact: true }).check()
    await card.getByRole('button', { name: 'Edit customer_id description', exact: true }).click()
    const description = page.getByRole('dialog', { name: 'Field description', exact: true })
    await description.getByRole('textbox', { name: 'Field customer_id description', exact: true }).fill('The customer requesting support.')
    await description.getByRole('button', { name: 'Done', exact: true }).click()
    await capture(page, 'context', width)
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect.poll(() => saves.length).toBe(1)
    expect(saves[0].external_context_contract.customer_id).toMatchObject({ required: true, scope: 'session', model: { expose: true }, description: 'The customer requesting support.' })
    await card.getByRole('button', { name: 'Remove customer_id', exact: true }).click()
    await expect(card.getByRole('textbox')).toHaveCount(0)
    await inside(card, card.getByRole('button'))
  })

  test(`Credential actions stay inside the modal at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1100 })
    await prepare(page)
    await page.goto(`${root}/credentials`)
    await page.getByRole('button', { name: 'Open provider connection DeepSeek', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'DeepSeek', exact: true })
    await expect(dialog).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    await inside(dialog, dialog.getByRole('button'))
    for (const name of ['Edit', 'Manage approvals', 'Manage key values', 'Revoke', 'Archive']) {
      await expect(dialog.getByRole('button', { name, exact: true })).toBeInViewport({ ratio: 1 })
    }
    const metadata = dialog.getByText('2 generation · 0 embedding', { exact: true })
    expect((await metadata.boundingBox())!.height).toBeLessThan(40)
    await capture(page, 'credential', width)
    await dialog.getByRole('button', { name: 'Manage approvals', exact: true }).click()
    await expect(page.getByRole('dialog', { name: 'Access approvals · DEEPSEEK_API_KEY', exact: true })).toBeVisible()
  })
}
