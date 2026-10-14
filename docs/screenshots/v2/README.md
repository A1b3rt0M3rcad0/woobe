# Guild v2 rendered evidence

These are real Chromium captures of production components with synthetic API data. See [method and commands](../README.md), [visual contract](../../design/README.md) and [review results](../../design/REVIEW.md).

618 PNG captures. Desktop: 1440px; tablet: 768px; mobile: 390px. Public pages also include their full mobile document. Scroll sequences preserve the real viewport and scrolling behavior; read each folder in order. Section captures expose internal navigation; pan captures continue horizontal navigation.

Open [the searchable gallery](index.html) through a static HTTP server for thumbnails, or follow the links below.

## Pages

| Route | Component | Evidence |
| --- | --- | --- |
| `/login` | LoginPage | [sign-in](pages/sign-in/) |
| `/register` | RegisterPage | [register](pages/register/) |
| `/workspaces` | WorkspacesPage | [workspaces](pages/workspaces/) |
| `/workspaces/:workspaceId/settings` | WorkspaceDetailPage | [workspace-settings](pages/workspace-settings/) |
| `/workspaces/:workspaceId/projects` | WorkspaceProjectsPage | [workspace-projects](pages/workspace-projects/) |
| `/workspaces/:workspaceId/setup` | FirstRunSetupPage | [workspace-setup](pages/workspace-setup/) |
| `/workspaces/:workspaceId/projects/:projectId` | DashboardPage | [overview](pages/overview/) |
| `/workspaces/:workspaceId/projects/:projectId/setup` | FirstRunSetupPage | [project-setup](pages/project-setup/) |
| `/workspaces/:workspaceId/projects/:projectId/settings` | WorkspaceProjectDetailPage | [project-settings](pages/project-settings/) |
| `/workspaces/:workspaceId/projects/:projectId/networks` | NetworksPage | [networks](pages/networks/) |
| `/workspaces/:workspaceId/projects/:projectId/networks/:networkId` | NetworkWorkspaceRoute | [network-workspace](pages/network-workspace/) |
| `/workspaces/:workspaceId/projects/:projectId/agents` | AgentsPage | [agents](pages/agents/) |
| `/workspaces/:workspaceId/projects/:projectId/agents/:agentId/playground` | AgentPlaygroundPage | [playground](pages/playground/) |
| `/workspaces/:workspaceId/projects/:projectId/knowledge` | KnowledgePage | [knowledge](pages/knowledge/) |
| `/workspaces/:workspaceId/projects/:projectId/tools` | ToolsPage | [tools](pages/tools/) |
| `/workspaces/:workspaceId/projects/:projectId/skills` | SkillsPage | [skills](pages/skills/) |
| `/workspaces/:workspaceId/projects/:projectId/models` | ModelsPage | [models](pages/models/) |
| `/workspaces/:workspaceId/projects/:projectId/environments` | ProjectEnvironmentsPage | [environments](pages/environments/) |
| `/workspaces/:workspaceId/projects/:projectId/credentials` | CredentialsPage | [credentials](pages/credentials/) |
| `/workspaces/:workspaceId/projects/:projectId/api-keys` | ApiKeysPage | [api-keys](pages/api-keys/) |
| `/workspaces/:workspaceId/projects/:projectId/chat-surfaces` | ChatSurfacesPage | [chat-surfaces](pages/chat-surfaces/) |
| `/workspaces/:workspaceId/projects/:projectId/usage` | UsagePage | [usage](pages/usage/) |
| `/workspaces/:workspaceId/projects/:projectId/traces` | TracesPage | [traces](pages/traces/) |
| `/mcp/oauth/callback` | McpConnectCallbackPage | [mcp-callback](pages/mcp-callback/) |
| `/settings` | SettingsPage | [account-settings](pages/account-settings/) |
| `*` | NotFoundPage | [not-found](pages/not-found/) |

## Shared component groups

- [buttons](components/buttons.png): Button.
- [badges](components/badges.png): Badge, Separator, TechnicalListItem.
- [fields](components/fields.png): Field, Input, InputGroup, Select, Textarea, Checkbox, ReadOnlyField, FormActions.
- [panels](components/panels.png): DotMeter, SectionBlock, PanelHeader, Card, MetricTile, OperationalResourceCard, CreateResourceCard.
- [tables](components/tables.png): PageHeader, ResourcePage, Tabs, Table, Stepper, SegmentedControl.
- [feedback](components/feedback.png): Alert, Skeleton, LoadingState, EmptyStatePanel, GuidedEmptyState.
- [code](components/code.png): CodePanel, JsonCodeBlock, CopyButton, JsonEditor, MathSurface.
- [dates](components/dates.png): WoobeDatePicker, WoobeDateTimePicker.
- [dropdown](components/dropdown.png): Dropdown.
- [resource-shell](components/resource-shell.png): ScrollArea.

Font probes: [capture](components/fonts.png), [actual rendered families and glyphs](fonts.json).

## Open overlays

| Production component / host | Evidence |
| --- | --- |
| Dialog | [3 captures](overlays/Dialog/) |
| Drawer | [3 captures](overlays/Drawer/) |
| DangerConfirmDialog | [3 captures](overlays/DangerConfirmDialog/) |
| ConfigurationValueEditor | [3 captures](overlays/ConfigurationValueEditor/) |
| CreateProjectDialog | [3 captures](overlays/CreateProjectDialog/) |
| CreateWorkspaceDialog | [3 captures](overlays/CreateWorkspaceDialog/) |
| AgentBehaviorFieldDialog | [3 captures](overlays/AgentBehaviorFieldDialog/) |
| AgentContextConfigurationDialog | [3 captures](overlays/AgentContextConfigurationDialog/) |
| AgentModelManagerModal | [3 captures](overlays/AgentModelManagerModal/) |
| CreateAgentFlowModal | [4 captures](overlays/CreateAgentFlowModal/) |
| CreateApiKeyDialog | [3 captures](overlays/CreateApiKeyDialog/) |
| RotateApiKeyDialog | [3 captures](overlays/RotateApiKeyDialog/) |
| AccountSettingsDialog | [3 captures](overlays/AccountSettingsDialog/) |
| ChatSurfaceDetailsModal | [24 captures](overlays/ChatSurfaceDetailsModal/) |
| ChatSurfaceLiveTestDialog | [6 captures](overlays/ChatSurfaceLiveTestDialog/) |
| ManualModelModal | [3 captures](overlays/ManualModelModal/) |
| ProviderConnectionModal | [3 captures](overlays/ProviderConnectionModal/) |
| AttachCollectionModal | [3 captures](overlays/AttachCollectionModal/) |
| BuildVectorSnapshotModalV2 | [4 captures](overlays/BuildVectorSnapshotModalV2/) |
| CollectionDetailsModal | [5 captures](overlays/CollectionDetailsModal/) |
| CollectionDetailsModalV2-CollectionDetailsModal | [6 captures](overlays/CollectionDetailsModalV2-CollectionDetailsModal/) |
| CollectionDocumentUploadModal | [3 captures](overlays/CollectionDocumentUploadModal/) |
| CreateCollectionModal | [3 captures](overlays/CreateCollectionModal/) |
| CreateEmbeddingModelModal | [3 captures](overlays/CreateEmbeddingModelModal/) |
| DocumentsDrawer | [3 captures](overlays/DocumentsDrawer/) |
| SelectKnowledgeVersionModal | [3 captures](overlays/SelectKnowledgeVersionModal/) |
| UploadDocumentModal | [3 captures](overlays/UploadDocumentModal/) |
| VectorSnapshotDetailsModal | [3 captures](overlays/VectorSnapshotDetailsModal/) |
| NetworkAgentCatalogDrawer | [3 captures](overlays/NetworkAgentCatalogDrawer/) |
| NetworkApiModal | [18 captures](overlays/NetworkApiModal/) |
| NetworkDraftConflictDialog | [3 captures](overlays/NetworkDraftConflictDialog/) |
| NetworkInspectorModal | [3 captures](overlays/NetworkInspectorModal/) |
| NetworkPromotionDialogV2-NetworkPromotionDialog | [3 captures](overlays/NetworkPromotionDialogV2-NetworkPromotionDialog/) |
| NetworkReleaseDialogs-NetworkReleaseModal | [3 captures](overlays/NetworkReleaseDialogs-NetworkReleaseModal/) |
| NetworkReleaseDialogs-UnsavedAgentSwitchDialog | [3 captures](overlays/NetworkReleaseDialogs-UnsavedAgentSwitchDialog/) |
| NetworkRemoveDialog | [3 captures](overlays/NetworkRemoveDialog/) |
| NetworkRollbackDialog | [3 captures](overlays/NetworkRollbackDialog/) |
| NetworkRuntimeControlsPopover | [3 captures](overlays/NetworkRuntimeControlsPopover/) |
| NetworkUnsavedChangesDialog | [3 captures](overlays/NetworkUnsavedChangesDialog/) |
| NetworkVersionsModalV2-NetworkVersionsModal | [7 captures](overlays/NetworkVersionsModalV2-NetworkVersionsModal/) |
| AgentControlsPopover | [3 captures](overlays/AgentControlsPopover/) |
| AgentManagerModal | [5 captures](overlays/AgentManagerModal/) |
| ApiModal | [18 captures](overlays/ApiModal/) |
| ConfirmDeleteModal | [3 captures](overlays/ConfirmDeleteModal/) |
| ConfirmVersionModal | [3 captures](overlays/ConfirmVersionModal/) |
| CreateReleaseDialog | [3 captures](overlays/CreateReleaseDialog/) |
| CreateToolModal | [3 captures](overlays/CreateToolModal/) |
| EditHttpGroupModal | [4 captures](overlays/EditHttpGroupModal/) |
| EditToolModal | [5 captures](overlays/EditToolModal/) |
| ImportToolsModal | [3 captures](overlays/ImportToolsModal/) |
| ManageKnowledgeModal | [5 captures](overlays/ManageKnowledgeModal/) |
| OutputContractHelpModal | [6 captures](overlays/OutputContractHelpModal/) |
| ProductionChangesModal | [3 captures](overlays/ProductionChangesModal/) |
| ReleaseLibraryModal | [3 captures](overlays/ReleaseLibraryModal/) |
| ReleaseSnapshotModal | [10 captures](overlays/ReleaseSnapshotModal/) |
| StageDraftSnapshotModal | [6 captures](overlays/StageDraftSnapshotModal/) |
| ConfigurationKeyDeclarationDialog | [3 captures](overlays/ConfigurationKeyDeclarationDialog/) |
| ConfigurationUsageDialog | [3 captures](overlays/ConfigurationUsageDialog/) |
| ProjectSettingsDialog | [5 captures](overlays/ProjectSettingsDialog/) |
| AddProviderCredentialModal | [3 captures](overlays/AddProviderCredentialModal/) |
| RotateProviderCredentialDialog | [3 captures](overlays/RotateProviderCredentialDialog/) |
| ModelSettingsModal | [8 captures](overlays/ModelSettingsModal/) |
| RuntimeApiReferenceModal | [12 captures](overlays/RuntimeApiReferenceModal/) |
| ManageSkillsDialog | [3 captures](overlays/ManageSkillsDialog/) |
| ToolSettingsModal | [5 captures](overlays/ToolSettingsModal/) |
| WorkspaceSettingsDialog | [5 captures](overlays/WorkspaceSettingsDialog/) |
| ToolsCreateDialog | [3 captures](overlays/ToolsCreateDialog/) |
| RagRuntimeSettings | [8 captures](overlays/RagRuntimeSettings/) |
| ConfigurationBatchEditor | [3 captures](overlays/ConfigurationBatchEditor/) |
| ManageSkills-Create | [3 captures](overlays/ManageSkills-Create/) |
| ManageSkills-Import | [3 captures](overlays/ManageSkills-Import/) |
| host-agent-result | [6 captures](overlays/host-agent-result/) |
| host-config-legacy | [3 captures](overlays/host-config-legacy/) |
| host-network-history | [6 captures](overlays/host-network-history/) |
| host-context-manager | [4 captures](overlays/host-context-manager/) |
| host-execution-strategy | [3 captures](overlays/host-execution-strategy/) |
| host-field-description | [3 captures](overlays/host-field-description/) |
| host-runtime-context | [3 captures](overlays/host-runtime-context/) |
| host-agent-snapshot | [3 captures](overlays/host-agent-snapshot/) |
| host-http-routes | [3 captures](overlays/host-http-routes/) |
| host-mcp-tools | [3 captures](overlays/host-mcp-tools/) |
| McpInputBindings | [desktop, tablet, mobile](overlays/McpInputBindings/) |
| CollectionDeleteDocument | [desktop, tablet, mobile](overlays/CollectionDeleteDocument/) |
| ConfigurationApproveUse | [desktop, tablet, mobile](overlays/ConfigurationApproveUse/) |
| ConfigurationRevokeUse | [desktop, tablet, mobile](overlays/ConfigurationRevokeUse/) |
| OverviewRuntimeCostCoverage | [desktop, tablet, mobile](overlays/OverviewRuntimeCostCoverage/) |
| SkillVersionReview | [desktop, tablet, mobile](overlays/SkillVersionReview/) |
| SkillChooseAgent | [desktop, tablet, mobile](overlays/SkillChooseAgent/) |
| ConfigurationDiscardValue | [desktop, tablet, mobile](overlays/ConfigurationDiscardValue/) |
| ConfigurationDiscardBatch | [desktop, tablet, mobile](overlays/ConfigurationDiscardBatch/) |
| AsacDiscardLocalEdits | [desktop, tablet, mobile](overlays/AsacDiscardLocalEdits/) |

Additional flows: [creation and confirmations](flows/), [interactive and loading/error states](states/), [expanded JSON](overlays/JsonCodeBlock/), [open dropdown](overlays/Dropdown/).

Unrouted compatibility modules are listed separately in [coverage.json](../../design/coverage.json); they are not counted as additional pages. Browser-native title hints retain native rendering. No custom tooltip implementation exists to capture independently.
