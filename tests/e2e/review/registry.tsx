import { AgentResultViewer } from '../../../packages/woobe-frontend/src/features/playground/components/AgentResultViewer'
import { RagRuntimeSettings } from '../../../packages/woobe-frontend/src/features/playground/components/RagRuntimeSettings'
import { ConfigurationBatchEditor } from '../../../packages/woobe-frontend/src/features/projects/components/ConfigurationBatchEditor'
import { ConfigurationLegacyPanel } from '../../../packages/woobe-frontend/src/features/projects/components/ConfigurationLegacyPanel'
import { AsacWorkbench } from '../../../packages/woobe-frontend/src/features/asac/AsacWorkbench'
import { CreateProjectDialog as Overlay0 } from '../../../packages/woobe-frontend/src/components/forms/CreateProjectDialog'
import { CreateWorkspaceDialog as Overlay1 } from '../../../packages/woobe-frontend/src/components/forms/CreateWorkspaceDialog'
import { AgentBehaviorFieldDialog as Overlay2 } from '../../../packages/woobe-frontend/src/features/agents/components/AgentBehaviorFieldDialog'
import { AgentContextConfigurationDialog as Overlay3 } from '../../../packages/woobe-frontend/src/features/agents/components/AgentContextConfigurationDialog'
import { AgentModelManagerModal as Overlay4 } from '../../../packages/woobe-frontend/src/features/agents/components/AgentModelManagerModal'
import { CreateAgentFlowModal as Overlay5 } from '../../../packages/woobe-frontend/src/features/agents/components/CreateAgentFlowModal'
import { CreateApiKeyDialog as Overlay6 } from '../../../packages/woobe-frontend/src/features/api-keys/components/CreateApiKeyDialog'
import { RotateApiKeyDialog as Overlay7 } from '../../../packages/woobe-frontend/src/features/api-keys/components/RotateApiKeyDialog'
import { AccountSettingsDialog as Overlay8 } from '../../../packages/woobe-frontend/src/features/auth/components/AccountSettingsDialog'
import { ChatSurfaceDetailsModal as Overlay9 } from '../../../packages/woobe-frontend/src/features/chat-surfaces/components/ChatSurfaceDetailsModal'
import { ChatSurfaceLiveTestDialog as Overlay10 } from '../../../packages/woobe-frontend/src/features/chat-surfaces/components/ChatSurfaceLiveTestDialog'
import { ManualModelModal as Overlay11 } from '../../../packages/woobe-frontend/src/features/first-run/components/ManualModelModal'
import { ProviderConnectionModal as Overlay12 } from '../../../packages/woobe-frontend/src/features/first-run/components/ProviderConnectionModal'
import { AttachCollectionModal as Overlay13 } from '../../../packages/woobe-frontend/src/features/knowledge/components/AttachCollectionModal'
import { BuildVectorSnapshotModalV2 as Overlay14 } from '../../../packages/woobe-frontend/src/features/knowledge/components/BuildVectorSnapshotModalV2'
import { CollectionDetailsModal as Overlay15 } from '../../../packages/woobe-frontend/src/features/knowledge/components/CollectionDetailsModal'
import { CollectionDetailsModal as Overlay16 } from '../../../packages/woobe-frontend/src/features/knowledge/components/CollectionDetailsModalV2'
import { CollectionDocumentUploadModal as Overlay17 } from '../../../packages/woobe-frontend/src/features/knowledge/components/CollectionDocumentUploadModal'
import { CreateCollectionModal as Overlay18 } from '../../../packages/woobe-frontend/src/features/knowledge/components/CreateCollectionModal'
import { CreateEmbeddingModelModal as Overlay19 } from '../../../packages/woobe-frontend/src/features/knowledge/components/CreateEmbeddingModelModal'
import { DocumentsDrawer as Overlay20 } from '../../../packages/woobe-frontend/src/features/knowledge/components/DocumentsDrawer'
import { SelectKnowledgeVersionModal as Overlay21 } from '../../../packages/woobe-frontend/src/features/knowledge/components/SelectKnowledgeVersionModal'
import { UploadDocumentModal as Overlay22 } from '../../../packages/woobe-frontend/src/features/knowledge/components/UploadDocumentModal'
import { VectorSnapshotDetailsModal as Overlay23 } from '../../../packages/woobe-frontend/src/features/knowledge/components/VectorSnapshotDetailsModal'
import { NetworkAgentCatalogDrawer as Overlay24 } from '../../../packages/woobe-frontend/src/features/network/components/NetworkAgentCatalogDrawer'
import { NetworkApiModal as Overlay25 } from '../../../packages/woobe-frontend/src/features/network/components/NetworkApiModal'
import { NetworkDraftConflictDialog as Overlay26 } from '../../../packages/woobe-frontend/src/features/network/components/NetworkDraftConflictDialog'
import { NetworkInspectorModal as Overlay27 } from '../../../packages/woobe-frontend/src/features/network/components/NetworkInspectorModal'
import { NetworkPromotionDialog as Overlay28 } from '../../../packages/woobe-frontend/src/features/network/components/NetworkPromotionDialogV2'
import { NetworkReleaseModal as Overlay29 } from '../../../packages/woobe-frontend/src/features/network/components/NetworkReleaseDialogs'
import { UnsavedAgentSwitchDialog as Overlay30 } from '../../../packages/woobe-frontend/src/features/network/components/NetworkReleaseDialogs'
import { NetworkRemoveDialog as Overlay31 } from '../../../packages/woobe-frontend/src/features/network/components/NetworkRemoveDialog'
import { NetworkRollbackDialog as Overlay32 } from '../../../packages/woobe-frontend/src/features/network/components/NetworkRollbackDialog'
import { NetworkRuntimeControlsPopover as Overlay33 } from '../../../packages/woobe-frontend/src/features/network/components/NetworkRuntimeControlsPopover'
import { NetworkUnsavedChangesDialog as Overlay34 } from '../../../packages/woobe-frontend/src/features/network/components/NetworkUnsavedChangesDialog'
import { NetworkVersionsModal as Overlay35 } from '../../../packages/woobe-frontend/src/features/network/components/NetworkVersionsModalV2'
import { AgentControlsPopover as Overlay36 } from '../../../packages/woobe-frontend/src/features/playground/components/AgentControlsPopover'
import { AgentManagerModal as Overlay37 } from '../../../packages/woobe-frontend/src/features/playground/components/AgentManagerModal'
import { ApiModal as Overlay38 } from '../../../packages/woobe-frontend/src/features/playground/components/ApiModal'
import { ConfirmDeleteModal as Overlay39 } from '../../../packages/woobe-frontend/src/features/playground/components/ConfirmDeleteModal'
import { ConfirmVersionModal as Overlay40 } from '../../../packages/woobe-frontend/src/features/playground/components/ConfirmVersionModal'
import { CreateReleaseDialog as Overlay41 } from '../../../packages/woobe-frontend/src/features/playground/components/CreateReleaseDialog'
import { CreateToolModal as Overlay42 } from '../../../packages/woobe-frontend/src/features/playground/components/CreateToolModal'
import { EditHttpGroupModal as Overlay43 } from '../../../packages/woobe-frontend/src/features/playground/components/EditHttpGroupModal'
import { EditToolModal as Overlay44 } from '../../../packages/woobe-frontend/src/features/playground/components/EditToolModal'
import { ImportToolsModal as Overlay45 } from '../../../packages/woobe-frontend/src/features/playground/components/ImportToolsModal'
import { ManageKnowledgeModal as Overlay46 } from '../../../packages/woobe-frontend/src/features/playground/components/ManageKnowledgeModal'
import { OutputContractHelpModal as Overlay47 } from '../../../packages/woobe-frontend/src/features/playground/components/OutputContractHelpModal'
import { ProductionChangesModal as Overlay48 } from '../../../packages/woobe-frontend/src/features/playground/components/ProductionChangesModal'
import { ReleaseLibraryModal as Overlay49 } from '../../../packages/woobe-frontend/src/features/playground/components/ReleaseLibraryModal'
import { ReleaseSnapshotModal as Overlay50 } from '../../../packages/woobe-frontend/src/features/playground/components/ReleaseSnapshotModal'
import { StageDraftSnapshotModal as Overlay51 } from '../../../packages/woobe-frontend/src/features/playground/components/StageDraftSnapshotModal'
import { ConfigurationKeyDeclarationDialog as Overlay52 } from '../../../packages/woobe-frontend/src/features/projects/components/ConfigurationKeyDeclarationDialog'
import { ConfigurationKeyDeletionDialog } from '../../../packages/woobe-frontend/src/features/projects/components/ConfigurationKeyDeletionDialog'
import { ConfigurationUsageDialog as Overlay53 } from '../../../packages/woobe-frontend/src/features/projects/components/ConfigurationUsageDialog'
import { ProjectSettingsDialog as Overlay54 } from '../../../packages/woobe-frontend/src/features/projects/components/ProjectSettingsDialog'
import { AddProviderCredentialModal as Overlay55 } from '../../../packages/woobe-frontend/src/features/provider-credentials/components/AddProviderCredentialModal'
import { RotateProviderCredentialDialog as Overlay56 } from '../../../packages/woobe-frontend/src/features/provider-credentials/components/RotateProviderCredentialDialog'
import { ModelSettingsModal as Overlay57 } from '../../../packages/woobe-frontend/src/features/provider-models/components/ModelSettingsModal'
import { ProviderModelReconciliationDialog } from '../../../packages/woobe-frontend/src/features/provider-models/components/ProviderModelReconciliationDialog'
import { RuntimeApiReferenceModal as Overlay58 } from '../../../packages/woobe-frontend/src/features/runtime-reference/RuntimeApiReferenceModal'
import { ManageSkillsDialog as Overlay59 } from '../../../packages/woobe-frontend/src/features/skills/ManageSkillsDialog'
import { ToolSettingsModal as Overlay60 } from '../../../packages/woobe-frontend/src/features/tools/components/ToolSettingsModal'
import { WorkspaceSettingsDialog as Overlay61 } from '../../../packages/woobe-frontend/src/features/workspaces/components/WorkspaceSettingsDialog'
import { ToolsCreateDialog as Overlay62 } from '../../../packages/woobe-frontend/src/pages/ToolsCreateDialog'
import type { ComponentType } from 'react'
import { Dialog, Drawer, DangerConfirmDialog, Input } from '@woobe/ui'
import { ConfigurationValueEditor } from '../../../packages/woobe-frontend/src/features/projects/components/ConfigurationValueEditor'
import { AgentContextAssemblerField } from '../../../packages/woobe-frontend/src/features/agents/components/AgentContextAssemblerField'
import { AgentExecutionStrategyField } from '../../../packages/woobe-frontend/src/features/agents/components/AgentExecutionStrategyField'
import { ContractFieldBuilder } from '../../../packages/woobe-frontend/src/features/contracts/ContractFieldBuilder'
import { RuntimeContextPanel } from '../../../packages/woobe-frontend/src/features/contracts/RuntimeContextPanel'
import { NetworkAgentVersions } from '../../../packages/woobe-frontend/src/features/network/components/NetworkAgentVersionsV2'
import { HttpProviderPanel } from '../../../packages/woobe-frontend/src/features/tools/components/HttpProviderPanel'
import { McpProviderPanel } from '../../../packages/woobe-frontend/src/features/tools/components/McpProviderPanel'
import { tool } from '../fixtures/resource-data'
export const overlayCases: { id: string; source: string; component: ComponentType<any>; props?: Record<string, any> }[] = [
  { id:'host-agent-result',source:'packages/woobe-frontend/src/features/playground/components/AgentResultViewer.tsx',component:AgentResultViewer as ComponentType<any>,props:{title:'Agent result',value:'# Support handbook\n\nThe handbook entry is available.\n\n- Verify the account.\n- Review the request.'} },
  { id:'host-config-legacy',source:'packages/woobe-frontend/src/features/projects/components/ConfigurationLegacyPanel.tsx',component:ConfigurationLegacyPanel as ComponentType<any>,props:{canConvert:true} },
  { id:'host-network-history',source:'packages/woobe-frontend/src/pages/NetworkPage.tsx',component:(()=><Dialog open onClose={()=>{}} title="Network history & lifecycle" variant="workspace" height="workspace"><AsacWorkbench projectId="project-a" resourceId="network-support" kind="Network" /></Dialog>) as ComponentType<any> },
  { id:'RagRuntimeSettings',source:'packages/woobe-frontend/src/features/playground/components/RagRuntimeSettings.tsx',component:RagRuntimeSettings as ComponentType<any>,props:{value:undefined} },
  { id:'ConfigurationBatchEditor',source:'packages/woobe-frontend/src/features/projects/components/ConfigurationBatchEditor.tsx',component:ConfigurationBatchEditor as ComponentType<any>,props:{keys:[{id:'batch-demo',key:'SUPPORT_ENDPOINT',kind:'value',value_format:'url',description:'Support API base URL',values:{}}]} },
  { id:'ManageSkills-Create',source:'packages/woobe-frontend/src/features/skills/ManageSkillsDialog.tsx',component:Overlay59 as ComponentType<any>,props:{initialMode:'create',title:'Create Skill'} },
  { id:'ManageSkills-Import',source:'packages/woobe-frontend/src/features/skills/ManageSkillsDialog.tsx',component:Overlay59 as ComponentType<any>,props:{initialMode:'import',title:'Import Skill'} },
  { id:'host-context-manager',source:'packages/woobe-frontend/src/features/agents/components/AgentContextAssemblerField.tsx',component:AgentContextAssemblerField as ComponentType<any> },
  { id:'host-execution-strategy',source:'packages/woobe-frontend/src/features/agents/components/AgentExecutionStrategyField.tsx',component:AgentExecutionStrategyField as ComponentType<any> },
  { id:'host-field-description',source:'packages/woobe-frontend/src/features/contracts/ContractFieldBuilder.tsx',component:ContractFieldBuilder as ComponentType<any>,props:{kind:'external',rows:[{name:'customer_id',type:'string',required:true,expose:true,scope:'run',description:'The customer making this request.'}],onChange:()=>{}} },
  { id:'host-runtime-context',source:'packages/woobe-frontend/src/features/contracts/RuntimeContextPanel.tsx',component:RuntimeContextPanel as ComponentType<any>,props:{contract:{customer_id:{schema:{type:'string'},description:'Customer identifier',required:true,scope:'run',model:{expose:true}}},savedValues:{customer_id:'customer-demo'}} },
  { id:'host-agent-snapshot',source:'packages/woobe-frontend/src/features/network/components/NetworkAgentVersionsV2.tsx',component:NetworkAgentVersions as ComponentType<any>,props:{networkBinding:{source:'release',version:'1.2.0',ref:'selected-release'},onOpenComposition:()=>{}} },
  { id:'host-http-routes',source:'packages/woobe-frontend/src/features/tools/components/HttpProviderPanel.tsx',component:HttpProviderPanel as ComponentType<any>,props:{tool:{...tool,config:{protocol:'http',mode:'group',schema_version:2,base_url:'https://example.test',routes:[{id:'route-demo',name:'Get support entry',description:'Find a support handbook entry.',method:'GET',path:'/support',default_permission:'review'}]}}} },
  { id:'host-mcp-tools',source:'packages/woobe-frontend/src/features/tools/components/McpProviderPanel.tsx',component:McpProviderPanel as ComponentType<any>,props:{allowBindingEdit:true,tool:{...tool,type:'mcp',config:{protocol:'mcp',server:{url:'https://example.test/mcp'},discovered_tools:[{name:'support_lookup',description:'Find a handbook entry.',input_schema:{type:'object',properties:{query:{type:'string'}}}}],readiness:{state:'ready'},permissions:{}}}} },
  { id: 'Dialog', source: 'packages/woobe-ui/src/components/Dialog.tsx', component: Dialog as ComponentType<any>, props: { children: <Input aria-label="Configuration name" defaultValue="PR Reviewer" /> } },
  { id: 'Drawer', source: 'packages/woobe-ui/src/components/Drawer.tsx', component: Drawer as ComponentType<any>, props: { children: <Input aria-label="Configuration name" defaultValue="PR Reviewer" /> } },
  { id: 'DangerConfirmDialog', source: 'packages/woobe-ui/src/components/DangerConfirmDialog.tsx', component: DangerConfirmDialog as ComponentType<any> },
  { id: 'ConfigurationValueEditor', source: 'packages/woobe-frontend/src/features/projects/components/ConfigurationValueEditor.tsx', component: ConfigurationValueEditor as ComponentType<any> },
  { id: 'CreateProjectDialog', source: 'packages/woobe-frontend/src/components/forms/CreateProjectDialog.tsx', component: Overlay0 as ComponentType<any> },
  { id: 'CreateWorkspaceDialog', source: 'packages/woobe-frontend/src/components/forms/CreateWorkspaceDialog.tsx', component: Overlay1 as ComponentType<any> },
  { id: 'AgentBehaviorFieldDialog', source: 'packages/woobe-frontend/src/features/agents/components/AgentBehaviorFieldDialog.tsx', component: Overlay2 as ComponentType<any> },
  { id: 'AgentContextConfigurationDialog', source: 'packages/woobe-frontend/src/features/agents/components/AgentContextConfigurationDialog.tsx', component: Overlay3 as ComponentType<any> },
  { id: 'AgentModelManagerModal', source: 'packages/woobe-frontend/src/features/agents/components/AgentModelManagerModal.tsx', component: Overlay4 as ComponentType<any> },
  { id: 'CreateAgentFlowModal', source: 'packages/woobe-frontend/src/features/agents/components/CreateAgentFlowModal.tsx', component: Overlay5 as ComponentType<any> },
  { id: 'CreateApiKeyDialog', source: 'packages/woobe-frontend/src/features/api-keys/components/CreateApiKeyDialog.tsx', component: Overlay6 as ComponentType<any> },
  { id: 'RotateApiKeyDialog', source: 'packages/woobe-frontend/src/features/api-keys/components/RotateApiKeyDialog.tsx', component: Overlay7 as ComponentType<any> },
  { id: 'AccountSettingsDialog', source: 'packages/woobe-frontend/src/features/auth/components/AccountSettingsDialog.tsx', component: Overlay8 as ComponentType<any> },
  { id: 'ChatSurfaceDetailsModal', source: 'packages/woobe-frontend/src/features/chat-surfaces/components/ChatSurfaceDetailsModal.tsx', component: Overlay9 as ComponentType<any> },
  { id: 'ChatSurfaceLiveTestDialog', source: 'packages/woobe-frontend/src/features/chat-surfaces/components/ChatSurfaceLiveTestDialog.tsx', component: Overlay10 as ComponentType<any> },
  { id: 'ManualModelModal', source: 'packages/woobe-frontend/src/features/first-run/components/ManualModelModal.tsx', component: Overlay11 as ComponentType<any> },
  { id: 'ProviderConnectionModal', source: 'packages/woobe-frontend/src/features/first-run/components/ProviderConnectionModal.tsx', component: Overlay12 as ComponentType<any> },
  { id: 'AttachCollectionModal', source: 'packages/woobe-frontend/src/features/knowledge/components/AttachCollectionModal.tsx', component: Overlay13 as ComponentType<any> },
  { id: 'BuildVectorSnapshotModalV2', source: 'packages/woobe-frontend/src/features/knowledge/components/BuildVectorSnapshotModalV2.tsx', component: Overlay14 as ComponentType<any> },
  { id: 'CollectionDetailsModal', source: 'packages/woobe-frontend/src/features/knowledge/components/CollectionDetailsModal.tsx', component: Overlay15 as ComponentType<any> },
  { id: 'CollectionDetailsModalV2-CollectionDetailsModal', source: 'packages/woobe-frontend/src/features/knowledge/components/CollectionDetailsModalV2.tsx', component: Overlay16 as ComponentType<any> },
  { id: 'CollectionDocumentUploadModal', source: 'packages/woobe-frontend/src/features/knowledge/components/CollectionDocumentUploadModal.tsx', component: Overlay17 as ComponentType<any> },
  { id: 'CreateCollectionModal', source: 'packages/woobe-frontend/src/features/knowledge/components/CreateCollectionModal.tsx', component: Overlay18 as ComponentType<any> },
  { id: 'CreateEmbeddingModelModal', source: 'packages/woobe-frontend/src/features/knowledge/components/CreateEmbeddingModelModal.tsx', component: Overlay19 as ComponentType<any> },
  { id: 'DocumentsDrawer', source: 'packages/woobe-frontend/src/features/knowledge/components/DocumentsDrawer.tsx', component: Overlay20 as ComponentType<any> },
  { id: 'SelectKnowledgeVersionModal', source: 'packages/woobe-frontend/src/features/knowledge/components/SelectKnowledgeVersionModal.tsx', component: Overlay21 as ComponentType<any> },
  { id: 'UploadDocumentModal', source: 'packages/woobe-frontend/src/features/knowledge/components/UploadDocumentModal.tsx', component: Overlay22 as ComponentType<any> },
  { id: 'VectorSnapshotDetailsModal', source: 'packages/woobe-frontend/src/features/knowledge/components/VectorSnapshotDetailsModal.tsx', component: Overlay23 as ComponentType<any> },
  { id: 'NetworkAgentCatalogDrawer', source: 'packages/woobe-frontend/src/features/network/components/NetworkAgentCatalogDrawer.tsx', component: Overlay24 as ComponentType<any> },
  { id: 'NetworkApiModal', source: 'packages/woobe-frontend/src/features/network/components/NetworkApiModal.tsx', component: Overlay25 as ComponentType<any> },
  { id: 'NetworkDraftConflictDialog', source: 'packages/woobe-frontend/src/features/network/components/NetworkDraftConflictDialog.tsx', component: Overlay26 as ComponentType<any> },
  { id: 'NetworkInspectorModal', source: 'packages/woobe-frontend/src/features/network/components/NetworkInspectorModal.tsx', component: Overlay27 as ComponentType<any> },
  { id: 'NetworkPromotionDialogV2-NetworkPromotionDialog', source: 'packages/woobe-frontend/src/features/network/components/NetworkPromotionDialogV2.tsx', component: Overlay28 as ComponentType<any> },
  { id: 'NetworkReleaseDialogs-NetworkReleaseModal', source: 'packages/woobe-frontend/src/features/network/components/NetworkReleaseDialogs.tsx', component: Overlay29 as ComponentType<any> },
  { id: 'NetworkReleaseDialogs-UnsavedAgentSwitchDialog', source: 'packages/woobe-frontend/src/features/network/components/NetworkReleaseDialogs.tsx', component: Overlay30 as ComponentType<any> },
  { id: 'NetworkRemoveDialog', source: 'packages/woobe-frontend/src/features/network/components/NetworkRemoveDialog.tsx', component: Overlay31 as ComponentType<any> },
  { id: 'NetworkRollbackDialog', source: 'packages/woobe-frontend/src/features/network/components/NetworkRollbackDialog.tsx', component: Overlay32 as ComponentType<any> },
  { id: 'NetworkRuntimeControlsPopover', source: 'packages/woobe-frontend/src/features/network/components/NetworkRuntimeControlsPopover.tsx', component: Overlay33 as ComponentType<any> },
  { id: 'NetworkUnsavedChangesDialog', source: 'packages/woobe-frontend/src/features/network/components/NetworkUnsavedChangesDialog.tsx', component: Overlay34 as ComponentType<any> },
  { id: 'NetworkVersionsModalV2-NetworkVersionsModal', source: 'packages/woobe-frontend/src/features/network/components/NetworkVersionsModalV2.tsx', component: Overlay35 as ComponentType<any>, props: { initialSection: 'draft' } },
  { id: 'AgentControlsPopover', source: 'packages/woobe-frontend/src/features/playground/components/AgentControlsPopover.tsx', component: Overlay36 as ComponentType<any> },
  { id: 'AgentManagerModal', source: 'packages/woobe-frontend/src/features/playground/components/AgentManagerModal.tsx', component: Overlay37 as ComponentType<any>, props: { initialSection: 'draft' } },
  { id: 'ApiModal', source: 'packages/woobe-frontend/src/features/playground/components/ApiModal.tsx', component: Overlay38 as ComponentType<any> },
  { id: 'ConfirmDeleteModal', source: 'packages/woobe-frontend/src/features/playground/components/ConfirmDeleteModal.tsx', component: Overlay39 as ComponentType<any> },
  { id: 'ConfirmVersionModal', source: 'packages/woobe-frontend/src/features/playground/components/ConfirmVersionModal.tsx', component: Overlay40 as ComponentType<any> },
  { id: 'CreateReleaseDialog', source: 'packages/woobe-frontend/src/features/playground/components/CreateReleaseDialog.tsx', component: Overlay41 as ComponentType<any> },
  { id: 'CreateToolModal', source: 'packages/woobe-frontend/src/features/playground/components/CreateToolModal.tsx', component: Overlay42 as ComponentType<any> },
  { id: 'EditHttpGroupModal', source: 'packages/woobe-frontend/src/features/playground/components/EditHttpGroupModal.tsx', component: Overlay43 as ComponentType<any> },
  { id: 'EditToolModal', source: 'packages/woobe-frontend/src/features/playground/components/EditToolModal.tsx', component: Overlay44 as ComponentType<any> },
  { id: 'ImportToolsModal', source: 'packages/woobe-frontend/src/features/playground/components/ImportToolsModal.tsx', component: Overlay45 as ComponentType<any> },
  { id: 'ManageKnowledgeModal', source: 'packages/woobe-frontend/src/features/playground/components/ManageKnowledgeModal.tsx', component: Overlay46 as ComponentType<any> },
  { id: 'OutputContractHelpModal', source: 'packages/woobe-frontend/src/features/playground/components/OutputContractHelpModal.tsx', component: Overlay47 as ComponentType<any> },
  { id: 'ProductionChangesModal', source: 'packages/woobe-frontend/src/features/playground/components/ProductionChangesModal.tsx', component: Overlay48 as ComponentType<any> },
  { id: 'ReleaseLibraryModal', source: 'packages/woobe-frontend/src/features/playground/components/ReleaseLibraryModal.tsx', component: Overlay49 as ComponentType<any> },
  { id: 'ReleaseSnapshotModal', source: 'packages/woobe-frontend/src/features/playground/components/ReleaseSnapshotModal.tsx', component: Overlay50 as ComponentType<any> },
  { id: 'StageDraftSnapshotModal', source: 'packages/woobe-frontend/src/features/playground/components/StageDraftSnapshotModal.tsx', component: Overlay51 as ComponentType<any> },
  { id: 'ConfigurationKeyDeclarationDialog', source: 'packages/woobe-frontend/src/features/projects/components/ConfigurationKeyDeclarationDialog.tsx', component: Overlay52 as ComponentType<any>, props: { item: undefined, onConfigure: () => {} } },
  { id: 'ConfigurationKeyDeletionDialog', source: 'packages/woobe-frontend/src/features/projects/components/ConfigurationKeyDeletionDialog.tsx', component: ConfigurationKeyDeletionDialog as ComponentType<any> },
  { id: 'ConfigurationUsageDialog', source: 'packages/woobe-frontend/src/features/projects/components/ConfigurationUsageDialog.tsx', component: Overlay53 as ComponentType<any> },
  { id: 'ProjectSettingsDialog', source: 'packages/woobe-frontend/src/features/projects/components/ProjectSettingsDialog.tsx', component: Overlay54 as ComponentType<any> },
  { id: 'AddProviderCredentialModal', source: 'packages/woobe-frontend/src/features/provider-credentials/components/AddProviderCredentialModal.tsx', component: Overlay55 as ComponentType<any> },
  { id: 'RotateProviderCredentialDialog', source: 'packages/woobe-frontend/src/features/provider-credentials/components/RotateProviderCredentialDialog.tsx', component: Overlay56 as ComponentType<any> },
  { id: 'ModelSettingsModal', source: 'packages/woobe-frontend/src/features/provider-models/components/ModelSettingsModal.tsx', component: Overlay57 as ComponentType<any> },
  { id: 'ProviderModelReconciliationDialog', source: 'packages/woobe-frontend/src/features/provider-models/components/ProviderModelReconciliationDialog.tsx', component: ProviderModelReconciliationDialog as ComponentType<any>, props: { credentialId: 'credential-demo' } },
  { id: 'RuntimeApiReferenceModal', source: 'packages/woobe-frontend/src/features/runtime-reference/RuntimeApiReferenceModal.tsx', component: Overlay58 as ComponentType<any> },
  { id: 'ManageSkillsDialog', source: 'packages/woobe-frontend/src/features/skills/ManageSkillsDialog.tsx', component: Overlay59 as ComponentType<any> },
  { id: 'ToolSettingsModal', source: 'packages/woobe-frontend/src/features/tools/components/ToolSettingsModal.tsx', component: Overlay60 as ComponentType<any> },
  { id: 'WorkspaceSettingsDialog', source: 'packages/woobe-frontend/src/features/workspaces/components/WorkspaceSettingsDialog.tsx', component: Overlay61 as ComponentType<any> },
  { id: 'ToolsCreateDialog', source: 'packages/woobe-frontend/src/pages/ToolsCreateDialog.tsx', component: Overlay62 as ComponentType<any> },
]
