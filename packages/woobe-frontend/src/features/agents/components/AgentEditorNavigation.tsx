import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Bot, FileJson, Puzzle, ServerCog } from 'lucide-react'
import { cn } from '@/lib/utils'

export type AgentEditorSection = 'details' | 'behavior' | 'runtime' | 'model' | 'output' | 'knowledge' | 'tools' | 'skills'
export type AgentEditorGroupId = 'agent' | 'execution' | 'capabilities' | 'output'

interface AgentEditorGroup {
  id: AgentEditorGroupId
  label: string
  icon: typeof Bot
  sections: ReadonlyArray<{ id: AgentEditorSection; label: string }>
}

export const agentEditorGroups: ReadonlyArray<AgentEditorGroup> = [
  {
    id: 'agent',
    label: 'Agent',
    icon: Bot,
    sections: [
      { id: 'details', label: 'Overview' },
      { id: 'behavior', label: 'Behavior' },
    ],
  },
  {
    id: 'execution',
    label: 'Execution',
    icon: ServerCog,
    sections: [
      { id: 'runtime', label: 'Runtime' },
      { id: 'model', label: 'Model' },
    ],
  },
  {
    id: 'capabilities',
    label: 'Capabilities',
    icon: Puzzle,
    sections: [
      { id: 'knowledge', label: 'Knowledge' },
      { id: 'tools', label: 'Tools' },
      { id: 'skills', label: 'Skills' },
    ],
  },
  {
    id: 'output',
    label: 'Output',
    icon: FileJson,
    sections: [{ id: 'output', label: 'Contract' }],
  },
]

function resolveSection(value: string | null): AgentEditorSection {
  if (value === 'agent' || value === 'overview') return 'details'
  for (const group of agentEditorGroups) {
    const section = group.sections.find(item => item.id === value)
    if (section) return section.id
  }
  return 'details'
}

export function groupForAgentEditorSection(section: AgentEditorSection) {
  return agentEditorGroups.find(group => group.sections.some(item => item.id === section)) ?? agentEditorGroups[0]
}

export function useAgentEditorSection() {
  const [params, setParams] = useSearchParams()
  const requested = params.get('editor')
  const [section, setLocalSection] = useState<AgentEditorSection>(() => resolveSection(requested))

  useEffect(() => { setLocalSection(resolveSection(requested)) }, [requested])

  const setSection = (next: AgentEditorSection) => {
    setLocalSection(next)
    const nextParams = new URLSearchParams(params)
    nextParams.set('editor', next)
    setParams(nextParams, { replace: true })
  }

  return [section, setSection] as const
}

export function AgentEditorNavigation({
  value,
  onChange,
}: {
  value: AgentEditorSection
  onChange: (value: AgentEditorSection) => void
}) {
  const activeGroup = groupForAgentEditorSection(value)

  return (
    <nav aria-label="Agent configuration" className="shrink-0 border-b border-border bg-surface/55">
      <div role="group" aria-label="Agent configuration groups" className="grid grid-cols-4 gap-[3px] border-b border-border/60 p-[3px]">
        {agentEditorGroups.map(group => {
          const Icon = group.icon
          const active = activeGroup.id === group.id
          return (
            <button
              key={group.id}
              type="button"
              aria-pressed={active}
              onClick={() => onChange(group.sections[0].id)}
              className={cn(
                'flex h-[30px] min-w-0 items-center justify-center gap-1 rounded-technical border px-1.5 font-mono text-[8px] transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40',
                active
                  ? 'border-primary/35 bg-primary/[0.10] text-slate-50'
                  : 'border-transparent text-muted-foreground hover:bg-control/45 hover:text-slate-50',
              )}
            >
              <Icon className={cn('h-3 w-3 shrink-0', active ? 'text-primary-light' : 'text-muted-foreground')} />
              <span className="truncate">{group.label}</span>
            </button>
          )
        })}
      </div>

      {activeGroup.sections.length > 1 ? (
        <div role="group" aria-label="Agent configuration sections" className="flex items-center gap-1 px-3 py-2">
          {activeGroup.sections.map(section => (
            <button
              key={section.id}
              type="button"
              aria-pressed={value === section.id}
              onClick={() => onChange(section.id)}
              className={cn(
                'flex h-[27px] items-center rounded-technical border px-2.5 font-mono text-[8px] transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40',
                value === section.id
                  ? 'border-primary/35 bg-primary/[0.10] text-primary-light'
                  : 'border-transparent text-muted-foreground hover:border-border hover:bg-control/45 hover:text-slate-50',
              )}
            >
              {section.label}
            </button>
          ))}
        </div>
      ) : null}
    </nav>
  )
}
