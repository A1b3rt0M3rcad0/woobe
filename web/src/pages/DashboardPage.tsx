import { useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import {
  Activity, AlertCircle, ArrowRight, Bot, Box, Check, CheckCircle2,
  ChevronDown, CircleDollarSign, Clock3, CloudUpload, Code2, Database,
  FileText, KeyRound, Layers3, Network, Play, Rocket, Sparkles,
  TimerReset, Users, Workflow, Wrench, XCircle,
} from 'lucide-react'
import { orgProjectPath } from '@/lib/constants/routes'

type Environment = 'Draft' | 'Staging' | 'Release'

const metrics: Array<{ label: string; value: string; change: string; direction: 'up' | 'down'; icon: LucideIcon; tone: string }> = [
  { label: 'Active Agents', value: '12', change: '2 vs yesterday', direction: 'up', icon: Users, tone: 'bg-blue-500/10 text-blue-400' },
  { label: 'Production Releases', value: '8', change: '1 this week', direction: 'up', icon: Rocket, tone: 'bg-blue-500/10 text-blue-400' },
  { label: 'Runtime Requests (24h)', value: '128,492', change: '18.6% vs yesterday', direction: 'up', icon: Activity, tone: 'bg-blue-500/10 text-blue-400' },
  { label: 'Avg Latency', value: '842 ms', change: '6.3% vs yesterday', direction: 'down', icon: Clock3, tone: 'bg-blue-500/10 text-blue-400' },
  { label: 'Success Rate', value: '99.42%', change: '0.21% vs yesterday', direction: 'up', icon: CheckCircle2, tone: 'bg-emerald-500/10 text-emerald-400' },
  { label: 'Estimated Cost (24h)', value: '$184.27', change: '12.4% vs yesterday', direction: 'up', icon: CircleDollarSign, tone: 'bg-blue-500/10 text-blue-400' },
]

const days = ['Jun 2', 'Jun 3', 'Jun 4', 'Jun 5', 'Jun 6', 'Jun 7', 'Jun 8']
const requestValues = [94, 124, 103, 134, 140, 165, 177]
const latencyValues = [1100, 1050, 920, 1280, 1060, 1380, 1580]
const tokenValues = [14, 15, 18, 24, 30, 22, 32]

const releases = [
  { agent: 'Support Agent', environment: 'Release' as Environment, version: 'v1.8.0', promoted: '2h ago' },
  { agent: 'Docs Agent', environment: 'Staging' as Environment, version: 'v2.1.0', promoted: '18m ago' },
  { agent: 'Sales Copilot', environment: 'Draft' as Environment, version: 'v0.9.0', promoted: '6m ago' },
]

const traces = [
  { time: 'Jun 8, 23:06:21', agent: 'Support Agent', environment: 'Release' as Environment, status: 'Success', latency: '612 ms', tokens: '8,432', cost: '$0.0121' },
  { time: 'Jun 8, 23:05:44', agent: 'Docs Agent', environment: 'Staging' as Environment, status: 'Success', latency: '1,142 ms', tokens: '12,189', cost: '$0.0187' },
  { time: 'Jun 8, 23:05:10', agent: 'Sales Copilot', environment: 'Release' as Environment, status: 'Success', latency: '523 ms', tokens: '6,021', cost: '$0.0083' },
  { time: 'Jun 8, 23:04:32', agent: 'Support Agent', environment: 'Release' as Environment, status: 'Warning', latency: '1,876 ms', tokens: '15,332', cost: '$0.0214' },
  { time: 'Jun 8, 23:03:58', agent: 'Docs Agent', environment: 'Draft' as Environment, status: 'Error', latency: '3,412 ms', tokens: '9,884', cost: '$0.0139' },
]

function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-slate-800/90 bg-[#081321] shadow-[0_14px_35px_rgba(0,0,0,.18)] ${className}`}>{children}</section>
}

function PanelHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 px-4 pb-2 pt-3.5">
      <div>
        <div className="flex items-center gap-1.5"><h2 className="text-[13px] font-semibold text-slate-100">{title}</h2><AlertCircle className="h-3 w-3 text-slate-500" /></div>
        {subtitle && <p className="mt-0.5 text-[10px] text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

function RangeButton({ label = 'Last 7 days' }: { label?: string }) {
  return <button className="flex items-center gap-1 rounded-md border border-slate-800 bg-slate-950/30 px-2 py-1 text-[10px] text-slate-300 hover:border-slate-700 hover:text-white">{label}<ChevronDown className="h-3 w-3" /></button>
}

function MiniLink({ label, onClick }: { label: string; onClick?: () => void }) {
  return <button onClick={onClick} className="flex items-center gap-1 text-[10px] font-medium text-blue-400 hover:text-blue-300">{label}<ArrowRight className="h-3 w-3" /></button>
}

function MetricCard({ metric }: { metric: (typeof metrics)[number] }) {
  const Icon = metric.icon
  return (
    <Panel className="min-h-[98px] p-3.5">
      <div className="flex items-start gap-3">
        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ${metric.tone}`}><Icon className="h-4 w-4" /></div>
        <div className="min-w-0">
          <p className="truncate text-[11px] font-medium text-slate-300">{metric.label}</p>
          <p className="mt-1 text-[22px] font-semibold leading-none tracking-tight text-white">{metric.value}</p>
          <p className="mt-2 flex items-center gap-1 text-[10px] text-emerald-400"><span>{metric.direction === 'down' ? '↓' : '↑'}</span>{metric.change}</p>
        </div>
      </div>
    </Panel>
  )
}

function buildPath(values: number[], width: number, height: number, padding = 12) {
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  return values.map((value, index) => {
    const x = padding + (index / (values.length - 1)) * (width - padding * 2)
    const y = height - padding - ((value - min) / range) * (height - padding * 2)
    return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
  }).join(' ')
}

function RuntimeChart() {
  const width = 420
  const height = 118
  const path = buildPath(requestValues, width, height, 13)
  const area = `${path} L ${width - 13} ${height - 13} L 13 ${height - 13} Z`
  return (
    <Panel className="h-full">
      <PanelHeader title="Runtime Requests" subtitle="7-day trend" action={<RangeButton />} />
      <div className="px-3 pb-3"><div className="relative h-[140px]">
        <div className="absolute bottom-6 left-7 right-0 top-2 flex flex-col justify-between">{[0, 1, 2, 3].map((line) => <div key={line} className="border-t border-slate-800/80" />)}</div>
        <div className="absolute bottom-7 left-0 top-1 flex w-7 flex-col justify-between text-[9px] text-slate-500"><span>200K</span><span>150K</span><span>100K</span><span>50K</span></div>
        <svg className="absolute left-7 right-0 top-0 h-[118px]" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-label="Runtime requests trend">
          <defs><linearGradient id="request-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3b82f6" stopOpacity=".24" /><stop offset="100%" stopColor="#3b82f6" stopOpacity="0" /></linearGradient></defs>
          <path d={area} fill="url(#request-area)" /><path d={path} fill="none" stroke="#3b82f6" strokeWidth="2.1" vectorEffect="non-scaling-stroke" />
          {requestValues.map((value, index) => {
            const x = 13 + (index / (requestValues.length - 1)) * (width - 26)
            const min = Math.min(...requestValues); const max = Math.max(...requestValues)
            const y = height - 13 - ((value - min) / (max - min)) * (height - 26)
            return <circle key={`${value}-${index}`} cx={x} cy={y} r="3" fill="#60a5fa" stroke="#dbeafe" strokeWidth="1" />
          })}
        </svg>
        <div className="absolute bottom-0 left-7 right-0 flex justify-between text-[9px] text-slate-500">{days.map((day) => <span key={day}>{day}</span>)}</div>
      </div></div>
    </Panel>
  )
}

function LatencyChart() {
  const width = 420
  const height = 104
  const path = buildPath(latencyValues, width, height, 12)
  const maxTokens = Math.max(...tokenValues)
  return (
    <Panel className="h-full">
      <PanelHeader title="Latency & Token Usage" subtitle="7-day trend" action={<RangeButton />} />
      <div className="px-3 pb-3">
        <div className="mb-1.5 flex items-center gap-4 pl-8 text-[9px] text-slate-400"><span className="flex items-center gap-1.5"><span className="h-0.5 w-3 rounded bg-blue-500" />Latency (ms)</span><span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-violet-500/80" />Tokens (M)</span></div>
        <div className="relative h-[126px]">
          <div className="absolute bottom-6 left-7 right-7 top-1 flex flex-col justify-between">{[0, 1, 2, 3].map((line) => <div key={line} className="border-t border-slate-800/80" />)}</div>
          <div className="absolute bottom-7 left-0 top-0 flex w-7 flex-col justify-between text-[9px] text-slate-500"><span>2K</span><span>1.5K</span><span>1K</span><span>500</span></div>
          <div className="absolute bottom-7 right-0 top-0 flex w-7 flex-col items-end justify-between text-[9px] text-slate-500"><span>40M</span><span>30M</span><span>20M</span><span>10M</span></div>
          <svg className="absolute left-7 right-7 top-0 h-[104px]" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-label="Latency and token usage">
            {tokenValues.map((value, index) => { const slot = width / tokenValues.length; const barHeight = (value / maxTokens) * 74; return <rect key={`${value}-${index}`} x={index * slot + slot * .37} y={height - 11 - barHeight} width={slot * .26} height={barHeight} rx="1" fill="#8b5cf6" fillOpacity=".72" stroke="#a78bfa" strokeOpacity=".8" /> })}
            <path d={path} fill="none" stroke="#3b82f6" strokeWidth="2.1" vectorEffect="non-scaling-stroke" />
            {latencyValues.map((value, index) => { const x = 12 + (index / (latencyValues.length - 1)) * (width - 24); const min = Math.min(...latencyValues); const max = Math.max(...latencyValues); const y = height - 12 - ((value - min) / (max - min)) * (height - 24); return <circle key={`${value}-${index}`} cx={x} cy={y} r="3" fill="#60a5fa" stroke="#dbeafe" strokeWidth="1" /> })}
          </svg>
          <div className="absolute bottom-0 left-7 right-7 flex justify-between text-[9px] text-slate-500">{days.map((day) => <span key={day}>{day}</span>)}</div>
        </div>
      </div>
    </Panel>
  )
}

function EnvironmentDistribution() {
  return (
    <Panel className="h-full"><PanelHeader title="Environment Distribution" action={<RangeButton label="Current" />} />
      <div className="grid min-h-[168px] grid-cols-[150px_1fr] items-center gap-4 px-5 pb-4">
        <div className="relative mx-auto h-32 w-32 rounded-full" style={{ background: 'conic-gradient(#22c55e 0 50%, #fbbf24 50% 83%, #3b82f6 83% 100%)' }}><div className="absolute inset-[18px] flex flex-col items-center justify-center rounded-full bg-[#081321] shadow-[inset_0_0_0_1px_rgba(51,65,85,.6)]"><span className="text-2xl font-semibold text-white">12</span><span className="text-[10px] text-slate-500">Agents</span></div></div>
        <div className="space-y-4">{[['Release', '50% (6)', 'bg-emerald-500'], ['Staging', '33% (4)', 'bg-amber-400'], ['Draft', '17% (2)', 'bg-blue-500']].map(([label, value, color]) => <div key={label} className="flex items-center justify-between gap-5 text-[11px]"><span className="flex items-center gap-2 text-slate-200"><span className={`h-2 w-2 rounded-full ${color}`} />{label}</span><span className="font-medium text-slate-300">{value}</span></div>)}</div>
      </div>
    </Panel>
  )
}

function EnvironmentBadge({ value }: { value: Environment }) {
  const classes: Record<Environment, string> = { Release: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400', Staging: 'border-amber-500/40 bg-amber-500/10 text-amber-400', Draft: 'border-blue-500/40 bg-blue-500/10 text-blue-400' }
  return <span className={`inline-flex rounded border px-1.5 py-0.5 text-[9px] font-medium ${classes[value]}`}>{value}</span>
}

function StatusBadge({ value }: { value: string }) {
  const classes: Record<string, string> = { Success: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400', Warning: 'border-orange-500/40 bg-orange-500/10 text-orange-400', Error: 'border-red-500/40 bg-red-500/10 text-red-400' }
  return <span className={`inline-flex rounded border px-1.5 py-0.5 text-[9px] font-medium ${classes[value]}`}>{value}</span>
}

function AgentReleases({ onOpen }: { onOpen: () => void }) {
  return (
    <Panel className="h-full"><PanelHeader title="Agent Releases" /><div className="px-3 pb-3">
      <div className="grid grid-cols-[1.55fr_1fr_.8fr_1fr_20px] border-b border-slate-800 px-1 pb-1.5 text-[9px] text-slate-500"><span>Agent</span><span>Environment</span><span>Release</span><span>Last Promoted</span><span /></div>
      {releases.map((release, index) => <div key={release.agent} className={`grid grid-cols-[1.55fr_1fr_.8fr_1fr_20px] items-center px-1 py-2 text-[10px] ${index !== releases.length - 1 ? 'border-b border-slate-800/80' : ''}`}><span className="flex min-w-0 items-center gap-2 font-medium text-slate-200"><span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-blue-500/15 text-blue-400"><Bot className="h-3 w-3" /></span><span className="truncate">{release.agent}</span></span><span><EnvironmentBadge value={release.environment} /></span><span className="text-slate-300">{release.version}</span><span className="text-slate-400">{release.promoted}</span><button className="text-slate-500 hover:text-white">•••</button></div>)}
      <div className="pt-2"><MiniLink label="View all releases" onClick={onOpen} /></div>
    </div></Panel>
  )
}

function KnowledgeBase({ onOpen }: { onOpen: () => void }) {
  const entries = [{ label: 'Collections', value: '14', icon: Layers3, tone: 'text-blue-400' }, { label: 'Documents', value: '3,281', icon: FileText, tone: 'text-blue-400' }, { label: 'Storage', value: '10.4 GB', icon: Database, tone: 'text-blue-400' }, { label: 'Embedding Jobs', value: '7 running', icon: Sparkles, tone: 'text-emerald-400' }]
  return <Panel className="h-full"><PanelHeader title="Knowledge Base" /><div className="grid grid-cols-2 gap-2 px-3 pb-3">{entries.map((entry) => { const Icon = entry.icon; return <div key={entry.label} className="flex items-center gap-2.5 rounded-lg border border-slate-800 bg-slate-950/20 p-2.5"><div className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-800/60"><Icon className={`h-4 w-4 ${entry.tone}`} /></div><div><p className="text-[9px] text-slate-500">{entry.label}</p><p className={`text-[17px] font-semibold leading-tight ${entry.tone === 'text-emerald-400' ? entry.tone : 'text-white'}`}>{entry.value}</p></div></div> })}<div className="col-span-2 pt-0.5"><MiniLink label="Open Knowledge" onClick={onOpen} /></div></div></Panel>
}

function ToolsIntegrations({ onOpen }: { onOpen: () => void }) {
  const items = [{ label: 'HTTP Tools', value: '26', icon: Wrench, tone: 'text-blue-400' }, { label: 'Provider Credentials', value: '9', icon: KeyRound, tone: 'text-violet-400' }, { label: 'MCP Connections', value: '5', icon: Network, tone: 'text-slate-300' }, { label: 'External APIs Healthy', value: '21 / 23', icon: CheckCircle2, tone: 'text-emerald-400' }]
  return <Panel className="h-full"><PanelHeader title="Tools & Integrations" /><div className="px-3 pb-3">{items.map((item, index) => { const Icon = item.icon; return <div key={item.label} className={`flex items-center justify-between py-2 text-[10px] ${index !== items.length - 1 ? 'border-b border-slate-800/80' : ''}`}><span className="flex items-center gap-2 text-slate-200"><Icon className={`h-3.5 w-3.5 ${item.tone}`} />{item.label}</span><span className={`font-semibold ${item.tone}`}>{item.value}</span></div> })}<div className="pt-2"><MiniLink label="Manage Integrations" onClick={onOpen} /></div></div></Panel>
}

function RecentTraces({ onOpen }: { onOpen: () => void }) {
  return <Panel className="h-full overflow-hidden"><PanelHeader title="Recent Traces" /><div className="overflow-x-auto px-3 pb-3 scrollbar-thin"><div className="min-w-[640px]"><div className="grid grid-cols-[1.2fr_1.25fr_1.05fr_.95fr_.85fr_.75fr_.75fr_18px] border-b border-slate-800 pb-1.5 text-[9px] text-slate-500"><span>Time</span><span>Agent</span><span>Environment</span><span>Status</span><span>Latency</span><span>Tokens</span><span>Cost</span><span /></div>{traces.map((trace, index) => <div key={trace.time} className={`grid grid-cols-[1.2fr_1.25fr_1.05fr_.95fr_.85fr_.75fr_.75fr_18px] items-center py-1.5 text-[9px] ${index !== traces.length - 1 ? 'border-b border-slate-800/70' : ''}`}><span className="text-slate-400">{trace.time}</span><span className="font-medium text-slate-200">{trace.agent}</span><span><EnvironmentBadge value={trace.environment} /></span><span><StatusBadge value={trace.status} /></span><span className="text-slate-300">{trace.latency}</span><span className="text-slate-300">{trace.tokens}</span><span className="text-slate-300">{trace.cost}</span><button className="text-slate-500 hover:text-white">•••</button></div>)}<div className="pt-2"><MiniLink label="View all traces" onClick={onOpen} /></div></div></div></Panel>
}

function SessionsJobs() {
  const rows = [{ label: 'Active Sessions', value: '84', icon: Users, tone: 'text-slate-300' }, { label: 'Queued Jobs', value: '23', icon: TimerReset, tone: 'text-blue-400' }, { label: 'Running Jobs', value: '17', icon: Play, tone: 'text-blue-400' }, { label: 'Failed Jobs (24h)', value: '3', icon: XCircle, tone: 'text-red-400' }]
  return <Panel className="h-full"><PanelHeader title="Sessions & Jobs" action={<RangeButton label="Current" />} /><div className="px-3 pb-3">{rows.map((row, index) => { const Icon = row.icon; return <div key={row.label} className={`flex items-center justify-between py-2.5 text-[10px] ${index !== rows.length - 1 ? 'border-b border-slate-800/80' : ''}`}><span className="flex items-center gap-2 text-slate-300"><span className="flex h-6 w-6 items-center justify-center rounded-lg bg-slate-800/60"><Icon className={`h-3.5 w-3.5 ${row.tone}`} /></span>{row.label}</span><span className={`text-sm font-semibold ${row.value === '3' ? 'text-red-400' : 'text-white'}`}>{row.value}</span></div> })}</div></Panel>
}

function IngestionPipeline() {
  const steps = [{ label: 'Upload', icon: CloudUpload }, { label: 'S3', icon: Check }, { label: 'Outbox', icon: Check }, { label: 'Queue', icon: Check }, { label: 'Inbox', icon: Check }, { label: 'Chunking', icon: Check }, { label: 'Embeddings', icon: Check }, { label: 'pgvector', icon: Box }]
  const stats = [['Docs Processed (24h)', '1,283'], ['Chunks Created (24h)', '24,912'], ['Embeddings (24h)', '24.9M'], ['Pipeline Latency (p95)', '28.4 s']]
  return <Panel className="h-full"><div className="flex items-center justify-between px-4 pb-2 pt-3.5"><h2 className="text-[13px] font-semibold text-slate-100">Ingestion Pipeline</h2><span className="flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[9px] font-medium text-emerald-400"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Live</span></div><div className="px-4 pb-3"><div className="relative flex justify-between py-2"><div className="absolute left-4 right-4 top-[21px] h-px bg-emerald-500/50" />{steps.map((step) => { const Icon = step.icon; return <div key={step.label} className="relative z-10 flex min-w-0 flex-col items-center gap-1.5"><span className="flex h-7 w-7 items-center justify-center rounded-full border border-emerald-500/20 bg-[#0c2b26] text-emerald-400"><Icon className="h-3.5 w-3.5" /></span><span className="max-w-[60px] truncate text-[8px] text-slate-300">{step.label}</span></div> })}</div><div className="mt-2 grid grid-cols-4 divide-x divide-slate-800 rounded-lg border border-slate-800 bg-slate-950/20">{stats.map(([label, value]) => <div key={label} className="p-2.5"><p className="text-[8px] text-slate-500">{label}</p><p className="mt-1 text-[14px] font-semibold text-white">{value}</p></div>)}</div><div className="pt-2"><MiniLink label="View pipeline" /></div></div></Panel>
}

function RecentActivity() {
  const items = [{ title: 'agent.created', description: 'Sales Copilot was created', time: '6m ago', icon: Bot, tone: 'bg-violet-500/10 text-violet-400' }, { title: 'release.promoted', description: 'Support Agent v1.8.0 promoted to Release', time: '18m ago', icon: Rocket, tone: 'bg-blue-500/10 text-blue-400' }, { title: 'knowledge.ingestion.started', description: 'document-2024-06-08.pdf ingestion started', time: '21m ago', icon: FileText, tone: 'bg-emerald-500/10 text-emerald-400' }, { title: 'trace.completed', description: 'Trace completed for Docs Agent', time: '23m ago', icon: Activity, tone: 'bg-emerald-500/10 text-emerald-400' }, { title: 'provider_credential.updated', description: 'OpenAI credential updated', time: '32m ago', icon: KeyRound, tone: 'bg-orange-500/10 text-orange-400' }]
  return <Panel><div className="px-4 pb-2 pt-3.5"><h2 className="text-[13px] font-semibold text-slate-100">Recent Activity</h2></div><div className="grid grid-cols-1 divide-y divide-slate-800 px-3 pb-3 sm:grid-cols-2 sm:divide-x sm:divide-y-0 xl:grid-cols-5">{items.map((item) => { const Icon = item.icon; return <div key={item.title} className="flex min-w-0 gap-2.5 px-3 py-2 first:pl-1 last:pr-1"><span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${item.tone}`}><Icon className="h-3.5 w-3.5" /></span><div className="min-w-0"><p className="truncate text-[10px] font-semibold text-slate-200">{item.title}</p><p className="mt-1 text-[9px] leading-4 text-slate-500">{item.description}</p><div className="mt-1 flex items-center gap-2 text-[8px] text-slate-600"><span>{item.time}</span><button className="rounded bg-slate-800/80 px-1.5 py-0.5 text-slate-400 hover:text-white">View</button></div></div></div> })}</div><div className="flex justify-end border-t border-slate-800 px-4 py-2"><MiniLink label="View all activity" /></div></Panel>
}

function TechTag({ icon: Icon, label, className }: { icon: LucideIcon; label: string; className: string }) {
  return <span className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[10px] font-medium ${className}`}><Icon className="h-3.5 w-3.5" />{label}</span>
}

export default function DashboardPage() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const navigate = useNavigate()
  const [environment, setEnvironment] = useState<Environment>('Release')

  const goTo = (segment: string) => {
    if (!projectId) return
    navigate(orgProjectPath(organizationId, projectId, segment))
  }

  return (
    <div className="h-full overflow-y-auto pr-1 scrollbar-thin">
      <div className="mx-auto min-w-0 max-w-[1720px] space-y-2.5 pb-6">
        <header className="flex flex-col gap-3 border-b border-slate-800/70 pb-3 xl:flex-row xl:items-start xl:justify-between">
          <div><h1 className="text-[22px] font-semibold tracking-tight text-white">Project Overview</h1><p className="mt-0.5 text-[11px] text-slate-500">API-first runtime for production AI agents</p></div>
          <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
            <div className="flex flex-wrap items-center gap-1.5"><TechTag icon={Sparkles} label="OpenAI-compatible" className="border-emerald-500/30 bg-emerald-500/5 text-emerald-400" /><TechTag icon={Code2} label="ChatOpenAI / LangChain" className="border-blue-500/30 bg-blue-500/5 text-blue-400" /><TechTag icon={Workflow} label="HTTP Tools" className="border-violet-500/30 bg-violet-500/5 text-violet-400" /><TechTag icon={FileText} label="Knowledge / RAG" className="border-violet-500/30 bg-violet-500/5 text-violet-400" /></div>
            <div className="flex overflow-hidden rounded-lg border border-slate-800 bg-slate-950/30 p-0.5">{(['Draft', 'Staging', 'Release'] as const).map((item) => <button key={item} onClick={() => setEnvironment(item)} className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[10px] font-medium transition ${environment === item ? item === 'Release' ? 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/35' : item === 'Staging' ? 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/35' : 'bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/35' : 'text-slate-500 hover:text-slate-300'}`}><span className={`h-1.5 w-1.5 rounded-full ${item === 'Release' ? 'bg-emerald-400' : item === 'Staging' ? 'bg-amber-400' : 'bg-blue-400'}`} />{item}</button>)}</div>
          </div>
        </header>

        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">{metrics.map((metric) => <MetricCard key={metric.label} metric={metric} />)}</div>
        <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-12"><div className="xl:col-span-4"><RuntimeChart /></div><div className="xl:col-span-4"><LatencyChart /></div><div className="xl:col-span-4"><EnvironmentDistribution /></div></div>
        <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-12"><div className="xl:col-span-4"><AgentReleases onOpen={() => goTo('agents')} /></div><div className="xl:col-span-4"><KnowledgeBase onOpen={() => goTo('knowledge')} /></div><div className="xl:col-span-4"><ToolsIntegrations onOpen={() => goTo('tools')} /></div></div>
        <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-12"><div className="xl:col-span-5"><RecentTraces onOpen={() => goTo('traces')} /></div><div className="xl:col-span-2"><SessionsJobs /></div><div className="xl:col-span-5"><IngestionPipeline /></div></div>
        <RecentActivity />
      </div>
    </div>
  )
}
