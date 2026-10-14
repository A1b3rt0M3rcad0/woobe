// Shared synthetic API data. Safe to import in the browser review harness.
export const now = '2026-06-20T12:00:00Z'
export const user = { id: 'user-a', email: 'owner-a@example.test', status: 'active' }
export const workspace = {
  id: 'workspace-a', name: 'Woobe Test Workspace', slug: 'woobe-test', status: 'active',
  membership_role: 'owner', can_manage_workspace: true, accessible_project_count: 1,
  access_mode: 'implicit_owner',
}
export const project = {
  id: 'project-a', workspace_id: workspace.id, name: 'Release Project',
  slug: 'release-project', status: 'active', workspace_role: 'owner', access_source: 'workspace',
}
const emptyNetworkDefinition = {
  schema_version: 2,
  root_node_id: '',
  nodes: [],
  edges: [],
  settings: { session_mode: 'stateful', max_depth: 8, max_invocations: 32, timeout_seconds: 120 },
}
export const networks = [
  {
    id: 'network-support', project_id: project.id, name: 'Customer Support',
    description: 'Handles customer requests.', draft_definition: emptyNetworkDefinition,
    draft_revision: 0, staging_version_id: null, production_version_id: null,
    agent_count: 0, created_at: now, updated_at: now,
  },
  {
    id: 'network-onboarding', project_id: project.id, name: 'Customer Onboarding',
    description: 'Guides new customers.', draft_definition: emptyNetworkDefinition,
    draft_revision: 0, staging_version_id: null, production_version_id: null,
    agent_count: 0, created_at: now, updated_at: now,
  },
]

export const overview = {
  project_id: project.id, generated_at: now, from: now, to: now,
  bucket: 'hour', environment: 'all',
  summary: {
    active_agents: 0, production_agents: 0, network_count: networks.length,
    staging_networks: 0, production_networks: 0, network_runs: 0,
    failed_network_runs: 0, requests: 0, request_change_percent: 0,
    avg_latency_ms: 0, p95_latency_ms: 0, success_rate: 100,
    failed_requests: 0, cost_usd: 0, unknown_cost_count: 0,
  },
  timeseries: [],
  environment_distribution: { draft: 0, staging: 0, production: 0 },
  recent_releases: [], recent_traces: [],
  knowledge_summary: {
    collections: 0, documents: 0, indexed_documents: 0,
    failed_documents: 0, storage_bytes: 0, pending_documents: 0,
  },
  tools_summary: { total: 0, active: 0, inactive: 0, recent_failures: [] },
  capabilities: { sessions_jobs: true, ingestion_pipeline: false, activity_feed: false },
}

export const productionAgent = {
  id: 'agent-asac', project_id: project.id, name: 'ASaC Production Agent', description: 'Selection UI acceptance',
  status: 'active', provider: 'custom', model: 'mutable-draft-model', session_mode: 'stateful', revision: 1,
  created_at: now, updated_at: now,
}
export const selectedRelease = {
  id: 'selected-release', project_id: project.id, agent_id: productionAgent.id, name: productionAgent.name,
  version: '1.2.0', status: 'released', snapshot_kind: 'release', provider: 'custom', model: 'frozen-release-model',
  session_mode: 'stateless', runtime_config: {}, created_at: now,
}
