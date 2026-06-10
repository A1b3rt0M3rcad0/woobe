import { CopyButton } from '@/components/common/CopyButton'
import { cn } from '@/lib/utils'

interface JsonCodeBlockProps {
  data: unknown
  title?: string
  maxHeight?: string
  className?: string
  copyText?: string
}

export function JsonCodeBlock({ data, title, maxHeight = 'max-h-60', className, copyText }: JsonCodeBlockProps) {
  const text = JSON.stringify(data, null, 2)
  return (
    <div className={cn('space-y-2', className)}>
      {title && (
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted">{title}</p>
          {text && <CopyButton text={copyText || text} />}
        </div>
      )}
      <pre
        className={cn(
          'rounded-lg border border-border bg-background p-3 text-xs overflow-y-auto',
          maxHeight,
        )}
      >
        <code className="text-muted whitespace-pre-wrap break-all">{text}</code>
      </pre>
    </div>
  )
}
