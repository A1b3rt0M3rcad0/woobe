import { useMemo, useState } from 'react'
import { FileStack } from 'lucide-react'
import { Alert, AlertDescription, Checkbox, Input, PanelHeader } from '@woobe/ui'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { useArtifactProcessingCapabilities } from '@/features/artifacts/hooks'
import type { ArtifactEnvironment } from '@/features/artifacts/types'

const actions = ['read', 'search', 'write', 'delete', 'process', 'transfer'] as const
type ArtifactAction = typeof actions[number]

function object(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function externalFields(value: unknown): Record<string, unknown> | null {
  let raw = value
  if (typeof raw === 'string') {
    try { raw = JSON.parse(raw) } catch { return null }
  }
  if (raw == null) return {}
  const fields = object(raw)
  if (Object.keys(fields).some(key => ['fields', 'additionalProperties'].includes(key)) && fields.fields) return object(fields.fields)
  return fields
}

function contractWithFields(contractValue: unknown, fields: Record<string, unknown>) {
  let root = contractValue
  if (typeof root === 'string') {
    try { root = JSON.parse(root) } catch { return null }
  }
  const wrapper = object(root)
  return wrapper.fields && typeof wrapper.fields === 'object' && !Array.isArray(wrapper.fields)
    ? { ...wrapper, fields }
    : fields
}

function defaultCapability(enabled = false) {
  return {
    schema_version: 1,
    enabled,
    workspace_binding: enabled ? { field: 'artifact_workspace', namespace: 'default', scope: 'session' } : null,
    actions: enabled ? ['read', 'search'] : ['read', 'search'],
    limits: { max_search_results: 20, max_read_chars: 8192, max_total_read_chars: 65536, max_context_units: 8000, max_writes: 0 },
    processing_profile: null,
  }
}

export function availableBindingField(contractValue: unknown, base = 'artifact_workspace') {
  const fields = externalFields(contractValue) ?? {}
  if (!Object.prototype.hasOwnProperty.call(fields, base)) return base
  let suffix = 2
  while (Object.prototype.hasOwnProperty.call(fields, `${base}_${suffix}`)) suffix++
  return `${base}_${suffix}`
}

export function synchronizeBindingContract(
  contractValue: unknown,
  previousField: string | null,
  fieldName: string,
  scope: 'run' | 'session',
) {
  const fields = externalFields(contractValue)
  if (fields == null) return null
  const next = { ...fields }
  if (Object.prototype.hasOwnProperty.call(next, fieldName) && previousField !== fieldName) return null
  if (previousField && previousField !== fieldName) delete next[previousField]
  next[fieldName] = {
    schema: { type: 'string', minLength: 1, maxLength: 128 },
    required: true,
    scope,
    model: { expose: false },
    description: 'Opaque Artifact Workspace selector. It is resolved and authorized by the Woobe server.',
  }
  return contractWithFields(contractValue, next)
}

export function AgentArtifactSettings({ projectId }: { projectId: string }) {
  const { state, setField } = useAgentEditor()
  const [bindingError, setBindingError] = useState<string | null>(null)
  const runtime = state.runtimeConfig
  const rawCapability = object(runtime.artifacts)
  const enabled = rawCapability.enabled === true
  const capability = { ...defaultCapability(enabled), ...rawCapability }
  const binding = object(capability.workspace_binding)
  const limits = { ...defaultCapability().limits, ...object(capability.limits) }
  const selectedActions = Array.isArray(capability.actions) ? capability.actions.filter((item): item is ArtifactAction => actions.includes(item as ArtifactAction)) : ['read', 'search']
  const processingProfile = object(capability.processing_profile)
  const scope = binding.scope === 'run' ? 'run' : 'session'
  const bindingField = typeof binding.field === 'string' ? binding.field : 'artifact_workspace'
  const bindingNamespace = typeof binding.namespace === 'string' ? binding.namespace : 'default'
  const environment = 'draft' as ArtifactEnvironment
  const readiness = useArtifactProcessingCapabilities(projectId, environment, enabled && selectedActions.includes('process'))
  const fieldError = useMemo(() => externalFields(state.externalContextContract) == null
    ? 'The External Context contract contains invalid JSON; fix it before configuring the Workspace binding.'
    : bindingError, [bindingError, state.externalContextContract])

  function writeCapability(next: Record<string, unknown>, nextContract?: Record<string, unknown> | null) {
    setField('runtimeConfig', { ...runtime, artifacts: next })
    if (nextContract) setField('externalContextContract', nextContract as never)
  }

  function toggleEnabled(nextEnabled: boolean) {
    const next: Record<string, unknown> = nextEnabled ? defaultCapability(true) : defaultCapability(false)
    if (nextEnabled) {
      const nextBinding = object(next.workspace_binding)
      next.workspace_binding = { ...nextBinding, field: availableBindingField(state.externalContextContract) }
    }
    const nextBinding = object(next.workspace_binding)
    const synced = nextEnabled
      ? synchronizeBindingContract(state.externalContextContract, null, String(nextBinding.field), 'session')
      : null
    if (nextEnabled && synced == null) {
      setBindingError('Choose a different External Context field; the selected name already belongs to another field.')
      return
    }
    setBindingError(null)
    writeCapability(next, synced)
  }

  function updateBinding(field: string, namespace: string, nextScope: 'run' | 'session') {
    const normalizedField = field.trim() || 'artifact_workspace'
    const synced = synchronizeBindingContract(state.externalContextContract, bindingField, normalizedField, nextScope)
    if (synced == null) {
      setBindingError('Choose a different External Context field; the selected name already belongs to another field.')
      return
    }
    setBindingError(null)
    writeCapability({
      ...capability,
      workspace_binding: { field: normalizedField, namespace: namespace.trim() || 'default', scope: nextScope },
    }, synced)
  }

  function toggleAction(action: ArtifactAction, checked: boolean) {
    const nextActions = checked ? [...new Set([...selectedActions, action])] : selectedActions.filter(item => item !== action)
    const nextLimits = { ...limits, max_writes: nextActions.includes('write') ? Math.max(1, Number(limits.max_writes) || 0) : 0 }
    writeCapability({ ...capability, actions: nextActions, limits: nextLimits, processing_profile: nextActions.includes('process') ? capability.processing_profile ?? null : null })
  }

  function updateLimit(name: keyof typeof limits, raw: string) {
    const value = Number(raw)
    const bounds = {
      max_search_results: [1, 200], max_read_chars: [1, 65_536],
      max_total_read_chars: [1, 1_048_576], max_context_units: [64, 1_000_000], max_writes: [0, 100],
    } as const
    const [minimum, maximum] = bounds[name]
    if (!Number.isInteger(value) || value < minimum || value > maximum) return
    const nextLimits = { ...limits, [name]: value }
    if (name === 'max_writes') {
      if (value > 0 && !selectedActions.includes('write')) nextLimits.max_writes = 0
    }
    writeCapability({ ...capability, limits: nextLimits })
  }

  return (
    <div className="min-w-0 max-w-full p-ui-sm 2xl:p-ui-md">
      <section className="min-w-0 max-w-full rounded-container border border-border bg-surface/[0.72]">
        <PanelHeader
          icon={<FileStack className="h-icon w-icon" />}
          title="Artifact Workspaces"
          description="Configure a typed Workspace binding, permitted operations and bounded context. Grants remain owned by Project and Workspace authority."
          actions={<label className="flex items-center gap-ui-sm font-sans text-system-label text-muted-foreground">{enabled ? 'Enabled' : 'Disabled'}<Checkbox checked={enabled} onChange={event => toggleEnabled(event.target.checked)} /></label>}
        />
        <div className="grid min-w-0 gap-ui-md p-ui-sm 2xl:p-ui-md">
          {!enabled ? <p className="text-product-small text-muted-foreground">Artifacts are disabled. Enabling them creates a required, non-model-exposed External Context selector; it does not grant access or add credentials.</p> : <>
            {fieldError && <Alert variant="destructive"><AlertDescription>{fieldError}</AlertDescription></Alert>}
            <div className="grid min-w-0 gap-ui-sm rounded-technical border border-border p-ui-md sm:grid-cols-2">
              <label className="grid min-w-0 gap-ui-xs text-product-small font-medium">External Context field
                <Input value={bindingField} maxLength={128} onChange={event => updateBinding(event.target.value, bindingNamespace, scope)} aria-label="Artifact binding field" />
              </label>
              <label className="grid min-w-0 gap-ui-xs text-product-small font-medium">Namespace
                <Input value={bindingNamespace} maxLength={255} onChange={event => updateBinding(bindingField, event.target.value, scope)} aria-label="Artifact namespace" />
              </label>
              <label className="grid gap-ui-xs text-product-small font-medium">Binding lifecycle
                <select value={scope} onChange={event => updateBinding(bindingField, bindingNamespace, event.target.value as 'run' | 'session')} className="h-control rounded-control border border-input bg-background px-ui-sm text-product-small">
                  <option value="session">Session · fixed when the Session opens</option><option value="run">Run · may vary per execution</option>
                </select>
              </label>
              <p className="self-end text-product-small text-muted-foreground">The technical field name identifies an opaque Workspace selector. It is never exposed to the model.</p>
            </div>

            <fieldset className="grid min-w-0 gap-ui-sm rounded-technical border border-border p-ui-md">
              <legend className="px-ui-xs text-product-small font-medium">Allowed actions</legend>
              <div className="grid gap-ui-sm sm:grid-cols-2 lg:grid-cols-3">
                {actions.map(action => <label key={action} className="flex min-w-0 items-center gap-ui-sm rounded-control border border-border/70 p-ui-sm text-product-small"><Checkbox checked={selectedActions.includes(action)} onChange={event => toggleAction(action, event.target.checked)} />{action}</label>)}
              </div>
            </fieldset>

            <fieldset className="grid min-w-0 gap-ui-sm rounded-technical border border-border p-ui-md">
              <legend className="px-ui-xs text-product-small font-medium">Read and write budgets</legend>
              <div className="grid min-w-0 gap-ui-sm sm:grid-cols-2 lg:grid-cols-3">
                {([
                  ['max_search_results', 'Search results', 1, 200], ['max_read_chars', 'Characters per read', 1, 65536],
                  ['max_total_read_chars', 'Total read characters', 1, 1048576], ['max_context_units', 'Context units', 64, 1000000],
                  ['max_writes', 'Writes per Run', 0, 100],
                ] as const).map(([key, label, minimum, maximum]) => <label key={key} className="grid min-w-0 gap-ui-xs text-product-small font-medium">{label}
                  <Input type="number" min={minimum} max={maximum} step={1} value={String(limits[key])} disabled={key === 'max_writes' && !selectedActions.includes('write')} onChange={event => updateLimit(key, event.target.value)} />
                </label>)}
              </div>
            </fieldset>

            {selectedActions.includes('process') && <section className="grid min-w-0 gap-ui-sm rounded-technical border border-border p-ui-md">
              <h3 className="font-medium">Processing profile</h3>
              <p className="text-product-small text-muted-foreground">Pin a portable profile reference and revision, or leave the default unset. Provider credentials are resolved by the server Environment and never enter this form.</p>
              <div className="grid gap-ui-sm sm:grid-cols-[minmax(0,1fr)_8rem]">
                <label className="grid min-w-0 gap-ui-xs text-product-small font-medium">Profile reference<Input value={String(processingProfile.ref ?? '')} maxLength={64} onChange={event => writeCapability({ ...capability, processing_profile: event.target.value ? { ref: event.target.value, revision: Number(processingProfile.revision ?? 1) } : null })} /></label>
                <label className="grid gap-ui-xs text-product-small font-medium">Revision<Input type="number" min={1} step={1} value={String(processingProfile.revision ?? 1)} onChange={event => writeCapability({ ...capability, processing_profile: { ref: String(processingProfile.ref ?? ''), revision: Number(event.target.value) || 1 } })} /></label>
              </div>
              {readiness.isPending ? <p role="status" className="text-product-small">Checking installed processing capabilities…</p> : readiness.isError ? <p role="status" className="text-product-small text-warning">Capability availability could not be confirmed. The server validates profile readiness at use time.</p> : <ul className="grid gap-ui-xs text-product-small">{readiness.data.components.map(component => <li key={`${component.role}:${component.name}`} className="flex flex-wrap justify-between gap-ui-sm"><span>{component.role}: {component.name}</span><span className={component.ready ? 'text-success' : 'text-muted-foreground'}>{component.ready ? 'Available' : 'Unavailable'}</span></li>)}</ul>}
            </section>}

            <Alert><AlertDescription>Saving this capability does not create grants. Project and Workspace permissions are checked by the server for every read, write, processing request and transfer. A Session-scoped binding is immutable after Session creation; changing it requires a new Session.</AlertDescription></Alert>
          </>}
        </div>
      </section>
    </div>
  )
}
