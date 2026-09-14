import { Search } from 'lucide-react'
import { EmptyStatePanel, Input, ScrollArea, Skeleton, TechnicalListItem } from '@woobe/ui'

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

export function ModelPicker({
  items,
  selectedId,
  query,
  onQueryChange,
  onSelect,
  loading = false,
  emptyTitle = 'No generation models found',
  emptyDescription = 'Try another search or add the model manually.',
  resultNote,
}: ModelPickerProps) {
  return (
    <div className={`grid h-full min-h-0 gap-ui-sm overflow-hidden ${resultNote ? 'grid-rows-[auto_auto_minmax(0,1fr)]' : 'grid-rows-[auto_minmax(0,1fr)]'}`}>
      <div className="relative">
        <Search className="pointer-events-none absolute left-ui-md top-1/2 h-icon w-icon -translate-y-1/2 text-muted-foreground" />
        <Input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="Search models" className="pl-9" />
      </div>
      {resultNote ? <p className="font-sans text-product-caption leading-5 text-muted-foreground">{resultNote}</p> : null}
      <ScrollArea className="model-picker-scroll h-full min-h-0 overflow-y-scroll rounded-container border border-border bg-background/30 p-ui-xs pr-ui-xs">
        {loading ? (
          <div className="grid gap-ui-xs pr-ui-xs">
            {Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-control-row w-full" />)}
          </div>
        ) : items.length === 0 ? (
          <EmptyStatePanel compact title={emptyTitle} description={emptyDescription} className="h-full min-h-40 border-0 bg-transparent" />
        ) : (
          <div className="grid gap-ui-xs pr-ui-xs">
            {items.map((item) => (
              <TechnicalListItem
                key={item.id}
                label={item.title}
                description={item.subtitle}
                meta={item.metadata}
                selected={item.id === selectedId}
                onClick={() => onSelect(item.id)}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  )
}
