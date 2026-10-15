import { formatCurrency, formatLatency, formatTokens } from '@/lib/formatters/number'

export function RunMetrics({ cost, costStatus, tokens, runtime, counts, loading = false }: {
  cost: number | null
  costStatus: string
  tokens: number | null
  runtime: number | null
  counts: { label: string; value: number | null }[]
  loading?: boolean
}) {
  const priced = cost != null && (costStatus === 'known' || costStatus === 'partial' || costStatus === 'estimated')
  const costLabel = loading ? 'Loading…' : priced ? `${formatCurrency(cost)}${costStatus === 'partial' ? '+' : ''}` : 'Cost unavailable'
  const tokenValue = tokens == null ? 'Unavailable' : tokens >= 1_000_000 ? new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(tokens) : formatTokens(tokens)
  return <div className="space-y-ui-sm" data-run-metrics>
    <dl className="woobe-metric-grid">
      <div className="col-span-full min-w-0 rounded-control border border-border bg-panel-band p-ui-md">
        <dt className="font-sans text-chrome-label text-muted-foreground">Run cost{costStatus === 'partial' ? ' · partial' : costStatus === 'estimated' ? ' · estimated' : ''}</dt>
        <dd className={priced ? 'mt-ui-xs whitespace-nowrap font-mono text-metric-compact text-foreground' : 'mt-ui-xs font-sans text-product-body font-medium text-foreground'}>{costLabel}</dd>
        <details className="mt-ui-sm text-system-meta text-muted-foreground">
          <summary className="min-h-control-xs cursor-pointer font-sans">Cost details</summary>
          <p className="mt-ui-xs font-sans">{priced ? 'Recorded cost in USD. Partial totals exclude unpriced operations.' : 'Pricing is not available for this Run. This does not indicate an execution failure.'}</p>
          <p className="mt-ui-xs break-all font-mono">Status: {costStatus}{cost != null ? ` · USD ${cost}` : ''}</p>
        </details>
      </div>
      {[['Total tokens', tokenValue], ['Runtime', runtime == null ? 'Unavailable' : formatLatency(runtime)]].map(([label, value]) =>
        <div key={label} className="min-w-0 rounded-control border border-border bg-surface p-ui-md">
          <dt className="font-sans text-chrome-label text-muted-foreground">{label}</dt>
          <dd className={value === 'Unavailable' || loading ? 'mt-ui-xs font-sans text-product-small text-muted-foreground' : 'mt-ui-xs whitespace-nowrap font-mono text-metric-compact text-foreground'}>{loading ? 'Loading…' : value}</dd>
        </div>)}
    </dl>
    {tokens != null && tokens >= 1_000_000 && <details className="font-sans text-system-meta text-muted-foreground"><summary className="min-h-control-xs cursor-pointer">Exact token usage</summary><p className="font-mono">{formatTokens(tokens)} total tokens</p></details>}
    <dl className="divide-y divide-border border-y border-border">
      {counts.map(({ label, value }) => <div key={label} className="flex items-baseline justify-between gap-ui-md py-ui-sm">
        <dt className="font-sans text-chrome-label text-muted-foreground">{label}</dt>
        <dd className="whitespace-nowrap font-mono text-system-value text-foreground">{loading ? '…' : value == null ? '—' : formatTokens(value)}</dd>
      </div>)}
    </dl>
  </div>
}
