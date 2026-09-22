import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Bot, FileJson, Puzzle, ServerCog } from 'lucide-react'
import { SegmentedControl } from '@woobe/ui'

export type AgentEditorSection = 'details' | 'behavior' | 'runtime' | 'model' | 'output' | 'external-context' | 'knowledge' | 'tools' | 'skills'
export type AgentEditorGroupId = 'agent' | 'execution' | 'capabilities' | 'contracts'

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
    id: 'contracts',
    label: 'Contracts',
    icon: FileJson,
    sections: [
      { id: 'output', label: 'Output' },
      { id: 'external-context', label: 'External Context' },
    ],
  },
]

function resolveSection(value: string | null): AgentEditorSection {
  if (value === 'agent' || value === 'overview') return 'details'
  if (value === 'contracts') return 'output'
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
      <div className="border-b border-border/60 p-ui-hairline">
        <SegmentedControl
          ariaLabel="Agent configuration groups"
          stretch
          value={activeGroup.id}
          onValueChange={(groupId) => {
            const group = agentEditorGroups.find((item) => item.id === groupId)
            if (group) onChange(group.sections[0].id)
          }}
          items={agentEditorGroups.map((group) => {
            const Icon = group.icon
            return { value: group.id, label: group.label, icon: <Icon className="h-icon-sm w-icon-sm" /> }
          })}
          className="w-full border-0 bg-transparent p-0"
        />
      </div>

      {activeGroup.sections.length > 1 ? (
        <div className="px-ui-md py-ui-sm">
          <SegmentedControl
            ariaLabel="Agent configuration sections"
            size="compact"
            value={value}
            onValueChange={(section) => onChange(section as AgentEditorSection)}
            items={activeGroup.sections.map((section) => ({ value: section.id, label: section.label }))}
          />
        </div>
      ) : null}
    </nav>
  )
}
