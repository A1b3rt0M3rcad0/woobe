import { expect, test } from '@playwright/test'
import { installApi, respond } from '../fixtures/control-plane'

for (const theme of ['light', 'dark']) test(`operational conversation, structured results and deep traces in ${theme}`, async ({ page }) => {
  await installApi(page, { asacAgent: true })
  await page.route('**/network/executions/network-design/diagnostics?*', route => respond(route, {
    schema_version: 1, execution_id: 'network-design', status: 'completed', network_wall_latency_ms: 18000,
    agent_work_latency_ms: 15210, llm_runtime_latency_ms: 14000, tool_work_latency_ms: 0,
    prepare_latency_ms: null, persistence_latency_ms: null, orchestration_latency_ms: null,
    agent_run_count: 9, delegation_count: 8, max_depth: 8, max_fan_out: 1,
    llm_call_count: 9, tool_call_count: 0, successful_tool_calls: 0, failed_tool_calls: 0,
    input_tokens: 17919, output_tokens: 900, total_tokens: 18819, usage_complete: true,
    cost_usd: null, cost_status: 'unknown', fallback_count: 0, source_count: 0, telemetry_status: 'complete',
    context: { telemetry_status: 'complete', model_invocation_count: 9, input_units: 17919,
      input_measurement: 'reported', peak_utilization: .2, median_utilization: .1, budget_unknown_count: 0,
      health_warning_count: 0, compaction_saving_units: 0, truncation_count: 0, selection_ratio: null,
      source_units: { SYSTEM: { units: 17082, share: 1898/1899 }, USER_INPUT: { units: 9, share: 1/1899 } }, agents: [] },
  }))
  await page.goto('/review.html?case=workspace')
  await page.getByLabel('Theme', { exact: true }).selectOption(theme)
  const conversation = page.getByRole('region', { name: 'Conversation review' })
  const diagnostics = page.getByRole('region', { name: 'Network diagnostics' })
  await expect(diagnostics.getByText('Cost unavailable', { exact: true })).toBeVisible()
  await expect(diagnostics.locator('[data-contribution-bars]')).toContainText('0.05%')
  await expect(conversation.getByText(/1 required context field is missing/)).toBeVisible()
  await conversation.getByRole('button', { name: 'Review External Context' }).click()
  await expect(conversation.getByText('Session fields are set once and reused automatically. Run fields may change on each Run.')).toBeVisible()
  await page.getByLabel('Scenario').selectOption('short')
  await expect(conversation.getByText('Request reviewed with the available evidence.')).toBeVisible()
  await page.getByLabel('Scenario').selectOption('long')
  await expect(conversation.getByText(/Conversation message 39/)).toBeVisible()
  await page.getByLabel('Scenario').selectOption('structured')
  await expect(conversation.getByText('Structured response', { exact: true })).toBeVisible()
  await conversation.getByRole('button', { name: 'Expand JSON', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Structured response', exact: true })
  await expect(dialog).toBeVisible()
  await expect(dialog.locator('.cm-editor')).toHaveCSS('background-color', theme === 'dark' ? 'rgb(23, 25, 21)' : 'rgb(234, 230, 223)')
  await page.keyboard.press('Escape')
  await expect(conversation.getByRole('button', { name: 'Expand JSON', exact: true })).toBeFocused()
  await page.getByLabel('Scenario').selectOption('running')
  await conversation.getByRole('button', { name: 'Stop generation' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Stop requested' })).toBeVisible()
  await page.getByLabel('Scenario').selectOption('error')
  await expect(conversation.getByText('The provider could not complete this Run. Your conversation is preserved.')).toBeVisible()
  await page.getByLabel('Scenario').selectOption('blocked')
  await expect(conversation.getByLabel('Message', { exact: true })).toBeDisabled()
  const tree = page.getByRole('region', { name: 'Deep invocation tree' })
  for (let i = 0; i < 8; i++) await tree.getByRole('button', { name: 'Expand invocation', exact: true }).first().click()
  await expect(tree.getByText('Delegation depth 8')).toBeVisible()
  const widths = await tree.locator('article').evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().width))
  expect(Math.max(...widths) - Math.min(...widths)).toBeLessThanOrEqual(20)
  await expect(tree.getByText('Customer Operations Evidence Specialist with a long name 8', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
})
