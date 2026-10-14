import { test, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { installApi, login, respond, project, workspace, now } from '../fixtures/control-plane'
import { installResources } from '../fixtures/resource-api'
import { projectOverviewFixture } from '../../../packages/woobe-frontend/src/features/dashboard/fixtures'
import { captureScrollSequence, resetCaptures } from './capture'

for (const width of [1440, 768, 390]) test(`page-owned cost coverage and Skill installation at ${width}px`, async ({ page }) => {
  test.setTimeout(45_000)
  await page.setViewportSize({ width, height: 1100 })
  await installApi(page, { asacAgent: true })
  await installResources(page)
  const fixture = structuredClone(projectOverviewFixture)
  Object.assign(fixture.summary, { agent_run_cost_usd: null, unknown_agent_run_cost_count: 58, unknown_pricing_agent_runs: 58, terminal_agent_runs: 58, priced_agent_runs: 0 })
  await page.route('**/core/projects/project-a/overview*', route => respond(route, fixture))
  const version = { id: 'skill-version-demo', skill_id: 'skill-demo', skill_version_id: 'skill-version-demo', project_id: project.id, version: '1.0.0', name: 'Support review', description: 'Review support answers against the handbook.', package_hash: 'a'.repeat(64), required_tools: [], estimated_instruction_units: 120, resource_paths: [], created_at: now,
    package: { name: 'Support review', description: 'Review support answers against the handbook.', instructions: 'Verify the answer against the handbook.', skill_md: '# Support review\n\nVerify the answer against the handbook.', resources: {}, required_tools: [] } }
  await page.route('**/skills/**/versions*', route => respond(route, [version]))
  await page.route('**/skills/versions/skill-version-demo', route => respond(route, version))
  const save = async (name: string) => {
    const dialog = page.getByRole('dialog').last()
    await expect(dialog).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    const bounds = await dialog.boundingBox()
    expect(bounds!.x).toBeGreaterThanOrEqual(0)
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width + 1)
    const directory = resolve(process.cwd(), '../../docs/screenshots/v2/overlays', name)
    if (process.env.WOOBE_CAPTURE_DOCS === '1') {
      await mkdir(directory, { recursive: true }); await resetCaptures(directory, `${width}px`)
      await page.screenshot({ path: resolve(directory, `${width}px.png`), animations: 'disabled' })
      await captureScrollSequence(page, dialog, directory, `${width}px`)
    }
  }
  await login(page)
  const root = `/workspaces/${workspace.id}/projects/${project.id}`
  await page.goto(root)
  await page.getByRole('button', { name: 'Runtime cost details' }).click()
  await save('OverviewRuntimeCostCoverage')
  await page.goto(`${root}/skills`)
  await page.getByRole('button', { name: 'Open Skill Support review', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Install on Agent', exact: true })).toBeEnabled()
  await save('SkillVersionReview')
  await page.getByRole('button', { name: 'Install on Agent', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Choose an Agent' })).toBeVisible()
  await save('SkillChooseAgent')
  await page.goto('/review.html?case=ConfigurationValueEditor')
  await page.locator('#configuration-value').fill('synthetic-local-value')
  await page.getByRole('button',{name:'Cancel',exact:true}).click()
  await save('ConfigurationDiscardValue')
  await page.getByRole('dialog').last().getByRole('button',{name:'Cancel',exact:true}).click()
  await expect(page.locator('#configuration-value')).toHaveValue('synthetic-local-value')
  await page.getByRole('button',{name:'Cancel',exact:true}).click()
  await page.getByRole('button',{name:'Discard value',exact:true}).click()
  await page.goto('/review.html?case=ConfigurationBatchEditor')
  await page.locator('#batch-batch-demo').fill('https://example.test/local')
  await page.getByRole('button',{name:'Cancel',exact:true}).click()
  await save('ConfigurationDiscardBatch')
  await page.getByRole('dialog').last().getByRole('button',{name:'Cancel',exact:true}).click()
  await page.getByRole('button',{name:'Cancel',exact:true}).click()
  await page.getByRole('button',{name:'Discard values',exact:true}).click()
  const draft={draft_id:'draft-demo',resource_uid:'network-support',name:'Review Draft',generation:2,working_revision_id:null,origin:{},definition_digest:'demo-digest'}
  await page.route('**/asac/**',route=>{
    const path=new URL(route.request().url()).pathname
    if(!path.startsWith('/projects/'))return route.fallback()
    return respond(route,path.endsWith('/editor') ? {draft:{...draft,generation:1},entrypoint_path:'author.yaml',files:[{path:'author.yaml',content:'kind: Network',editable:true}]} : path.endsWith('/drafts') ? {drafts:[draft]} : path.endsWith('/drafts/draft-demo') ? draft : {schema_version:'1.0',resource_id:'network-support',kind:'Network',environment:'production',snapshot_id:null,environment_generation:0,selection_authority:'asac',remote_status:'verified',complete:true})
  })
  await page.goto('/review.html?case=host-network-history')
  await page.getByRole('combobox',{name:'Isolated Draft',exact:true}).selectOption('draft-demo')
  await page.getByRole('button',{name:'Load saved files',exact:true}).click()
  await page.getByRole('textbox',{name:'Author YAML',exact:true}).fill('kind: Network\nname: local-review')
  await page.getByRole('button',{name:'Discard local edits',exact:true}).click()
  await save('AsacDiscardLocalEdits')
  await page.getByRole('dialog').last().getByRole('button',{name:'Cancel',exact:true}).click()
  await expect(page.getByRole('textbox',{name:'Author YAML',exact:true})).toHaveValue('kind: Network\nname: local-review')
  await page.getByRole('button',{name:'Discard local edits',exact:true}).click()
  await page.getByRole('dialog').last().getByRole('button',{name:'Discard local edits',exact:true}).click()
  await expect(page.getByText('Local edits discarded. Load the current saved files explicitly.')).toBeVisible()
})
