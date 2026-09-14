import { AlertTriangle, Bot, KeyRound, Network } from 'lucide-react'
import {
  Alert,
  AlertDescription,
  AlertTitle,
  CodePanel,
  SectionBlock,
  TechnicalListItem,
} from '@woobe/ui'

import { CopyButton } from '@/components/common/CopyButton'
import type { CreateApiKeyResponse, RuntimeTargetType } from '@/features/api-keys/types'

interface ApiKeySecretRevealProps {
  apiKey: CreateApiKeyResponse
  targetName?: string | null
  agentName?: string | null
}

function permissionLabel(scope: string): string {
  if (scope === 'traces:read') return 'Traces'
  if (scope === 'usage:read') return 'Usage & cost'
  if (scope === 'runtime:execute') return 'Runtime execution'
  return scope
}

function targetType(apiKey: CreateApiKeyResponse): RuntimeTargetType {
  return apiKey.target_type === 'network' ? 'network' : 'agent'
}

export function ApiKeySecretReveal({ apiKey, targetName, agentName }: ApiKeySecretRevealProps) {
  const runtime = apiKey.kind === 'runtime'
  const runtimeTargetType = targetType(apiKey)
  const runtimeTargetLabel = runtimeTargetType === 'network' ? 'Network' : 'Agent'
  const RuntimeTargetIcon = runtimeTargetType === 'network' ? Network : Bot
  const resolvedTargetName = targetName || agentName || apiKey.target_id || apiKey.agent_id || `Unknown ${runtimeTargetLabel.toLowerCase()}`

  return (
    <div className="grid gap-ui-md">
      <Alert variant="warning">
        <div className="flex items-start gap-ui-sm">
          <AlertTriangle className="mt-ui-hairline h-icon w-icon shrink-0" />
          <div>
            <AlertTitle>Copy this secret now</AlertTitle>
            <AlertDescription>It is shown once and cannot be recovered later.</AlertDescription>
          </div>
        </div>
      </Alert>

      <SectionBlock
        title={runtime ? `${runtimeTargetLabel} Runtime Key created` : 'Project Key created'}
        description={apiKey.description || apiKey.name}
        actions={<KeyRound className="h-icon w-icon text-primary-light" />}
      >
        <CodePanel
          title="Secret"
          badge="One-time reveal"
          density="compact"
          actions={<CopyButton text={apiKey.key} />}
        >
          <code className="block break-all bg-background/20 p-ui-md font-mono text-system-control text-accent-foreground">{apiKey.key}</code>
        </CodePanel>
      </SectionBlock>

      <div className="grid gap-ui-xs sm:grid-cols-2">
        {runtime ? (
          <>
            <TechnicalListItem
              label={runtimeTargetLabel}
              description={resolvedTargetName}
              leading={<RuntimeTargetIcon className="h-icon w-icon text-primary-light" />}
            />
            <TechnicalListItem label="Environment" description={apiKey.environment} />
            <TechnicalListItem className="sm:col-span-2" label="Interfaces" description={apiKey.interfaces.join(' · ')} />
          </>
        ) : (
          <TechnicalListItem className="sm:col-span-2" label="Permissions" description={apiKey.scopes.map(permissionLabel).join(' · ')} />
        )}
      </div>

      <CodePanel
        title="Environment setup"
        badge="Shell"
        density="compact"
        actions={<CopyButton text={`export WOOBE_API_KEY="${apiKey.key}"`} />}
      >
        <code className="block break-all bg-background/20 p-ui-md font-mono text-system-control text-muted-foreground">
          export WOOBE_API_KEY=&quot;{apiKey.key}&quot;
        </code>
      </CodePanel>
    </div>
  )
}
