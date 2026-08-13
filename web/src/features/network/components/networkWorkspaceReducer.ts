import type { NetworkEditorSelection } from '../editor/types'
import type { Environment } from './networkWorkspaceTypes'

export type NetworkCenterMode = 'canvas' | 'chat'
export type NetworkInspectorContext = 'agent' | 'network'

export type NetworkInspectionScope =
  | { type: 'current' }
  | { type: 'run'; runId: string }

export interface NetworkWorkspaceState {
  centerMode: NetworkCenterMode
  environment: Environment
  selection: NetworkEditorSelection
  inspectorContext: NetworkInspectorContext
  inspectionScope: NetworkInspectionScope
}

export type NetworkWorkspaceAction =
  | { type: 'center'; mode: NetworkCenterMode }
  | { type: 'environment'; environment: Environment; selection?: NetworkEditorSelection }
  | { type: 'select'; selection: NetworkEditorSelection; context?: NetworkInspectorContext }
  | { type: 'context'; context: NetworkInspectorContext }
  | { type: 'inspect-run'; runId: string }
  | { type: 'clear-run-inspection' }

export const initialNetworkWorkspaceState: NetworkWorkspaceState = {
  centerMode: 'canvas',
  environment: 'draft',
  selection: { type: 'network' },
  inspectorContext: 'network',
  inspectionScope: { type: 'current' },
}

export function networkWorkspaceReducer(
  state: NetworkWorkspaceState,
  action: NetworkWorkspaceAction,
): NetworkWorkspaceState {
  switch (action.type) {
    case 'center':
      return { ...state, centerMode: action.mode }
    case 'environment':
      return {
        ...state,
        environment: action.environment,
        selection: action.selection ?? state.selection,
        inspectorContext: 'network',
        inspectionScope: { type: 'current' },
      }
    case 'select':
      return {
        ...state,
        selection: action.selection,
        // Selection changes the inspected entity without implicitly changing
        // the active inspector context. Callers can request a context explicitly.
        inspectorContext: action.context ?? state.inspectorContext,
      }
    case 'context':
      return { ...state, inspectorContext: action.context }
    case 'inspect-run':
      return { ...state, inspectionScope: { type: 'run', runId: action.runId } }
    case 'clear-run-inspection':
      return { ...state, inspectionScope: { type: 'current' } }
    default:
      return state
  }
}
