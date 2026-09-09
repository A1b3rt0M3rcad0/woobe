import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Bot, FileJson, Puzzle, ServerCog } from 'lucide-react'
import { cn } from '@/lib/utils'

export type AgentEditorSection = 'details' | 'behavior' | 'runtime' | 'model' | 'output' | 'knowledge' | 'tools' | 'skills'
type AgentEditorGroupId = 'agent' | 'execution' | 'capabilities' | 'output'

interface AgentEditorGroup {
  id: AgentEditorGroupId
  label: string
  icon: typeof Bot
  sections: ReadonlyArray<{ id: AgentEditorSection; label: string }>
}

const groups: ReadonlyArray<AgentEditorGroup> = [
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
  for (const group of groups) {
    const section = group.sections.find(item => item.id === value)
    if (section) return section.id
  }
  return 'details'
}

function groupForSection(section: AgentEditorSection) {
  return groups.find(group => group.sections.some(item => item.id === section)) ?? groups[0]
}

export function useAgentEditorSection() {
  const [params] = useSearchParams()
  const requested = params.get('editor')
  const [section, setSection] = useState<AgentEditorSection>(() => resolveSection(requested))
  useEffect(() => { setSection(resolveSection(requested)) }, [requested])
  return [section, setSection] as const
}

export function AgentEditorNavigation({ value, onChange }: { value: AgentEditorSection; onChange: (value: AgentEditorSection) => void }) {
  const activeGroup = groupForSection(value)

  return (
    <nav aria-label="Agent configuration" className="shrink-0 border-b border-border/80 bg-surface/45">
      <div role="group" aria-label="Agent configuration groups" className="grid grid-cols-4 px-2 pt-1.5">
        {groups.map(group => {
          const Icon = group.icon
          const active = activeGroup.id === group.id
          return (
            <button
              key={group.id}
              type="button"
              aria-pressed={active}
              onClick={() => onChange(group.sections[0].id)}
              className={cn(
                'relative flex min-w-0 items-center justify-center gap-1.5 border-b-2 border-transparent px-1.5 py-2 text-[10px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60',
                active ? 'border-primary text-white' : 'text-muted hover:text-white',
              )}
            >
              <Icon className={cn('h-3.5 w-3.5 shrink-0', active ? 'text-primary-light' : 'text-muted')} />
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
