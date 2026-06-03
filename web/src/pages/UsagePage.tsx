import { useParams } from 'react-router-dom'
import { useProjectUsage } from '@/features/usage/hooks'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Table } from '@/components/ui/Table'
import { formatMoney } from '@/lib/formatters/money'
import { BarChart3, MessageSquare, FileText, Wrench, Database, HardDrive } from 'lucide-react'
import type { DailyUsage } from '@/features/usage/types'

export default function UsagePage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: usage, isLoading, isError, error, refetch } = useProjectUsage(projectId)

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const totalRequests = usage?.reduce((s: number, d: DailyUsage) => s + d.requests, 0) || 0
  const totalInput = usage?.reduce((s: number, d: DailyUsage) => s + d.input_tokens, 0) || 0
  const totalOutput = usage?.reduce((s: number, d: DailyUsage) => s + d.output_tokens, 0) || 0
  const totalCost = usage?.reduce((s: number, d: DailyUsage) => s + d.cost_usd, 0) || 0

  const statCards = [
    { icon: MessageSquare, label: 'Requests', value: totalRequests.toLocaleString() },
    { icon: FileText, label: 'Input Tokens', value: totalInput.toLocaleString() },
    { icon: FileText, label: 'Output Tokens', value: totalOutput.toLocaleString() },
    { icon: BarChart3, label: 'Estimated Cost', value: formatMoney(totalCost) },
    { icon: Wrench, label: 'Tool Calls', value: '—' },
    { icon: Database, label: 'Vector Queries', value: '—' },
    { icon: HardDrive, label: 'Storage', value: '—' },
  ]

  const columns = [
    { key: 'day', header: 'Date' },
    { key: 'requests', header: 'Requests' },
    { key: 'input_tokens', header: 'Input Tokens' },
    { key: 'output_tokens', header: 'Output Tokens' },
    { key: 'cost_usd', header: 'Cost', render: (d: DailyUsage) => formatMoney(d.cost_usd) },
  ]

  return (
    <div>
      <PageHeader title="Usage" description="Track your project usage and costs" />

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 mb-8">
        {statCards.map((s) => (
          <Card key={s.label}>
            <CardContent className="flex items-center gap-3 p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <s.icon className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-lg font-bold text-white">{s.value}</p>
                <p className="text-xs text-muted">{s.label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {usage && usage.length > 0 ? (
        <Card>
          <CardHeader><CardTitle>Daily Usage</CardTitle></CardHeader>
          <CardContent className="p-0">
            <Table columns={columns} data={usage} keyExtractor={(d) => d.day} />
          </CardContent>
        </Card>
      ) : (
        <EmptyState icon={<BarChart3 className="h-12 w-12" />} title="No usage data" description="Usage data will appear once you start using your agents." />
      )}
    </div>
  )
}
