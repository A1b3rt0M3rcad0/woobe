import { useParams } from 'react-router-dom'
import { Alert, AlertDescription, AlertTitle, Button, buttonClassName } from '@woobe/ui'
import { ApiError } from '@/lib/api/errors'
import { workspaceProjectPath } from '@/lib/constants/routes'
import { configurationReturnPath } from '@/features/projects/configuration'
import type { ProjectEnvironment } from '@/features/projects/types'

const configurationIssues: Record<string, { title: string; description: string; action: string }> = {
  CONFIG_USAGE_NOT_AUTHORIZED: {
    title: 'authorization required', action: 'authorization',
    description: 'Open the key’s consumers in Environments and approve this provider connection and its destination for this environment. Retry the catalog after approval.',
  },
  CONFIG_DESTINATION_CHANGED: {
    title: 'destination approval required', action: 'authorization',
    description: 'Review this connection’s destination in the key’s consumers before approving its use. Retry the catalog after approval.',
  },
  CONFIG_VALUE_MISSING: {
    title: 'configuration value required', action: 'configuration',
    description: 'Set the referenced key’s value in this environment, then retry the catalog. Values from another environment are not used.',
  },
  CONFIG_REFERENCE_NOT_FOUND: { title: 'configuration reference unavailable', action: 'configuration', description: 'Review the declared key and this provider connection’s reference in Environments.' },
  CONFIG_KIND_MISMATCH: { title: 'configuration key incompatible', action: 'configuration', description: 'This provider connection requires a secret key. Review its configuration reference.' },
  CONFIG_VALUE_INVALID: { title: 'configuration value invalid', action: 'configuration', description: 'Replace the referenced value with one that satisfies its declared format, then retry.' },
  CONFIG_VALUE_REVOKED: { title: 'configuration value revoked', action: 'configuration', description: 'Review the referenced value and its approval, then retry the catalog.' },
  CONFIG_VERSION_UNAVAILABLE: { title: 'configuration version unavailable', action: 'configuration', description: 'Refresh the key’s configuration and retry the catalog.' },
  CONFIG_STORE_UNAVAILABLE: { title: 'configuration status unavailable', action: 'configuration', description: 'Configuration could not be checked. Retry when the configuration service is available.' },
  CONFIG_REVISION_CONFLICT: { title: 'configuration changed', action: 'configuration', description: 'Review the current key and its approvals, then retry the catalog.' },
  CONFIG_BINDING_INVALID: { title: 'configuration reference invalid', action: 'configuration', description: 'Review this provider connection’s authentication reference.' },
  LEGACY_ENVIRONMENT_REQUIRED: { title: 'legacy configuration requires review', action: 'configuration', description: 'Review the legacy mapping and select its environment in Environments before retrying.' },
}

export function discoveryConfigurationIssue(error: unknown, environment: ProjectEnvironment = 'draft') {
  if (!(error instanceof ApiError) || !error.data || typeof error.data !== 'object') return null
  const data = error.data as { configuration_schema_version?: unknown; diagnostics?: unknown }
  if (data.configuration_schema_version !== 'project_configuration.v1' || !Array.isArray(data.diagnostics)) return null
  for (const diagnostic of data.diagnostics) {
    if (!diagnostic || typeof diagnostic !== 'object') continue
    const { code, key, environment: reportedEnvironment } = diagnostic
    if (typeof code !== 'string' || !Object.prototype.hasOwnProperty.call(configurationIssues, code)) continue
    if (reportedEnvironment != null && reportedEnvironment !== environment) continue
    return { ...configurationIssues[code], key: typeof key === 'string' && /^[A-Za-z_][A-Za-z0-9_]{0,127}$/.test(key) ? key : null }
  }
  return null
}

export function ProviderDiscoveryErrorNotice({ projectId, error, onRetry, onManual, environment = 'draft' }: {
  projectId: string; error: unknown; onRetry: () => void; onManual?: () => void; environment?: ProjectEnvironment
}) {
  const { workspaceId } = useParams()
  const issue = discoveryConfigurationIssue(error, environment)
  const label = environment[0].toUpperCase() + environment.slice(1)
  const params = new URLSearchParams({ environment })
  if (issue?.key) params.set('key', issue.key)
  const returnTo = configurationReturnPath(window.location.pathname + window.location.search, projectId, window.location.origin)
  if (returnTo) params.set('returnTo', returnTo)
  const href = workspaceProjectPath(workspaceId, projectId, 'environments') + '?' + params
  return <Alert variant="warning">
    <AlertTitle>{issue ? `${label} ${issue.title}` : 'Provider catalog unavailable'}</AlertTitle>
    <AlertDescription>
      {issue?.key && <code className="mb-ui-xs block break-all">{issue.key}</code>}
      {issue ? issue.description : onManual
        ? 'Retry discovery or enter the model ID manually. Entering an ID does not change connection permissions.'
        : 'Retry discovery or review the provider connection.'}
    </AlertDescription>
    <div className="mt-ui-md flex flex-wrap gap-ui-sm">
      {issue && <a href={href} className={buttonClassName({ variant: 'outline', size: 'sm' })}>Review {label} {issue.action}</a>}
      <Button type="button" size="sm" variant="outline" onClick={onRetry}>Retry</Button>
      {!issue && onManual && <Button type="button" size="sm" variant="ghost" onClick={onManual}>Enter model ID manually</Button>}
    </div>
  </Alert>
}
