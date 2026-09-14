import { type ReactNode } from 'react'
import { cn } from '../lib/cn'
import { ScrollArea } from './ScrollArea'

export interface TableColumn<T> {
  key: string
  header: string
  render?: (item: T) => ReactNode
  className?: string
}

export interface TableProps<T> {
  columns: TableColumn<T>[]
  data: T[]
  keyExtractor: (item: T) => string
  onRowClick?: (item: T) => void
  className?: string
  emptyLabel?: ReactNode
}

export function Table<T>({
  columns,
  data,
  keyExtractor,
  onRowClick,
  className,
  emptyLabel = 'No data',
}: TableProps<T>) {
  return (
    <ScrollArea orientation="both" className={cn('w-full', className)}>
      <table className="w-full font-sans text-product-small">
        <thead className="bg-background/20">
          <tr className="border-b border-border">
            {columns.map((column) => (
              <th
                key={column.key}
                className={cn('px-ui-lg py-ui-md text-left font-mono text-system-label font-semibold uppercase tracking-ui-label text-muted-foreground', column.className)}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-ui-lg py-ui-xxl text-center font-sans text-product-small text-muted-foreground">
                {emptyLabel}
              </td>
            </tr>
          ) : (
            data.map((item) => (
              <tr
                key={keyExtractor(item)}
                onClick={() => onRowClick?.(item)}
                className={cn(
                  'border-b border-border/70 transition-colors last:border-b-0',
                  onRowClick && 'cursor-pointer hover:bg-accent/35',
                )}
              >
                {columns.map((column) => (
                  <td key={column.key} className={cn('px-ui-lg py-ui-md align-middle text-accent-foreground/85', column.className)}>
                    {column.render ? column.render(item) : String((item as Record<string, unknown>)[column.key] ?? '')}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </ScrollArea>
  )
}
