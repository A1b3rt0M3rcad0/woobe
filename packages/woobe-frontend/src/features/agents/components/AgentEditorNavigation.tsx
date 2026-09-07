import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BookOpen, Bot, Cpu, FileJson, Puzzle, Wrench } from 'lucide-react'
import { cn } from '@/lib/utils'

export type AgentEditorSection = 'agent' | 'output' | 'model' | 'knowledge' | 'tools' | 'skills'
const sections = [
  { id: 'agent', label: 'Agent', icon: Bot },
  { id: 'output', label: 'Output', icon: FileJson },
  { id: 'model', label: 'Model', icon: Cpu },
  { id: 'knowledge', label: 'Knowledge', icon: BookOpen },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'skills', label: 'Skills', icon: Puzzle },
] as const

export function useAgentEditorSection() {
  const [params] = useSearchParams()
  const requested = params.get('editor')
  const [section, setSection] = useState<AgentEditorSection>(requested === 'skills' ? 'skills' : 'agent')
  useEffect(() => { if (requested === 'skills') setSection('skills') }, [requested])
  return [section, setSection] as const
}

/** Keep every section visible in both compact Agent editors, without horizontal scrolling. */
export function AgentEditorNavigation({ value, onChange }: { value: AgentEditorSection; onChange: (value: AgentEditorSection) => void }) {
  return <div role="group" aria-label="Agent sections" className="grid shrink-0 grid-cols-3 gap-1 border-b border-border/80 bg-surface/60 p-1.5">
    {sections.map(({ id, label, icon: Icon }) => <button key={id} type="button" aria-pressed={value === id} onClick={() => onChange(id)} className={cn('flex min-w-0 items-center justify-center gap-1.5 rounded-lg border px-2 py-2 text-[11px] font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40', value === id ? 'border-primary/35 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/80 hover:text-white')}><Icon className="h-3 w-3 shrink-0" />{label}</button>)}
  </div>
}
