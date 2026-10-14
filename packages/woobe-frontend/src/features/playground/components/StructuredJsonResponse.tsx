import { CodePanel, EmptyStatePanel, JsonCodeBlock, woobeLayout } from '@woobe/ui'

interface StructuredJsonResponseProps {
  value: unknown
  raw?: string
  maxHeight?: number | string
  className?: string
  density?: 'comfortable' | 'compact'
}

export function StructuredJsonResponse({ value, maxHeight, className, density = 'comfortable' }: StructuredJsonResponseProps) {
  if (value == null || value === '') return <CodePanel title="Structured response" className={className}><div className="p-ui-md"><EmptyStatePanel compact title="No structured output" description="This Run did not persist a structured response payload." /></div></CodePanel>
  return <JsonCodeBlock title="Structured response" value={value} className={className}
    maxHeight={maxHeight ?? (density === 'compact' ? woobeLayout.codeStructuredCompact : woobeLayout.codeStructuredDefault)}
    density={density === 'compact' ? 'compact' : 'default'} />
}
