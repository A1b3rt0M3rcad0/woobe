import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Key, Plus } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { CreateApiKeyDialog } from '@/features/api-keys/components/CreateApiKeyDialog'
import { useApiKeys } from '@/features/api-keys/hooks'
import type { RuntimeEnvironment } from '@/features/api-keys/types'

interface ApiReferenceRuntimeKeySectionProps {
  projectId: string
  agentId: string
  agentName: string
  environment: RuntimeEnvironment
  manageKeysPath: string
  selectedKeyId: string | null
  onSelectedKeyId: (keyId: string | null) => void
}

export function ApiReferenceRuntimeKeySection({
  projectId,
  agentId,
  agentName,
  environment,
  manageKeysPath,
  selectedKeyId,
  onSelectedKeyId,
}: ApiReferenceRuntimeKeySectionProps) {
  const { data: apiKeys = [] } = useApiKeys(projectId)
  const [showCreate, setShowCreate] = useState(false)

  const compatibleKeys = useMemo(
    () => apiKeys.filter((key) => (
      key.kind === 'runtime'
      && key.agent_id === agentId
      && key.environment === environment
      && key.status === 'active'
    )),
    [apiKeys, agentId, environment],
  )

  useEffect(() => {
    if (selectedKeyId && compatibleKeys.some((key) => key.id === selectedKeyId)) return
    onSelectedKeyId(compatibleKeys[0]?.id ?? null)
  }, [compatibleKeys, selectedKeyId, onSelectedKeyId])

  const selectedKey = compatibleKeys.find((key) => key.id === selectedKeyId) ?? null
  const manageKeyPath = `${manageKeysPath}?type=runtime&agent=${encodeURIComponent(agentId)}&environment=${environment}${selectedKey ? `&credential=${encodeURIComponent(selectedKey.credential_id)}` : ''}`

  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Runtime Key</p>
        <button type="button" onClick={() => setShowCreate(true)} className="inline-flex items-center gap-1 text-[11px] font-medium text-primary-light hover:text-white">
          <Plus className="h-3.5 w-3.5" /> Create
        </button>
      </div>

      {compatibleKeys.length > 0 ? (
        <div className="mt-2 space-y-2">
          <select
            value={selectedKeyId ?? ''}
            onChange={(event) => onSelectedKeyId(event.target.value || null)}
            className="h-10 w-full rounded-lg border border-border/80 bg-background/70 px-3 text-xs text-white outline-none transition-colors focus:border-primary/40"
          >
            {compatibleKeys.map((key) => (
              <option key={key.id} value={key.id}>{key.name}</option>
            ))}
          </select>
          {selectedKey && (
            <div className="rounded-lg border border-border/80 bg-background/45 p-2.5">
              <div className="flex items-center gap-2">
                <Key className="h-3.5 w-3.5 text-primary-light" />
                <code className="min-w-0 flex-1 truncate text-[11px] text-white">{selectedKey.key_prefix}...</code>
              </div>
              <p className="mt-1 truncate text-[10px] text-muted">{selectedKey.interfaces.join(' · ')}</p>
            </div>
          )}
        </div>
      ) : (
        <div className="mt-2 rounded-xl border border-dashed border-border/80 bg-background/35 p-3">
          <p className="text-xs font-medium text-white">No Runtime Key for this environment</p>
          <p className="mt-1 text-[11px] leading-4 text-muted">Create a key bound to {agentName} and {environment}.</p>
          <Button className="mt-3 w-full" size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="mr-2 h-3.5 w-3.5" /> Create Runtime Key
          </Button>
        </div>
      )}

      <Link to={manageKeyPath} className="mt-2 inline-flex text-[11px] text-muted hover:text-white">
        Manage this Agent&apos;s keys
      </Link>

      <CreateApiKeyDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        projectId={projectId}
        initialKind="runtime"
        lockedAgentId={agentId}
        initialEnvironment={environment}
        layer="nestedModal"
        onCreated={(key) => onSelectedKeyId(key.id)}
      />
    </div>
  )
}
