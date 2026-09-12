import { useEffect, useRef, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Textarea } from '@/components/ui/Textarea'
import { behaviorFields } from '../behavior'

type Field = (typeof behaviorFields)[number]
type Value = string | string[]

interface Props {
  field: Field
  value: Value
  agentName: string
  onApply: (value: Value) => void
  onClose: () => void
}

export function AgentBehaviorFieldDialog({ field, value, agentName, onApply, onClose }: Props) {
  const [initialValue] = useState<Value>(() => Array.isArray(value) ? [...value] : value)
  const [draft, setDraft] = useState<Value>(() => Array.isArray(value) ? [...value] : value)
  const [item, setItem] = useState<{ index: number; original: string; text: string } | null>(null)
  const [confirmDiscard, setConfirmDiscard] = useState(false)
  const bodyRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const returnFocusRef = useRef(document.activeElement as HTMLElement | null)
  const dirty = JSON.stringify(draft) !== JSON.stringify(initialValue) || Boolean(item && item.text !== item.original)

  useEffect(() => { const trigger = returnFocusRef.current; return () => { trigger?.focus() } }, [])
  useEffect(() => { if (confirmDiscard) bodyRef.current?.querySelector('button')?.focus(); else if (textareaRef.current) textareaRef.current.focus(); else bodyRef.current?.querySelector('button')?.focus() }, [confirmDiscard, item?.index])

  const requestClose = () => { if (dirty) setConfirmDiscard(true); else onClose() }
  const applyItem = () => {
    if (!item || !Array.isArray(draft) || !item.text.trim()) return
    setDraft(item.index === -1 ? [...draft, item.text] : draft.map((text, index) => index === item.index ? item.text : text))
    setItem(null)
  }

  return <Dialog open title={field.label} onClose={requestClose} className="flex h-[min(640px,calc(100svh-2rem))] max-w-3xl flex-col overflow-hidden" contentClassName="flex min-h-0 flex-1 flex-col p-0">
    <div ref={bodyRef} aria-label={`Edit ${field.label}`} className="flex min-h-0 flex-1 flex-col">
      {confirmDiscard ? <>
        <div className="flex min-h-0 flex-1 flex-col justify-center gap-2 overflow-y-auto p-5"><p className="font-mono text-[10px] font-bold text-slate-50">Discard changes to this field?</p><p className="font-sans text-[9px] leading-4 text-muted-foreground">Your Agent configuration will remain unchanged.</p></div>
        <div className="flex min-h-[56px] shrink-0 justify-end gap-2 border-t border-border bg-surface/[0.98] px-4 py-3"><Button type="button" variant="outline" onClick={() => setConfirmDiscard(false)}>Keep editing</Button><Button type="button" variant="destructive" onClick={onClose}>Discard changes</Button></div>
      </> : <>
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden p-4">
          <div className="shrink-0 border-b border-border pb-3"><p className="truncate font-mono text-[9px] font-semibold text-slate-100">{agentName || 'Unnamed Agent'}</p><p className="mt-1 font-sans text-[9px] leading-4 text-muted-foreground">{field.help}</p></div>
          {Array.isArray(draft) && !item ? <>
            <div className="flex shrink-0 items-center justify-between gap-3"><span className="font-mono text-[8px] text-muted-foreground">{draft.length} items</span><Button type="button" size="sm" onClick={() => setItem({ index: -1, original: '', text: '' })}><Plus className="h-3.5 w-3.5" />Add item</Button></div>
            <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain rounded-container border border-border bg-background/20">{draft.length === 0 ? <p className="p-4 font-sans text-[9px] text-muted-foreground">No items configured.</p> : draft.map((text, index) => <div key={index} className="flex items-center gap-3 border-b border-border/60 px-3 py-2.5 last:border-b-0"><p className="line-clamp-2 min-w-0 flex-1 break-words font-sans text-[10px] leading-4 text-slate-200">{text || 'Empty item'}</p><div className="flex shrink-0 gap-1"><Button type="button" size="sm" variant="ghost" aria-label={`Edit ${field.label.toLowerCase()} ${index + 1}`} onClick={() => setItem({ index, original: text, text })}><Pencil className="h-3.5 w-3.5" /></Button><Button type="button" size="sm" variant="ghost" className="text-muted-foreground hover:text-red-300" aria-label={`Remove ${field.label.toLowerCase()} ${index + 1}`} onClick={() => setDraft(draft.filter((_, itemIndex) => itemIndex !== index))}><Trash2 className="h-3.5 w-3.5" /></Button></div></div>)}</div>
          </> : <div className="min-h-0 flex-1 [&>div]:h-full"><Textarea ref={textareaRef} aria-label={item ? `${field.label} item` : field.label} value={item ? item.text : draft as string} onChange={event => item ? setItem({ ...item, text: event.target.value }) : setDraft(event.target.value)} placeholder={item ? 'Describe this item...' : field.help} className="scrollbar-thin h-full min-h-0 resize-none overflow-y-auto overscroll-contain bg-background/25 font-sans text-[11px] leading-5" /></div>}
        </div>
        <div className="flex min-h-[56px] shrink-0 flex-wrap items-center justify-between gap-3 border-t border-border bg-surface/[0.98] px-4 py-3"><p className="font-sans text-[8px] text-muted-foreground">{item ? 'Apply this item, then apply the field changes.' : 'Apply locally, then save the Agent Draft.'}</p><div className="ml-auto flex gap-2">{item ? <><Button type="button" variant="outline" onClick={() => setItem(null)}>Cancel item</Button><Button type="button" disabled={!item.text.trim()} onClick={applyItem}>{item.index === -1 ? 'Add item' : 'Apply item'}</Button></> : <><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="button" onClick={() => { onApply(draft); onClose() }}>Apply changes</Button></>}</div></div>
      </>}
    </div>
  </Dialog>
}
