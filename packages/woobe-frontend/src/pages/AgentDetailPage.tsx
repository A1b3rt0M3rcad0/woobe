import { Link, useNavigate, useParams } from 'react-router-dom'
import { ExternalLink, Key, Pencil, Play } from 'lucide-react'
import { CodePanel, SectionBlock } from '@woobe/ui'
import { useAgent } from '@/features/agents/hooks'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { Tabs } from '@/components/ui/Tabs'
import { Button } from '@/components/ui/Button'
import { AgentBehaviorDetails } from '@/features/agents/components/AgentBehaviorDetails'
import { StatusBadge } from '@/components/common/StatusBadge'
import { CopyButton } from '@/components/common/CopyButton'
import { workspaceProjectPath } from '@/lib/constants/routes'

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="flex items-center justify-between gap-4 border-b border-border py-2 last:border-b-0"><span className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted">{label}</span><span className="min-w-0 text-right font-sans text-xs text-slate-200">{value}</span></div>
}

export default function AgentDetailPage() {
  const { workspaceId, projectId, agentId } = useParams<{ workspaceId?: string; projectId: string; agentId: string }>()
  const navigate = useNavigate()
  const { data: agent, isLoading, isError, error, refetch } = useAgent(agentId)
  const p = (projId: string, ...segments: string[]) => workspaceProjectPath(workspaceId, projId, ...segments)

  const tabs = [
    { id: 'general', label: 'General', content: agent ? <SectionBlock title="Agent Details" density="compact"><DetailRow label="Name" value={agent.name} /><DetailRow label="Description" value={agent.description || '—'} /><DetailRow label="Status" value={<StatusBadge status={agent.status} />} /><DetailRow label="Session mode" value={agent.session_mode || 'stateful'} /></SectionBlock> : null },
    { id: 'behavior', label: 'Behavior', content: agent ? <AgentBehaviorDetails behavior={agent.behavior_spec} legacyPrompt={agent.system_prompt} /> : null },
    { id: 'model', label: 'Model', content: agent ? <SectionBlock title="Model Configuration" density="compact"><DetailRow label="Provider" value={<code className="font-mono text-[10px]">{agent.provider}</code>} /><DetailRow label="Model" value={<code className="font-mono text-[10px]">{agent.model}</code>} /><DetailRow label="Temperature" value={agent.temperature ?? '—'} /><DetailRow label="Max output tokens" value={agent.max_output_tokens ?? '—'} /></SectionBlock> : null },
    { id: 'api', label: 'API', content: agent ? <div className="space-y-3"><SectionBlock title="Runtime endpoint" density="compact"><DetailRow label="Agent ID" value={<span className="inline-flex items-center gap-1.5"><code className="font-mono text-[10px]">{agent.id}</code><CopyButton text={agent.id} iconOnly /></span>} /><DetailRow label="Endpoint" value={<span className="inline-flex items-center gap-1.5"><code className="font-mono text-[10px]">POST /runtime/ask</code><CopyButton text="POST /runtime/ask" iconOnly /></span>} /></SectionBlock><CodePanel title="cURL example" density="compact" actions={<CopyButton text={`curl -X POST http://localhost:8000/runtime/ask -H "Authorization: Bearer <API_KEY>" -H "Content-Type: application/json" -d '{"session_id": "<session_id>", "content": "Hello, agent!"}'`} iconOnly />}><pre className="overflow-x-auto p-3 font-mono text-[10px] leading-5 text-slate-300">{`curl -X POST http://localhost:8000/runtime/ask \\
  -H "Authorization: Bearer <API_KEY>" \\
  -H "Content-Type: application/json" \\
  -d '{\n  "session_id": "<session_id>",\n  "content": "Hello, agent!"\n}'`}</pre></CodePanel><Link to={p(projectId!, 'api-keys')} className="inline-flex items-center gap-1.5 font-mono text-[10px] text-primary-light hover:underline"><Key className="h-3.5 w-3.5" />Manage API Keys</Link></div> : null },
  ]

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />
  if (!agent) return <ErrorState message="Agent not found" />

  return <div><PageHeader title={agent.name} description={`${agent.provider} / ${agent.model}`} eyebrow="Build / Agent" actions={<div className="flex items-center gap-1.5"><Button variant="outline" size="sm" onClick={() => navigate(p(projectId!, 'agents', agentId!, 'edit'))}><Pencil className="mr-1 h-3.5 w-3.5" />Edit</Button><Button size="sm" onClick={() => navigate(p(projectId!, 'agents', agentId!, 'playground'))}><Play className="mr-1 h-3.5 w-3.5" />Open Playground</Button><Button variant="outline" size="sm" onClick={() => navigate(p(projectId!, 'agents'))}><ExternalLink className="mr-1 h-3.5 w-3.5" />Agents</Button></div>} /><Tabs tabs={tabs} /></div>
}
