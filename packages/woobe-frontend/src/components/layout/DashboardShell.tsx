import { Outlet } from 'react-router-dom'
import { ScrollArea } from '@/components/ui/ScrollArea'

export function DashboardShell() {
  return (
    <ScrollArea className="flex-1 p-6">
      <Outlet />
    </ScrollArea>
  )
}
