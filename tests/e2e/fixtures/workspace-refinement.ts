import type { Page } from '@playwright/test'
import { installApi, networks, now, productionAgent, project, respond, workspace } from './control-plane'

export const projectRoot = `/workspaces/${workspace.id}/projects/${project.id}`
export const playgroundPath = `${projectRoot}/agents/${productionAgent.id}/playground`
export const networkPath = `${projectRoot}/networks/network-support`
export const longNodeName = 'Customer Operations Request Orchestrator'

export async function installWorkspaceRefinement(page: Page, options: {
  cost?: number | null; costStatus?: string; units?: number[]; tokens?: number; nodes?: number
} = {}) {
  await installApi(page, { asacAgent: true })
  const cost = options.cost === undefined ? null : options.cost
  const costStatus = options.costStatus ?? 'unknown_pricing'
  const units = options.units ?? [1898, 1]
  const tokens = options.tokens ?? 2091
  const run = {
    id: 'run-design', trace_id: 'trace-design', project_id: project.id, agent_id: productionAgent.id,
    session_id: null, environment: 'draft', origin: 'playground', status: 'completed', input_message: 'Review this customer request.',
    provider: 'custom', model: 'review-model-with-a-long-technical-identifier', started_at: now, completed_at: now, created_at: now,
    latency_ms: 1690, usage: { total_tokens: tokens, input_tokens: tokens - 100, output_tokens: 100, cost_usd: cost },
    answer: 'Request reviewed. No execution error was reported.', tool_calls: [], sources: [], llm_calls: [{}],
    diagnostics: { cost_usd: cost, cost_status: costStatus, agent_runtime_latency_ms: 1690, total_tokens: tokens, llm_call_count: 1, tool_call_count: 0, source_count: 0, usage_complete: true },
  }
  await page.route('**/runtime/runs?*', route => respond(route, [run]))
  await page.route('**/runtime/runs/run-design', route => respond(route, run))
  await page.route('**/runtime/runs/run-design/model-invocations', route => respond(route, units.length ? [{
    id: 'invocation-design', call_index: 1, phase: 'response', provider: run.provider, model: run.model,
    status: 'completed', latency_ms: 1690, input_units: 1991, output_units: 100, total_units: tokens, cost_usd: cost,
    context_snapshot: { id: 'context-design', estimated_input_units: 1899, reported_input_units: 1991, measurement_status: 'reported',
      usable_input_budget: 16000, utilization: .124, manifest: { metrics: { context_fit_status: 'FIT' } },
      contributions: units.map((value, index) => ({ source_type: ['SYSTEM', 'USER_INPUT', 'TOOL', 'KNOWLEDGE'][index] ?? 'MEMORY', source_ref: null, materialized_units: value })),
    },
  }] : []))
  const count = options.nodes ?? 5
  const nodes = Array.from({ length: count }, (_, i) => ({
    id: `node-${i}`, agent_id: productionAgent.id,
    label: i === 0 ? longNodeName : ['Knowledge Research and Evidence', 'Billing and Payment Specialist', 'Technical Support Specialist', 'Customer Context Researcher'][i - 1] ?? `Additional specialist ${i}`,
    capability_description: i === 0 ? 'Interpret the request and delegate to the appropriate specialists.' : 'Investigate customer evidence and return a structured result.',
    position: { x: i === 0 ? 80 : 500 + Math.floor((i - 1) / 3) * 400, y: i === 0 ? 260 : ((i - 1) % 3) * 270 },
    binding: { source: 'draft', release_id: null },
  }))
  const composed = { ...networks[0], agent_count: count, draft_revision: 2, draft_definition: { ...networks[0].draft_definition,
    root_node_id: nodes[0].id, nodes, edges: nodes.slice(1).map((node, i) => ({ id: `edge-${i}`, source_node_id: nodes[0].id, target_node_id: node.id })),
  } }
  await page.route('**/network/projects/project-a/networks/network-support', route => respond(route, composed))
}
