import { productionAgent, selectedRelease, networks, project, workspace, now } from '../fixtures/control-plane-data'
import { DEFAULT_CHAT_SURFACE_APPEARANCE } from '../../../packages/woobe-frontend/src/features/chat-surfaces/appearance'
import { agentToEditorState, canonicalSnapshot } from '../../../packages/woobe-frontend/src/features/playground/AgentEditorContext'
import { behaviorFields } from '../../../packages/woobe-frontend/src/features/agents/behavior'

export { productionAgent, selectedRelease, networks, project, workspace, now }
export { credential, model, collection, snapshot, tool, surface, apiKey, networkVersion } from '../fixtures/resource-data'
import { credential, model, collection, snapshot, tool, surface, apiKey, networkVersion } from '../fixtures/resource-data'
export const state = agentToEditorState(productionAgent)
export const commonProps = {
  open: true, projectId: project.id, workspaceId: workspace.id, agentId: productionAgent.id, agent: productionAgent, agentName: productionAgent.name, networkId: networks[0].id,
  targetId: productionAgent.id, targetType: 'agent', targetName: productionAgent.name,
  collection, collectionId: collection.id, collectionName: collection.name, collectionIds: [collection], existingCollectionIds: [],
  snapshot, currentSnapshotId: snapshot.id, surface, surfaceId: surface.id, credential, existingCredentials: [credential], credentials: [credential], selectedModel: model, selectedModelId: model.id,
  tool, importedToolIds: new Set(), externalContextFields: new Set(), projectEnvironmentKeys: new Set(), apiKey,
  generationCount: 1, embeddingCount: 0, loading: false, pending: false, isPending: false,
  agents: [productionAgent], addedAgentIds: new Set(), agentNames: [productionAgent.name], issues: [], definition: networks[0].draft_definition,
  draftDefinition: networks[0].draft_definition, draftRevision: 1, draftDirty: false, networkDirty: true,
  networkName: networks[0].name, versions: [networkVersion], stagingVersion: networkVersion, productionVersion: networkVersion, currentVersionId: networkVersion.id,
  bindings: { staging: {}, production: {} }, draftBindings: {}, stagingBindings: {}, action: 'stage', target: 'production',
  environment: 'draft', initialSection: 'overview', initialMode: 'browse', versionName: '1.2.0', release: selectedRelease, releases: [selectedRelease], lastRelease: selectedRelease, activations: [],
  currentSnapshot: canonicalSnapshot(state), state, hasUnsavedChanges: false, currentStaging: null,
  activeBinding: null, field: behaviorFields[0], value: 'Resolve support requests accurately.', managerName: 'Standard',
  title: 'Review configuration', description: 'Synthetic fixture for reviewing the production component.', impact: 'The selected resource will be removed.', confirmLabel: 'Confirm',
  item: { id: 'config-demo', key: 'SUPPORT_ENDPOINT', kind: 'value', value_format: 'url', definition_revision: 1, values: { draft: { configured: true, revision:1, material:'present' } } }, canApprove: true, canWrite: true, canClear: true,
  manageKeysPath: '/workspaces/workspace-a/projects/project-a/api-keys',
  environments: { draft: { enabled: true, available: true, version: '1.2.0', summary: [], request: {input:'Hello'}, response: {output:'Hello'}, streamEvents: [] }, staging: { enabled: true, available: true, version: '1.2.0', summary: [], request: {input:'Hello'}, response: {output:'Hello'}, streamEvents: [] }, production: { enabled: true, available: true, version: '1.2.0', summary: [], request: {input:'Hello'}, response: {output:'Hello'}, streamEvents: [] } },
  workspaceProjectPathFn: (_id: string, ...segments: string[]) => `/workspaces/${workspace.id}/projects/${project.id}/${segments.join('/')}`,
}
