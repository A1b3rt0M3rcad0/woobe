import { Check, Search } from 'lucide-react'

import { Input } from '@/components/ui/Input'
import { ScrollArea } from '@/components/ui/ScrollArea'

export interface ModelPickerItem {
  id: string
  title: string
  subtitle: string
  metadata?: string
}

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
    <div
      className={`grid h-full min-h-0 gap-3 overflow-hidden ${
        resultNote
          ? 'grid-rows-[auto_auto_minmax(0,1fr)]'
          : 'grid-rows-[auto_minmax(0,1fr)]'
      }`}
    >
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search models"
          className="h-10 pl-9"
        />
      </div>

      {resultNote && <p className="text-xs leading-5 text-muted">{resultNote}</p>}

      <ScrollArea className="model-picker-scroll h-full min-h-0 overflow-y-scroll rounded-xl border border-border/80 bg-background/40 p-2 pr-1.5">
        {loading ? (
          <div className="space-y-2 pr-1">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="h-[68px] animate-pulse rounded-lg border border-border/60 bg-surface/50" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="flex h-full min-h-56 flex-col items-center justify-center px-6 text-center">
            <p className="text-sm font-medium text-white">{emptyTitle}</p>
            <p className="mt-1 max-w-sm text-xs leading-5 text-muted">{emptyDescription}</p>
          </div>
        ) : (
          <div className="space-y-2 pr-1">
            {items.map((item) => {
              const selected = item.id === selectedId
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelect(item.id)}
                  aria-pressed={selected}
                  className={`flex h-[68px] min-h-[68px] max-h-[68px] w-full items-center justify-between gap-4 overflow-hidden rounded-lg border px-4 py-2 text-left transition-colors ${
                    selected
                      ? 'border-primary/55 bg-primary/[0.08]'
                      : 'border-border/70 bg-background/55 hover:border-primary/30 hover:bg-background/80'
                  }`}
                >
                  <span className="min-w-0 overflow-hidden">
                    <span className="block truncate text-sm font-medium text-white" title={item.title}>{item.title}</span>
                    <span className="mt-0.5 block truncate text-xs text-muted" title={item.subtitle}>{item.subtitle}</span>
                    {item.metadata && (
                      <span className="mt-0.5 block truncate text-[11px] text-muted/75" title={item.metadata}>
                        {item.metadata}
                      </span>
                    )}
                  </span>
                  <span
                    className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
                      selected ? 'border-primary bg-primary text-white' : 'border-border bg-background'
                    }`}
                  >
                    {selected && <Check className="h-3 w-3" />}
                  </span>
                </button>
              )
            })}
          </div>
        )}
      </ScrollArea>
    </div>
  )
}