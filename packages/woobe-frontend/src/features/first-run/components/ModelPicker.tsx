import { Search } from 'lucide-react'
import { EmptyStatePanel, Skeleton, TechnicalListItem } from '@woobe/ui'
import { Input } from '@/components/ui/Input'
import { ScrollArea } from '@/components/ui/ScrollArea'

export interface ModelPickerItem { id: string; title: string; subtitle: string; metadata?: string }

interface ModelPickerProps {
  items: ModelPickerItem[]
  selectedId?: string
  query: string
  onQueryChange: (query: string) => void
  onSelect: (id: string) => void
  loading?: boolean
  emptyTitle?: string
  emptyDescription?: string
  resultNote?: string
}

export function ModelPicker({ items, selectedId, query, onQueryChange, onSelect, loading = false, emptyTitle = 'No generation models found', emptyDescription = 'Try another search or add the model manually.', resultNote }: ModelPickerProps) {
  return (
    <div className={`grid h-full min-h-0 gap-2 overflow-hidden ${resultNote ? 'grid-rows-[auto_auto_minmax(0,1fr)]' : 'grid-rows-[auto_minmax(0,1fr)]'}`}>
      <div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" /><Input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="Search models" className="pl-9" /></div>
      {resultNote ? <p className="font-sans text-[11px] leading-4 text-muted">{resultNote}</p> : null}
      <ScrollArea className="model-picker-scroll h-full min-h-0 overflow-y-scroll rounded-container border border-border bg-background/30 p-1.5 pr-1">
        {loading ? (
          <div className="space-y-1.5 pr-1">{Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-[50px] w-full" />)}</div>
        ) : items.length === 0 ? (
          <EmptyStatePanel compact title={emptyTitle} description={emptyDescription} className="h-full min-h-40 border-0 bg-transparent" />
        ) : (
          <div className="space-y-1 pr-1">{items.map((item) => <TechnicalListItem key={item.id} label={item.title} description={item.subtitle} meta={item.metadata} selected={item.id === selectedId} onClick={() => onSelect(item.id)} />)}</div>
        )}
      </ScrollArea>
    </div>
  )
}
