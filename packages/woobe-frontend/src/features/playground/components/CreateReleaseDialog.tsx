import { useState, useMemo, useEffect } from 'react'
import { useReleases, useCreateRelease, usePrompts, useContracts, useModelConfigs, useKnowledgeVersions } from '@/features/agents/hooks'
import { Dialog } from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Select } from '@/components/ui/Select'
import { toast } from 'sonner'
import type { AgentPrompt, AgentContract, AgentModelConfig, KnowledgeVersion } from '@/features/agents/types'

interface CreateReleaseDialogProps {
  open: boolean
  onClose: () => void
  agentId: string
  projectId: string
}

function getNextVersion(releases: { version: string }[] | undefined): string {
  if (!releases || releases.length === 0) return 'v1.0.0'
  const sorted = [...releases].map(r => r.version).sort()
  const latest = sorted[sorted.length - 1]
  const match = latest.match(/^v(\d+)\.(\d+)\.(\d+)$/)
  if (!match) return 'v1.0.0'
  return `v${match[1]}.${Number(match[2]) + 1}.0`
}

function getLatestNonArchived<T extends { id: string; status: string; created_at?: string }>(items: T[] | undefined): T | undefined {
  if (!items || items.length === 0) return undefined
  return [...items]
    .filter(i => i.status !== 'archived')
    .sort((a, b) => {
      const aTime = a.created_at ? new Date(a.created_at).getTime() : 0
      const bTime = b.created_at ? new Date(b.created_at).getTime() : 0
      return bTime - aTime
    })[0]
}

export function CreateReleaseDialog({ open, onClose, agentId, projectId }: CreateReleaseDialogProps) {
  const { data: releases } = useReleases(agentId)
  const { data: prompts } = usePrompts(agentId)
  const { data: contracts } = useContracts(agentId)
  const { data: modelConfigs } = useModelConfigs(agentId)
  const { data: knowledgeVersions } = useKnowledgeVersions(agentId)
  const createRelease = useCreateRelease(agentId)

  const [version, setVersion] = useState('')
  const [releaseNotes, setReleaseNotes] = useState('')
  const [promptVersionId, setPromptVersionId] = useState('')
  const [contractVersionId, setContractVersionId] = useState('')
  const [modelConfigVersionId, setModelConfigVersionId] = useState('')
  const [knowledgeVersionId, setKnowledgeVersionId] = useState('')

  useEffect(() => {
    if (open) {
      setVersion(getNextVersion(releases))
      setReleaseNotes('')
      setPromptVersionId('')
      setContractVersionId('')
      setModelConfigVersionId('')
      setKnowledgeVersionId('')
    }
  }, [open])

  const latestPrompt = useMemo(() => getLatestNonArchived(prompts), [prompts])
  const latestContract = useMemo(() => getLatestNonArchived(contracts), [contracts])
  const latestModelConfig = useMemo(() => getLatestNonArchived(modelConfigs), [modelConfigs])
  const latestKV = useMemo(() => getLatestNonArchived(knowledgeVersions), [knowledgeVersions])

  useEffect(() => { if (latestPrompt && !promptVersionId) setPromptVersionId(latestPrompt.id) }, [latestPrompt])
  useEffect(() => { if (latestContract && !contractVersionId) setContractVersionId(latestContract.id) }, [latestContract])
  useEffect(() => { if (latestModelConfig && !modelConfigVersionId) setModelConfigVersionId(latestModelConfig.id) }, [latestModelConfig])
  useEffect(() => { if (latestKV && !knowledgeVersionId) setKnowledgeVersionId(latestKV.id) }, [latestKV])

  const promptOptions = useMemo(() =>
    (prompts ?? []).map(p => ({ value: p.id, label: `${p.version} (${p.status})` })),
    [prompts],
  )
  const contractOptions = useMemo(() =>
    (contracts ?? []).map(c => ({ value: c.id, label: `${c.version} (${c.status})` })),
    [contracts],
  )
  const modelConfigOptions = useMemo(() =>
    (modelConfigs ?? []).map(mc => ({ value: mc.id, label: `${mc.version} (${mc.status})` })),
    [modelConfigs],
  )
  const knowledgeOptions = useMemo(() =>
    (knowledgeVersions ?? []).map(kv => ({ value: kv.id, label: `${kv.version} (${kv.status})` })),
    [knowledgeVersions],
  )

  const handleSubmit = async () => {
    try {
      await createRelease.mutateAsync({
        project_id: projectId,
        agent_id: agentId,
        version,
        prompt_version_id: promptVersionId || undefined,
        contract_version_id: contractVersionId || undefined,
        model_config_version_id: modelConfigVersionId || undefined,
        knowledge_version_id: knowledgeVersionId || undefined,
        release_notes: releaseNotes || undefined,
      })
      toast.success(`Release ${version} created`)
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create release')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Create Release">
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-muted mb-1">Version</label>
          <Input value={version} onChange={(e) => setVersion(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs font-medium text-muted mb-1">Release Notes</label>
          <Textarea
            value={releaseNotes}
            onChange={(e) => setReleaseNotes(e.target.value)}
            className="min-h-[80px]"
            placeholder="Describe what changed in this release..."
          />
        </div>
        <div className="rounded-lg border border-border p-3 space-y-3">
          <p className="text-xs font-semibold text-muted uppercase tracking-wider">Version Composition</p>
          <div>
            <label className="block text-xs font-medium text-muted mb-1">
              Prompt: {latestPrompt ? `${latestPrompt.version} (${latestPrompt.status})` : '—'}
            </label>
            <Select value={promptVersionId} onChange={(e) => setPromptVersionId(e.target.value)} options={promptOptions} placeholder="Select prompt version" />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted mb-1">
              Contract: {latestContract ? `${latestContract.version} (${latestContract.status})` : '—'}
            </label>
            <Select value={contractVersionId} onChange={(e) => setContractVersionId(e.target.value)} options={contractOptions} placeholder="Select contract version" />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted mb-1">
              Model Config: {latestModelConfig ? `${latestModelConfig.version} (${latestModelConfig.status})` : '—'}
            </label>
            <Select value={modelConfigVersionId} onChange={(e) => setModelConfigVersionId(e.target.value)} options={modelConfigOptions} placeholder="Select model config version" />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted mb-1">
              Knowledge: {latestKV ? `${latestKV.version} (${latestKV.status})` : '—'}
            </label>
            <Select value={knowledgeVersionId} onChange={(e) => setKnowledgeVersionId(e.target.value)} options={knowledgeOptions} placeholder="Select knowledge version" />
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" onClick={handleSubmit} loading={createRelease.isPending}>Create Release</Button>
        </div>
      </div>
    </Dialog>
  )
}
