import type { ReactNode } from 'react'

export interface ContributionRow {
  id: string
  label: ReactNode
  value: number | null
  share: number | null
}

/** Length encodes the supplied share, with no minimum visual fill. */
export function ContributionBars({ rows, unit }: { rows: ContributionRow[]; unit: string }) {
  return <div className="space-y-ui-md" data-contribution-bars>
    <p className="font-sans text-system-meta text-muted-foreground">{unit}</p>
    <dl className="space-y-ui-md">
      {rows.map(row => <div key={row.id}>
        <div className="flex flex-wrap items-baseline justify-between gap-x-ui-sm gap-y-ui-xs">
          <dt className="min-w-0 break-words font-sans text-chrome-label text-foreground">{row.label}</dt>
          <dd className="ml-auto flex shrink-0 gap-ui-sm whitespace-nowrap font-mono text-system-meta text-foreground">
            <span>{row.value == null ? 'Unavailable' : row.value.toLocaleString()}</span>
            <span className="min-w-[4rem] text-right text-muted-foreground">{row.share == null ? '—' : `${(row.share * 100).toFixed(row.share >= .1 ? 1 : 2)}%`}</span>
          </dd>
        </div>
        <div aria-hidden="true" className="mt-ui-xs h-2 overflow-hidden rounded-technical bg-control">
          {row.share != null && <div className="h-full bg-primary-light" style={{ width: `${Math.max(0, Math.min(100, row.share * 100))}%` }} />}
        </div>
      </div>)}
    </dl>
  </div>
}
