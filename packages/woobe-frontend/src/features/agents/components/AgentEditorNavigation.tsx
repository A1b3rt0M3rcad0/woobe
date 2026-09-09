import { useEffect, useRef, useState } from 'react'
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
  standalone = false,
}: {
  value: AgentEditorSection
  onChange: (value: AgentEditorSection) => void
  standalone?: boolean
}) {
  const activeGroup = groupForAgentEditorSection(value)
  const lastVisited = useRef<Partial<Record<AgentEditorGroupId, AgentEditorSection>>>({})

  useEffect(() => {
    lastVisited.current[activeGroup.id] = value
  }, [activeGroup.id, value])

  return (
    <nav aria-label="Agent configuration" className="shrink-0 border-b border-border/80 bg-surface/45">
      <div
        role="group"
        aria-label="Agent configuration groups"
        className={cn('grid grid-cols-4', standalone ? 'px-2 py-1.5' : 'px-2 pt-1.5')}
      >
        {agentEditorGroups.map(group => {
          const Icon = group.icon
          const active = activeGroup.id === group.id
          const target = standalone ? lastVisited.current[group.id] ?? group.sections[0].id : group.sections[0].id
          return (
            <button
              key={group.id}
              type="button"
              aria-pressed={active}
              onClick={() => onChange(target)}
              className={cn(
                'relative flex min-w-0 items-center justify-center border-b-2 border-transparent font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60',
                standalone ? 'h-9 gap-0.5 px-1 text-[11px]' : 'gap-1.5 px-1.5 py-2 text-[10px]',
                active ? 'border-primary text-white' : 'text-muted hover:text-white',
              )}
            >
              {!standalone ? <Icon className={cn('h-3.5 w-3.5 shrink-0', active ? 'text-primary-light' : 'text-muted')} /> : null}
              <span className="truncate">{group.label}</span>
            </button>
          )
        })}
      </div>

      {!standalone && activeGroup.sections.length > 1 ? (
        <div role="group" aria-label="Agent configuration sections" className="flex items-center gap-1 px-3 py-2">
          {activeGroup.sections.map(section => (
            <button
              key={section.id}
              type="button"
              aria-pressed={value === section.id}
              onClick={() => onChange(section.id)}
              className={cn(
                'rounded-md px-2.5 py-1.5 text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60',
                value === section.id ? 'bg-primary/10 text-primary-light' : 'text-muted hover:bg-background/45 hover:text-white',
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
